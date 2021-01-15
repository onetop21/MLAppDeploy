import sys
import os
import time
import datetime
import itertools
import requests_unixsocket
from dateutil import parser
from threading import Thread

def logs(target, **params):
    if config['docker']['host'].startswith('http://') or config['docker']['host'].startswith('https://'):
        host = config['docker']['host'] 
    elif config['docker']['host'].startswith('unix://'):
        host = f"http+{config['docker']['host'][:7]+config['docker']['host'][7:].replace('/', '%2F')}"
    else:
        host = f"http://{config['docker']['host']}"

    with requests_unixsocket.get(f"{host}/v1.24{target}/logs", params=params, stream=True) as resp:
        def get_line(resp):
            import struct
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError as e:
                raise create_api_error_from_http_exception(e)
            while True:
                try:
                    print("Start")
                    header = resp.raw.read(docker.constants.STREAM_HEADER_SIZE_BYTES)
                    if not header:
                        break
                    _, length = struct.unpack('>BxxxL', header)
                    print(_, length, header)
                    if not length:
                        continue
                    data = resp.raw.read(length)
                    if not data:
                        break
                    print('Data', data)
                    yield data
                #except StopIteration:
                #    pass
                #except requests.exceptions.StreamConsumedError:
                #    pass
                except Exception as e:
                    print("Exception", type(e), e)
                    break
        #for line in resp.iter_lines():
        for line in get_line(resp):
            out = line[docker.constants.STREAM_HEADER_SIZE_BYTES:].decode('utf8')
            if out:
                if timestamps:
                    temp = f"{out} ".split(' ') # Add space at end to prevent error without body
                    out = ' '.join([temp[1], temp[0]] + temp[2:])
                out = out.strip() + '\n'
            yield out.encode()
        print("??")

class LogCollector(): 
    def __init__(self, maxbuffer=1000):
        self.threads = {}
        self.queue = Queue(maxsize=maxbuffer)
        self.should_run = Value('b', True)

    def __next__(self):
        msg = self.queue.get()
        object_id = msg['object_id']
        if 'stream' in msg:
            stream = msg['stream'].decode()
            output = {'name': self.threads[object_id]['name']}
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
                output['task_id'] = f"{_[_.rfind('=')+1:][:SHORT_LEN]}"
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
        else: raise RuntimeError('Invalid stream type.')

    def __iter__(self):
        return self

    def __enter__(self):
        self.should_run.value = True
        return self

    def __exit__(self, ty, val, tb):
        self.release()
        if ty == KeyboardInterrupt:
            return True
        else:
            import traceback
            traceback.print_exception(ty, val, tb)
            return False

    def add_iterable(self, iterable, name=None, timestamps=False):
        self.threads[id(iterable)] = {
            'name': name, 
            'timestamps': timestamps,
            'from_dockerpy': isinstance(iterable, docker.types.daemon.CancellableStream),
            'thread': Thread(target=LogCollector._read_stream, args=(iterable, self.queue, self.should_run), daemon=True)
        }
        self.threads[id(iterable)]['thread'].start()

    def release(self):
        self.should_run.value = False
        for _ in self.threads.values():
            _['thread'].join()
        #print('Released Collector.', file=sys.stderr)

    def _read_stream(iterable, queue, should_run):
        for _ in iterable:
            if not should_run.value: break
            if _: queue.put({'stream': _, 'object_id': id(iterable)})
        queue.put({'status': 'stopped', 'object_id': id(iterable)})
        #print('Stream Thread is Down.', file=sys.stderr)
