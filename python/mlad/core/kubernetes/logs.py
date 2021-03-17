import sys
import os
import time
import datetime
import struct
import itertools
import socket
import urllib3
import docker
import requests_unixsocket
from dateutil import parser
from threading import Thread
from multiprocessing import Queue, Value
from mlad.core.libs import utils
from mlad.core.kubernetes import controller as ctrl
from kubernetes import client, watch

class LogHandler:
    def __init__(self, cli):
        self.cli = cli
        self.responses = []
        self.monitoring = Value('b', True)

    def __del__(self):
        self.release()

    def release(self):
        self.monitoring.value = False

    def close(self, resp=None):
        for _ in ([resp] if resp else self.responses):
            try:
                sock = _.raw._fp.fp.raw._sock
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except AttributeError:
                pass

    def logs(self, namespace, target, **params):
        follow = params['follow']
        timestamps = params['timestamps']
        tail = None if params['tail']=='all' else params['tail']
        timeout = None if params['follow'] else 3
        cli = ctrl.get_api_client()
        api = client.CoreV1Api(cli)
        try:
            resp = api.read_namespaced_pod_log(name=target, namespace=namespace, tail_lines=tail, timestamps=timestamps,
                                               follow=follow, _preload_content=False)
            self.responses.append(resp)
            #Thread(target=LogHandler._monitor, args=(self.monitoring, host, target, lambda: self.close(resp)), daemon=True).start()
            for line in resp:
                line = line.decode()
                line = f"{target} {line}"
                sys.stdout.write(f"{line.encode()}")
                if not (line.endswith('\n') or line.endswith('\r')): line += '\n'
                line= line.encode()
                if params.get('timestamps'):
                    separated = line.split(b' ')
                    line = b' '.join([separated[0], separated[1], *separated[2:]])
                    #line = b' '.join([separated[1], separated[0], *separated[2:]])
                yield line
            self.responses.remove(resp)
        except urllib3.exceptions.ProtocolError:
            pass
        except urllib3.exceptions.ReadTimeoutError:
            pass

    @classmethod
    def _monitor(cls, should_run, host, target, callback):
        params = {'stderr': True, 'tail': 1}
        cli = ctrl.get_api_client()
        api = client.CoreV1Api(cli)
        while should_run.value:
            ret = api.read_namespaced_pod_log(name=target, namespace=namespace, follow=True, _preload_content=False)
           # status = requests_unixsocket.get(f"{host}/v1.24{target}/logs", params=params, timeout=1).status_code
            if ret.status != 200:
                callback()
                break
            time.sleep(1)

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
            output = {'name': self.threads[object_id]['name'], 'name_width': self.name_width+6}
            if not self.threads[object_id]['from_dockerpy']:
                if self.threads[object_id]['timestamps']:
                    separated = stream.split(' ', 2)
                    if len(separated) < 3: _, timestamp, body = (*separated, '')
                    else: _, timestamp, body = separated
                    output['timestamp'] = parser.parse(timestamp).astimezone()
                    output['stream'] = body.encode()
                else:
                    separated = stream.split(' ', 1)
                    if len(separated) < 2: _, body = (*separated, '')
                    else: _, body = separated
                    output['stream'] = body.encode()
                output['name'] = f"{_[_.rfind('=')+1:]}"
            else:
                if self.threads[object_id]['timestamps']:
                    separated = stream.split(' ', 1)
                    if len(separated) < 2: timestamp, body = (*separated, '')
                    else: timestamp, body = separated
                    output['timestamp'] = parser.parse(timestamp).astimezone()
                    output['stream'] = body.encode()
                else:
                    output['stream'] = stream.encode()
            return output
        elif 'status' in msg and msg['status'] == 'stopped':
            del self.threads[object_id]
            if not self.threads: raise StopIteration
            return self.__next__()
        else: raise RuntimeError('Invalid stream type.')

    def __iter__(self):
        return self

    def __enter__(self):
        self.should_run.value = True
        return self

    def __exit__(self, ty, val, tb):
        self.release()
        if not ty in [None, KeyboardInterrupt]:
            import traceback
            traceback.print_exception(ty, val, tb)
        return True

    def __del__(self):
        self.release()

    def add_iterable(self, iterable, name=None, timestamps=False):
        self.name_width = max(self.name_width, len(name))
        self.threads[id(iterable)] = {
            'name': name,
            'timestamps': timestamps,
            'from_dockerpy': isinstance(iterable, docker.types.daemon.CancellableStream),
            'thread': Thread(target=LogCollector._read_stream, args=(iterable, self.queue, self.should_run), daemon=True)
        }
        self.threads[id(iterable)]['thread'].start()

    def remove_iterable(self, object_id):
        pass


    def release(self):
        self.should_run.value = False
        if self.release_callback:
            self.release_callback()
        for _ in self.threads.values():
            _['thread'].join()
        self.threads.clear()

    @classmethod
    def _read_stream(cls, iterable, queue, should_run):
        for _ in iterable:
            if not should_run.value: break
            if _: queue.put({'stream': _, 'object_id': id(iterable)})
        queue.put({'status': 'stopped', 'object_id': id(iterable)})


class LogMonitor(Thread):

    def __init__(self, cli, handler, collector, namespace, last_resource, **params):
        Thread.__init__(self)
        self.daemon = True
        self.api = client.CoreV1Api(cli)
        self.handler = handler
        self.collector = collector
        self.namespace = namespace
        self.resource_version = last_resource
        self.params = params
        self.__stopped = False

    def run(self):
        api = self.api
        namespace = self.namespace
        follow = self.params['follow']
        tail = self.params['tail']
        timestamps = self.params['timestamps']
        added = [] #pending pods of svc

        w = watch.Watch()
        for e in w.stream(api.list_namespaced_pod, namespace=namespace, resource_version=self.resource_version):
            if self.__stopped:
                break

            event = e['type']
            pod = e['object'].metadata.name
            phase = e['object'].status.phase
            service = e['object'].metadata.labels['MLAD.PROJECT.SERVICE']

            if event == 'ADDED':
                added.append(pod)
            elif event == 'MODIFIED' and phase == 'Running':
                if pod in added:
                    log = self.handler.logs(namespace, pod, details=True, follow=follow,
                                            tail=tail, timestamps=timestamps, stdout=True, stderr=True)
                    self.collector.add_iterable(log, name=service, timestamps=timestamps)
                    added.remove(pod)
            elif event == 'DELETED':
                object_id = None
                for id, _ in self.collector.threads.items():
                    if _['name'] == service:
                        object_id = id
                        break
                if object_id:
                    self.collector.remove_iterable(object_id)

    def stop(self):
        self.__stopped = True

