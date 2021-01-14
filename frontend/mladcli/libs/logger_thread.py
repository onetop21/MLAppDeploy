import sys
import os
import time
import datetime
import itertools
import threading
from dateutil import parser

NoColor = '\x1b[0m'
ErrColor = '\x1b[1;31;40m'
Colors = []
for bg in range(40, 48):
    for fg in range(30, 38):
        if fg % 10 == 1: continue # Remove Red Foreground
        if fg % 10 == bg % 10: continue
        color = ';'.join(['1', str(fg), str(bg)])
        Colors.append(f'\x1b[{color}m')

_counter = itertools.count()
def colorIndex():
    return next(_counter) % len(Colors)

class LoggerThread(threading.Thread):
    def __init__(self, name, width, log, detail=False, timestamps=False, short_len=10, queue=None):
        threading.Thread.__init__(self)
        self.name = name if len(name) <= width else (name[:width-3] + '...')
        self.width = width
        self.log = log
        self.detail = detail
        self.timestamps = timestamps
        self.short_len = short_len
        self.colorkey = {}
        self.queue = queue
        self.interrupted = False
        self.daemon = True

    def run(self):
        while not self.interrupted:
            try:
                name = self.name
                msg = next(self.log).decode('utf8')
                if msg.startswith('Error'):
                    print(f'{ErrColor}{msg}{NoColor}')
                else:
                    if self.detail: 
                        # Logs from Docker REST API
                        if self.timestamps:
                            split_msg = msg.split(' ', 2)
                            if len(split_msg) < 3: _, timestamp, body = (*split_msg, '')
                            else: _, timestamp, body = split_msg
                            #msg = ' '.join([parser.parse(timestamp).astimezone().isoformat(), msg])
                            body = ' '.join([parser.parse(timestamp).astimezone().strftime("[%Y-%m-%d %H:%M:%S.%f]"), body])
                        else:
                            split_msg = msg.split(' ', 1)
                            if len(split_msg) < 2: _, body = (*split_msg, '')
                            else: _, body = split_msg
                        name += f".{_[_.rfind('=')+1:][:self.short_len]}"
                    else:
                        # Logs from Docker Py
                        split_msg = msg.strip('\r\n').split(' ', 1)
                        if len(split_msg) < 2: _, body = (*split_msg, '')
                        else: _, body = split_msg

                    self.colorkey[name] = self.colorkey[name] if name in self.colorkey else Colors[colorIndex()]
                    output = ("{}{:%d}{} {}" % self.width).format(self.colorkey[name], name, NoColor, body)
                    if self.queue:
                        try:
                            self.queue.put({"stream": f"{output}\n"})
                        except BrokenPipeError:
                            pass
                    else:
                        print(output)
            except StopIteration as e:
                self.interrupt()
        if self.queue:
            try:
                self.queue.put({"status": "interrupted"})
            except BrokenPipeError:
                pass

    def interrupt(self):
        self.interrupted = True

sys.modules[__name__] = LoggerThread
