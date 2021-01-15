import sys, os, signal

class InterruptHandler(object):
    def __init__(self, message='Aborted.', blocked=False, sig=signal.SIGINT):
        self.message = message
        self.sig = sig
        self.blocked = blocked

    def __enter__(self):
        self.interrupted = False
        self.released = False
        self.original_handler = signal.getsignal(self.sig)
        def handler(signum, frmae):
            if not self.blocked:
                self.release(True)
            self.interrupted = True
            print(self.message, file=sys.stderr)
        signal.signal(self.sig, handler)
        return self

    def __exit__(self, type, value, tb):
        return self.release()

    def release(self, interrupted=False):
        if self.released:
            return True
        signal.signal(self.sig, self.original_handler)
        self.released = True
        if interrupted: raise KeyboardInterrupt
        return False

sys.modules[__name__] = InterruptHandler
