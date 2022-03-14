import sys
import time
import math
from datetime import datetime
import socket
import ssl
import urllib3
import traceback
import docker
import kubernetes
from dateutil import parser
from threading import Thread
from multiprocessing import Queue, Value
from mlad.core.kubernetes import controller as ctrl
from mlad.core.libs.constants import MLAD_PROJECT_APP
from kubernetes import client, watch


class LogHandler:
    def __init__(self, cli):
        self.cli = cli
        self.responses = {}
        self.monitoring = Value('b', True)

    def __del__(self):
        self.release()

    def release(self):
        self.monitoring.value = False

    def close(self, resp=None):
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

    def logs(self, namespace, target, **params):
        follow = params['follow']
        timestamps = params['timestamps']
        tail = None if params['tail'] == 'all' else params['tail']
        since_seconds = None
        if 'since_seconds' in params.keys():
            since_seconds = params['since_seconds']
        cli = ctrl.get_api_client()
        api = client.CoreV1Api(cli)
        try:
            resp = api.read_namespaced_pod_log(name=target, namespace=namespace, tail_lines=tail, timestamps=timestamps,
                                               follow=follow, since_seconds=since_seconds, _preload_content=False)
            self.responses[target] = resp
            for line in resp:
                try:
                    line = line.decode()
                except UnicodeDecodeError as e:
                    print(f"[Ignored] Log Decode Error : {e}")
                    continue
                line = f"{target} {line}"
                if not (line.endswith('\n') or line.endswith('\r')):
                    line += '\n'
                line = line.encode()
                if params.get('timestamps'):
                    separated = line.split(b' ')
                    line = b' '.join([separated[0], separated[1], *separated[2:]])
                yield line
        except urllib3.exceptions.ProtocolError:
            pass
        except urllib3.exceptions.ReadTimeoutError:
            pass
        if target in self.responses:
            del self.responses[target]


class LogCollector():
    def __init__(self, maxbuffer=65535, release_callback=None):
        self.name_width = 0
        self.threads = {}
        self.queue = Queue(maxsize=maxbuffer)
        self.release_callback = release_callback
        self.should_run = Value('b', True)

    def __next__(self):
        msg = self.queue.get()
        object_id = msg['object_id']

        if 'stream' in msg:
            stream = msg['stream'].decode()
            output = {'name': self.threads[object_id]['name'], 'name_width': self.name_width}
            if not self.threads[object_id]['from_dockerpy']:
                if self.threads[object_id]['timestamps']:
                    separated = stream.split(' ', 2)
                    if len(separated) < 3:
                        _, timestamp, body = (*separated, '')
                    else:
                        _, timestamp, body = separated
                    output['timestamp'] = str(parser.parse(timestamp).astimezone())
                    output['stream'] = body
                else:
                    separated = stream.split(' ', 1)
                    if len(separated) < 2:
                        _, body = (*separated, '')
                    else:
                        _, body = separated
                    output['stream'] = body
                output['name'] = f"{_[_.rfind('=')+1:]}"
            else:
                if self.threads[object_id]['timestamps']:
                    separated = stream.split(' ', 1)
                    if len(separated) < 2:
                        timestamp, body = (*separated, '')
                    else:
                        timestamp, body = separated
                    output['timestamp'] = parser.parse(timestamp).astimezone()
                    output['stream'] = body.encode()
                else:
                    output['stream'] = stream.encode()
            return output
        elif 'status' in msg and msg['status'] == 'stopped':
            del self.threads[object_id]
            if len(self.threads) == 0:
                raise StopIteration
            return self.__next__()
        else:
            raise RuntimeError('Invalid stream type.')

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

    def add_iterable(self, iterable, name=None, timestamps=False):
        self.name_width = max(self.name_width, len(name))
        if name not in [_['name'] for _ in self.threads.values()]:
            self.threads[id(iterable)] = {
                'name': name,
                'timestamps': timestamps,
                'from_dockerpy': isinstance(iterable, docker.types.daemon.CancellableStream),
                'thread': Thread(target=LogCollector._read_stream, args=(iterable, self.queue, self.should_run), daemon=True)
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
    def _read_stream(cls, iterable, queue, should_run):
        LogCollector.thread_count += 1
        for _ in iterable:
            if not should_run.value:
                break
            if _:
                queue.put({'stream': _, 'object_id': id(iterable)})
            time.sleep(.001)
        queue.put({'status': 'stopped', 'object_id': id(iterable)})
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
                if len(self.app_names) == 0:
                    label_selector = None
                else:
                    label_selector = f'{MLAD_PROJECT_APP} in ({",".join(self.app_names)})'
                for ev in w.stream(wrapped_api, namespace=namespace, resource_version=self.resource_version,
                                   label_selector=label_selector):
                    event = ev['type']
                    pod = ev['object']['metadata']['name']
                    phase = ev['object']['status']['phase']

                    if event == 'MODIFIED' and phase == 'Running':
                        container_status = ev['object']['status']['containerStatuses'][0]
                        restart = container_status['restartCount']
                        if restart:
                            state = container_status['state']
                            if 'running' in state.keys():
                                created = state['running']['startedAt']
                            else:
                                continue
                        else:
                            created = ev['object']['metadata']['creationTimestamp']
                        ts = time.mktime(datetime.strptime(created, '%Y-%m-%dT%H:%M:%SZ').timetuple())
                        since_seconds = math.ceil(datetime.utcnow().timestamp() - ts)

                        log = self.handler.logs(namespace, pod, details=True, follow=follow,
                                                tail='all', since_seconds=since_seconds, timestamps=timestamps, stdout=True, stderr=True)
                        self.collector.add_iterable(log, name=pod, timestamps=timestamps)
                    elif event == 'DELETED':
                        for oid in [k for k, v in self.collector.threads.items() if v['name'] == pod]:
                            print(f'Register stopped [{oid}]')
                            self.handler.close(pod)
                self.__stopped = True
            except urllib3.exceptions.ProtocolError:
                print(f'Watch Stop [{namespace}]')
                self.__stopped = True
            except kubernetes.client.exceptions.ApiException as e:
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
