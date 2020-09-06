import sys
import os
import datetime
import socket
import zmq

context = zmq.Context()
sock = context.socket(zmq.ROUTER)
sock.bind('tcp://*:5555')
print('Server Ready')
while True:
   client = sock.recv_string()
   data = sock.recv_string()
   current_time = datetime.datetime.now()
   print(f'[{current_time}] Received Data : {data} / From : {client}')
   sock.send(client.encode(), zmq.SNDMORE)
   sock.send_string(f'Message Received. [{socket.gethostname()} - {current_time}]')
    
