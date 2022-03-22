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
from typing import List, Callable, Generator

from kubernetes import client, watch
from kubernetes.client.api_client import ApiClient

from mlad.core.libs.constants import MLAD_PROJECT_APP


class LogHandler:
    def __init__(self, cli: ApiClient, namespace: str, tail: str):
        self.api = client.CoreV1Api(cli)
        self.responses = {}
        self.namespace = namespace
        self.tail = 65535 if tail == 'all' else tail

    def close(self, name: str = None):
        for resp in ([self.responses.get(name)] if name else list(self.responses.values())):
            if resp and resp._fp and resp._fp.fp:
                try:
                    sock = resp._fp.fp.raw._sock
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
        try:
            parser.parse(timestamp)
        except parser.ParserError as e:
            timestamp = None
        msg = separated[1] if len(separated) > 1 else ''
        if not (msg.endswith('\n') or msg.endswith('\r')):
            msg += '\n'
        return timestamp, msg.encode()

    def get_stacked_logs(self, names: List):
        logs_dict = {}
        for name in names:
            resp = self.api.read_namespaced_pod_log(name=name, namespace=self.namespace,
                                                    tail_lines=self.tail, timestamps=True)
            logs = resp.split('\n')
            logs_dict[name] = logs

        while True:
            if all([True if len(logs_dict[name]) == 0 else False for name in names]):
                break
            for name in names:
                logs = logs_dict[name]
                if len(logs) > 0 :
                    timestamp, msg = self._parse_log(logs.pop(0))
                    if timestamp is None:
                        break
                    yield timestamp, name, msg


    def get_stream_logs(self, name: str, **params):
        since_seconds = params.get('since_seconds', None)
        try:
            resp = self.api.read_namespaced_pod_log(name=name, namespace=self.namespace,
                                                    timestamps=True, follow=True,
                                                    since_seconds=since_seconds,
                                                    _preload_content=False)
            self.responses[name] = resp
            for line in resp:
                try:
                    log = line.decode()
                except UnicodeDecodeError as e:
                    print(f"[Ignored] Log Decode Error : {e}")
                    continue
                timestamp, msg = self._parse_log(log)
                yield timestamp, name, msg
            self.close(name)
        except urllib3.exceptions.ProtocolError:
            pass
        except urllib3.exceptions.ReadTimeoutError:
            pass
        if name in self.responses:
            del self.responses[name]


class LogCollector():
    def __init__(self, stream: bool = False, with_timestamp: bool = False,
                 maxbuffer: int = 65535, release_callback: Callable = None):
        self.name_width = 0
        self.thread_dict = {}
        self.stream_logs = Queue(maxsize=maxbuffer)
        self.stacked_logs = PriorityQueue(maxsize=maxbuffer)
        self.release_callback = release_callback
        self.should_run = Value('b', True)
        self.stream = stream
        self.with_timestamp = with_timestamp

    def _output_dict(self, name: str, log: str, timestamp: str = None):
        self.name_width = max(self.name_width, len(name))
        output = {'name': name, 'stream': log, 'name_width': self.name_width}
        if self.with_timestamp:
            output['timestamp'] = str(parser.parse(timestamp).astimezone()) if timestamp is not None\
                else None
        return output

    def __next__(self):
        if not self.stacked_logs.empty():
            msg = self.stacked_logs.get()
            timestamp = msg[0]
            name, log = msg[1]
            return self._output_dict(name, log.decode(), timestamp)
        else:
            if self.stream:
                msg = self.stream_logs.get()
                name = msg['name']
                timestamp = msg['timestamp']
                if 'status' in msg and msg['status'] == 'stopped':
                    del self.thread_dict[name]
                    if len(self.thread_dict) == 0:
                        raise StopIteration
                    return self.__next__()
                stream = msg['stream'].decode()
                output_dict = self._output_dict(name, stream, timestamp)
                if 'timestamp' in output_dict and output_dict['timestamp'] is None:
                    return self.__next__()
                return self._output_dict(name, stream, timestamp)
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

    def collect_logs(self, names: List, handler: LogHandler = None):
        last_timestamp_dict = defaultdict(str)
        for timestamp, name, log in handler.get_stacked_logs(names):
            self.stacked_logs.put((timestamp, (name, log)))
            last_timestamp_dict[name] = timestamp

        if self.stream:
            logs = []
            for name in names:
                last_timestamp = last_timestamp_dict.get(name, None)
                if last_timestamp is not None:
                    dt = datetime.strptime(last_timestamp[:len(last_timestamp) - 4],
                                           '%Y-%m-%dT%H:%M:%S.%f')
                    ms = dt.microsecond / 10**6
                    ts = time.mktime(dt.timetuple())
                    now = datetime.utcnow().timestamp()
                    since_seconds = math.floor(now - ts - ms)
                    since_seconds = since_seconds if since_seconds > 0 else 1
                else:
                    since_seconds = None
                logs = handler.get_stream_logs(name, since_seconds=since_seconds)
                self.add_iterable(logs, name)

    def add_iterable(self, iterable: Generator, name: str = None):
        self.name_width = max(self.name_width, len(name))
        if name not in self.thread_dict:
            self.thread_dict[name] = Thread(target=LogCollector._read_stream,
                                            args=(name, iterable, self.stream_logs, self.should_run),
                                            daemon=True)
            self.thread_dict[name].start()
        else:
            print(f"Failed to add interable. Conflicted name [{name}].")

    def release(self):
        self.should_run.value = False
        if self.release_callback:
            self.release_callback()
        for thread in self.thread_dict.values():
            thread.join()

    @classmethod
    def _read_stream(cls, name: str, iterable: Generator, queue: Queue, should_run: bool):
        for timestamp, name, log in iterable:
            if not should_run.value:
                break
            if log:
                queue.put({'timestamp': timestamp, 'name': name, 'stream': log})
            time.sleep(.001)
        timestamp_now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        queue.put({'timestamp': timestamp_now, 'name': name, 'status': 'stopped'})


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
                    pod_name = ev['object']['metadata']['name']
                    phase = ev['object']['status']['phase']

                    if event == 'MODIFIED' and phase == 'Running':
                        if 'deletionTimestamp' in ev['object']['metadata']:
                            continue
                        created = ev['object']['metadata']['creationTimestamp']
                        ts = time.mktime(datetime.strptime(created, '%Y-%m-%dT%H:%M:%SZ').timetuple())
                        since_seconds = math.ceil(datetime.utcnow().timestamp() - ts)

                        log = self.handler.get_stream_logs(pod_name, since_seconds=since_seconds)
                        self.collector.add_iterable(log, pod_name)
                    elif event == 'DELETED':
                        if pod_name in self.collector.thread_dict:
                            self.handler.close(pod_name)
                            print(f'Register stopped [{pod_name}]')
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
