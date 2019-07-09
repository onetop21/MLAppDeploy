import sys, os, time, itertools, threading

NoColor = '\x1b[0m'
Colors = []
for bg in range(40, 48):
    for fg in range(30, 38):
        if fg % 10 == bg % 10: continue
        color = ';'.join(['1', str(fg), str(bg)])
        Colors.append('\x1b[%sm' % color)

_counter = itertools.count()
def colorIndex():
    return next(_counter) % len(Colors)

class LoggerThread(threading.Thread):

    def __init__(self, name, width, log, detail=False, short_len=10):
        threading.Thread.__init__(self)
        self.name = name if len(name) <= width else (name[:width-3] + '...')
        self.width = width
        self.log = log
        self.detail=detail
        self.short_len = short_len
        self.color = Colors[colorIndex()]
        self.interrupted = False
        self.daemon = True

    def run(self):
        while not self.interrupted:
            try:
                name = self.name
                msg = next(self.log).decode('utf8')[:-1] # Remove line feed
                if self.detail: 
                    _, msg = msg.split(' ', 1)
                    name += '.{}'.format(_[_.rfind('=')+1:][:self.short_len])
                print(('%s{NAME:%d}%s {LOG}' % (self.color, self.width, NoColor)).format(NAME=name, LOG=msg))
            except StopIteration as e:
                self.interrupt()
            time.sleep(0.001)

    def interrupt(self):
        self.interrupted = True

sys.modules[__name__] = LoggerThread
