import sys
import time
import math
import socket
import ssl
import urllib3
import traceback

from collections import defaultdict
from dateutil import parser
from threading import Thread
from datetime import datetime
from queue import PriorityQueue
from multiprocessing import Queue, Value
from typing import List, Dict, Callable, Tuple, Generator

from kubernetes import client, watch
from kubernetes.client.api_client import ApiClient

from mlad.core.kubernetes import controller as ctrl
from mlad.core.libs.constants import MLAD_PROJECT_APP


class LogHandler:
    def __init__(self, cli: ApiClient, namespace: str, tail: str):
        self.api = client.CoreV1Api(cli)
        self.responses = {}
        self.namespace = namespace
        self.tail = None if tail == 'all' else tail
        self.last_timestamp_dict = defaultdict(str)

    def close(self, resp: str = None):
        for _ in ([self.responses.get(resp)] if resp else list(self.responses.values())):
            if _ and _._fp and _._fp.fp:
                try:
                    sock = _._fp.fp.raw._sock
                    if isinstance(sock, ssl.SSLSocket):
                        sock.shutdown(socket.SHUT_RDWR)
                    else:
                        sock.shutdown()
                    sock.close()
                except AttributeError as e:
                    print(f'Error on LogHandler::Close! [{e}]')

    def _parse_log(self, log: str):
        # log response to timestamp & msg
        separated = log.split(' ', 1)
        timestamp = separated[0]
        msg = separated[1] if len(separated) > 1 else ''
        if not (msg.endswith('\n') or msg.endswith('\r')):
            msg += '\n'
        return timestamp, msg.encode()

    def get_stacked_logs(self, targets: List):
        for target in targets:
            resp = self.api.read_namespaced_pod_log(name=target, namespace=self.namespace,
                                                    tail_lines=self.tail, timestamps=True)
            logs = resp.split('\n')
            for log in logs:
                timestamp, msg = self._parse_log(log)
                if len(timestamp) == 0:
                    break
                self.last_timestamp_dict[target] = timestamp
                yield timestamp, target, msg

    def get_stream_logs(self, target: str, **params):
        since_seconds = params.get('since_seconds', None)
        try:
            resp = self.api.read_namespaced_pod_log(name=target, namespace=self.namespace,
                                                    timestamps=True, follow=True,
                                                    since_seconds=since_seconds,
                                                    _preload_content=False)
            self.responses[target] = resp
            for line in resp:
                try:
                    log = line.decode()
                except UnicodeDecodeError as e:
                    print(f"[Ignored] Log Decode Error : {e}")
                    continue
                timestamp, msg = self._parse_log(log)
                yield timestamp, target, msg
        except urllib3.exceptions.ProtocolError:
            pass
        except urllib3.exceptions.ReadTimeoutError:
            pass
        if target in self.responses:
            del self.responses[target]


class LogCollector():
    def __init__(self, timestamps: bool = False, maxbuffer: int = 65535,
                 release_callback: Callable = None):
        self.name_width = 0
        self.threads = {}
        self.stream_logs = Queue(maxsize=maxbuffer)
        self.stacked_logs = PriorityQueue(maxsize=maxbuffer)
        self.release_callback = release_callback
        self.should_run = Value('b', True)
        self.streaming = Value('b', False)
        self.timestamps = timestamps

    def _output_dict(self, target: str, log: str, timestamp: str = None):
        self.name_width = max(self.name_width, len(target))
        output = {'name': target, 'stream': log, 'name_width': self.name_width}
        if timestamp is not None:
            output['timestamp'] = str(parser.parse(timestamp).astimezone())
        return output

    def __next__(self):
        if not self.stacked_logs.empty():
            msg = self.stacked_logs.get()
            timestamp = str(parser.parse(msg[0]).astimezone())
            name, log = msg[1]
            return self._output_dict(name, log.decode(), timestamp if self.timestamps else None)
        else:
            if self.streaming == True:
                msg = self.stream_logs.get()
                object_id = msg['object_id']
                timestamp = msg['timestamp']
                if 'stream' in msg:
                    timestamp = str(parser.parse(msg['timestamp']).astimezone())
                    stream = msg['stream'].decode()
                    target = msg['target']
                    return self._output_dict(target, stream, timestamp if self.timestamps else None)
                elif 'status' in msg and msg['status'] == 'stopped':
                    del self.threads[object_id]
                    if len(self.threads) == 0:
                        raise StopIteration
                    return self.__next__()
                else:
                    raise RuntimeError('Invalid stream type.')
            else:
                raise StopIteration

    def __iter__(self):
        return self

    def __enter__(self):
        self.should_run.value = True
        return self

    def __exit__(self, ty, val, tb):
        self.release()
        if ty not in [None, KeyboardInterrupt]:
            traceback.print_exception(ty, val, tb)
        return True

    def __del__(self):
        self.release()

    def collect_logs(self, names: List, stream: bool = True, handler: LogHandler = None):
        for timestamp, target, log in handler.get_stacked_logs(names):
            self.stacked_logs.put((timestamp, (target, log)))

        if stream:
            self.streaming = True
            logs = []
            last_timestamp = self.stacked_logs.queue[self.stacked_logs.qsize()-1][0]
            for target in names:
                last_timestamp = handler.last_timestamp_dict.get(target, None)
                if last_timestamp is not None:
                    dt = datetime.strptime(last_timestamp[:len(last_timestamp)-4], '%Y-%m-%dT%H:%M:%S.%f')
                    ms = dt.microsecond / 10**6
                    ts = time.mktime(dt.timetuple())
                    since_seconds = math.floor(datetime.utcnow().timestamp() - ts - ms)
                else:
                    since_seconds = None
                log = (target, handler.get_stream_logs(target, since_seconds=since_seconds))
                logs.append(log)
            for name, log in logs:
                self.add_iterable(log, name)


    def add_iterable(self, iterable: Generator, name: str = None):
        self.name_width = max(self.name_width, len(name))
        if name not in [_['name'] for _ in self.threads.values()]:
            self.threads[id(iterable)] = {
                'name': name,
                'thread': Thread(target=LogCollector._read_stream,
                                 args=(iterable, self.stream_logs, self.should_run), daemon=True)
            }
            self.threads[id(iterable)]['thread'].start()
        else:
            print(f"Failed to add interable. Conflicted name [{name}].")

    def release(self):
        self.should_run.value = False
        if self.release_callback:
            self.release_callback()
        for _ in self.threads.values():
            _['thread'].join()

    thread_count = 0

    @classmethod
    def _read_stream(cls, iterable, queue: Queue, should_run: bool):
        LogCollector.thread_count += 1
        for timestamp, target, log in iterable:
            if not should_run.value:
                break
            if log:
                queue.put({'timestamp': timestamp, 'target': target, 'stream': log,
                           'object_id': id(iterable)})
            time.sleep(.001)
        timestamp_now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        queue.put({'timestamp': timestamp_now, 'status': 'stopped', 'object_id': id(iterable)})
        LogCollector.thread_count -= 1


