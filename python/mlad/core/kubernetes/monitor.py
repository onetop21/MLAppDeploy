import ssl
import socket
import urllib3
from threading import Thread
from multiprocessing import Queue
from kubernetes import client, watch


class DelMonitor(Thread):
    @staticmethod
    def api_wrapper(fn, callback):
        def inner(*args, **kwargs):
            resp = fn(*args, **kwargs)
            callback(resp)
            return resp
        return inner

    def __init__(self, cli, collector, service_specs, namespace, timeout=0xFFFF):
        super().__init__(daemon=True)
        self.__stopped = False
        self.api = client.CoreV1Api(cli)
        self.collector = collector
        self.service_specs = service_specs
        self.namespace = namespace
        self.timeout = timeout

        self.stream_resp = None

    def run(self):
        def assign(x):
            self.stream_resp = x

        target_task_keys = []
        service_name_to_task_keys = {}
        for spec in self.service_specs:
            name, _, task_keys = spec
            service_name_to_task_keys[name] = task_keys
            target_task_keys.extend(task_keys)
        w = watch.Watch()
        completed = False
        self.collector.queue.put({'stream': 'Wait for the services to be removed...'})
        try:
            wrapped_api = DelMonitor.api_wrapper(self.api.list_namespaced_pod, assign)
            for ev in w.stream(wrapped_api, namespace=self.namespace,
                               _request_timeout=self.timeout):
                event = ev['type']
                pod_name = ev['object']['metadata']['name']
                service_name = ev['object']['metadata']['labels']['MLAD.PROJECT.SERVICE']
                if event == 'DELETED':
                    if pod_name in service_name_to_task_keys[service_name]:
                        service_name_to_task_keys[service_name].remove(pod_name)
                        if not service_name_to_task_keys[service_name]:
                            msg = f'Service \'{service_name}\' was removed.'
                            self.collector.queue.put({'result': 'succeed', 'stream': msg})
                        target_task_keys.remove(pod_name)
                if not target_task_keys:
                    completed = True
                    break
        except urllib3.exceptions.ReadTimeoutError:
            pass
        if completed:
            msg = "All Services were removed."
            self.collector.queue.put({'result': 'completed', 'stream': msg})
        else:
            for svc, task_keys in service_name_to_task_keys.items():
                if len(task_keys) > 0:
                    msg = f"Failed to remove service {svc}."
                    self.collector.queue.put({'result': 'failed', 'stream': msg})
        self.collector.queue.put({'result': 'stopped'})

    def stop(self):
        self.__stopped = True
        print('Request Stop Delete Monitor')
        if self.stream_resp and self.stream_resp._fp and self.stream_resp._fp.fp:
            try:
                sock = self.stream_resp._fp.fp.raw._sock
                if isinstance(sock, ssl.SSLSocket):
                    sock.shutdown(socket.SHUT_RDWR)
                else:
                    sock.shutdown()
                sock.close()
            except AttributeError as e:
                print(f'Error on Delete Monitor::Stop [{e}]')
            finally:
                self.stream_resp = None


class Collector:
    def __init__(self, maxbuffer=65535):
        self.queue = Queue(maxsize=maxbuffer)

    def __next__(self):
        msg = self.queue.get()
        if 'stream' in msg:
            return msg
        elif 'result' in msg:
            if msg['result'] == 'stopped':
                raise StopIteration
            else:
                return msg

    def __iter__(self):
        return self
