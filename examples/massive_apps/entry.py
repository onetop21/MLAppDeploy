import time
import random


if __name__ == '__main__':

    start_time = time.time()
    for _ in range(1000):
        interval = random.randint(0, 3)
        time.sleep(interval)
        print(f'Elapsed time: {time.time() - start_time:.2f}')