class LogMonitor(Thread):
    @staticmethod
    def api_wrapper(fn, callback):
        def inner(*args, **kwargs):
            resp = fn(*args, **kwargs)
            callback(resp)
            return resp
        return inner

    def __init__(self, cli, handler, collector, namespace, app_names, last_resource, **params):
        Thread.__init__(self)
        self.daemon = True
        self.api = client.CoreV1Api(cli)
        self.handler = handler
        self.collector = collector
        self.namespace = namespace
        self.app_names = app_names
        self.resource_version = last_resource
        self.params = params
        self.__stopped = False

        self.stream_resp = None

    def run(self):
        namespace = self.namespace
        follow = self.params['follow']
        timestamps = self.params['timestamps']

        def assign(x):
            self.stream_resp = x

        w = watch.Watch()
        while not self.__stopped:
            try:
                print(f'Watch Start [{namespace}]')
                wrapped_api = LogMonitor.api_wrapper(self.api.list_namespaced_pod, assign)
                label_selector = f'{MLAD_PROJECT_APP} in ({",".join(self.app_names)})'
                for ev in w.stream(wrapped_api, namespace=namespace, label_selector=label_selector,
                                   resource_version=self.resource_version):
                    event = ev['type']
                    pod = ev['object']['metadata']['name']
                    phase = ev['object']['status']['phase']

                    if event == 'MODIFIED' and phase == 'Running':
                        if 'deletionTimestamp' in ev['object']['metadata']:
                            continue
                        created = ev['object']['metadata']['creationTimestamp']
                        ts = time.mktime(datetime.strptime(created, '%Y-%m-%dT%H:%M:%SZ').timetuple())
                        since_seconds = math.ceil(datetime.utcnow().timestamp() - ts)

                        log = self.handler.get_stream_logs(pod, since_seconds=since_seconds)
                        self.collector.add_iterable(log, pod)
                    elif event == 'DELETED':
                        for oid in [k for k, v in self.collector.threads.items() if v['name'] == pod]:
                            print(f'Register stopped [{oid}]')
                            self.handler.close(pod)
                self.__stopped = True
            except urllib3.exceptions.ProtocolError:
                print(f'Watch Stop [{namespace}]')
                self.__stopped = True
            except client.exceptions.ApiException as e:
                if e.status == 410:
                    print(f"[Re-stream] {e}", file=sys.stderr)
                    continue
                else:
                    raise e

    def stop(self):
        self.__stopped = True
        print('Request Stop LogMonitor')
        if self.stream_resp and self.stream_resp._fp and self.stream_resp._fp.fp:
            try:
                sock = self.stream_resp._fp.fp.raw._sock
                if isinstance(sock, ssl.SSLSocket):
                    sock.shutdown(socket.SHUT_RDWR)
                else:
                    sock.shutdown()
                sock.close()
            except AttributeError as e:
                print(f'Error on LogMonitor::Stop [{e}]')
            finally:
                self.stream_resp = None
