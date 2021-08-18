import ssl
import socket
import urllib3
from threading import Thread
from multiprocessing import Queue
from kubernetes import client, config, watch

class DelMonitor(Thread):
    @staticmethod
    def api_wrapper(fn, callback):
        def inner(*args, **kwargs):
            resp = fn(*args, **kwargs)
            callback(resp)
            return resp
        return inner

    def __init__(self,cli, collector, services, namespace, timeout=0xFFFF):
        Thread.__init__(self)
        self.daemon=True
        self.__stopped = False
        self.api = client.CoreV1Api(cli)
        self.collector = collector
        self.service_to_check = services
        self.namespace = namespace
        self.timeout = timeout

        self.stream_resp=None

    def run(self):
        def assign(x):
            self.stream_resp = x

        all_targets=[]
        services={}
        for service in self.service_to_check:
            name, namespace, _, targets = service
            services[name] = targets
            all_targets.extend(targets)
        w = watch.Watch()
        print(f'Watch start to check service removed')
        service_removed = False
        msg = f"Wait to remove services..\n"
        self.collector.queue.put({'stream': msg})
        try:
            wrapped_api = DelMonitor.api_wrapper(self.api.list_namespaced_pod, assign)
            for ev in w.stream(wrapped_api, namespace=self.namespace,
                               _request_timeout=self.timeout):
                event = ev['type']
                pod = ev['object']['metadata']['name']
                service = ev['object']['metadata']['labels']['MLAD.PROJECT.SERVICE']
                if event == 'DELETED':
                    if pod in services[service]:
                        services[service].remove(pod)
                        if not services[service]:
                            msg = f"Service {service} removed."
                            self.collector.queue.put({'result': 'succeed', 'stream': msg})
                        all_targets.remove(pod)
                        if not all_targets:
                            service_removed = True
                            break
        except urllib3.exceptions.ReadTimeoutError as e: #for timeout
            pass
        if service_removed:
            msg = f"All Service removed."
            self.collector.queue.put({'result': 'completed', 'stream': msg})
        else:
            for svc, target in services.items():
                if target:
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
            else: return msg

    def __iter__(self):
        return self