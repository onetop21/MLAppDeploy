import os
import time


if __name__ == '__main__':
    time.sleep(int(os.environ.get('WAIT_TIME')))
    if os.environ.get('FAILED', None) is not None:
        raise Exception
