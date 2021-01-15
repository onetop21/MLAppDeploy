import sys
import os
import time
import datetime
import struct
import itertools
import docker
import socket
import urllib3
import requests_unixsocket
from dateutil import parser
from threading import Thread
from multiprocessing import Queue, Value
from mladcli.libs import utils

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

    def logs(self, target, **params):
        config = utils.read_config()
        if config['docker']['host'].startswith('http://') or config['docker']['host'].startswith('https://'):
            host = config['docker']['host'] 
        elif config['docker']['host'].startswith('unix://'):
            host = f"http+{config['docker']['host'][:7]+config['docker']['host'][7:].replace('/', '%2F')}"
        else:
            host = f"http://{config['docker']['host']}"

        timeout = None if params['follow'] else 3
        try:
            with requests_unixsocket.get(f"{host}/v1.24{target}/logs", params=params, timeout=timeout, stream=True) as resp:
                self.responses.append(resp)
                Thread(target=LogHandler._monitor, args=(self.monitoring, host, target, lambda: self.close(resp)), daemon=True).start()
                def iter_lines(resp):
                    #resp.raise_for_status()
                    #except requests.exceptions.HTTPError as e:
                    while True:
                        header = resp.raw.read(docker.constants.STREAM_HEADER_SIZE_BYTES)
                        if not header:
                            break
                        _, length = struct.unpack('>BxxxL', header)
                        if not length:
                            continue
                        data = resp.raw.read(length)   
                        if not data:
                            break
                        yield data
                #for line in resp.iter_lines():
                for line in iter_lines(resp):
                    if params.get('timestamps'):
                        separated = line.split(b' ')
                        line = b' '.join([separated[1], separated[0], *separated[2:]])
                    yield line
            self.responses.remove(resp)
        except urllib3.exceptions.ProtocolError:
            pass
        except urllib3.exceptions.ReadTimeoutError:
            pass

    @classmethod
    def _monitor(cls, should_run, host, target, callback):
        params = {'stderr': True, 'tail': 1}
        while should_run.value:
            status = requests_unixsocket.get(f"{host}/v1.24{target}/logs", params=params, timeout=1).status_code
            if status != 200:
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
            output = {'name': self.threads[object_id]['name'], 'name_width': self.name_width}
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
                output['task_id'] = f"{_[_.rfind('=')+1:]}"
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
