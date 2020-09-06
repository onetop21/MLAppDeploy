import sys
import os
import socket
import zmq
import time

context = zmq.Context()
sock = context.socket(zmq.DEALER)
sock.setsockopt(zmq.IDENTITY, socket.gethostname().encode())
sock.connect('tcp://server:5555')
index = 0
print('Client Ready v0.0.3')
while True:
   sock.send_string(f'Index: {index}')
   index += 1
   print(sock.recv_string())
   time.sleep(1)
    
