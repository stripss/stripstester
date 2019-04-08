from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import json
import time
import random
import subprocess
import logging
from subprocess import Popen, PIPE
from os import kill
import signal

clients = []

class SimpleChat(WebSocket):
    def handleMessage(self):
        print(self.data)
        data = json.loads(self.data)

        if "shutdown" in data['command']:
            subprocess.Popen("/usr/bin/sudo /sbin/shutdown -h now".split(), stdout=subprocess.PIPE)


    def handleConnected(self):
        print(self.address, 'connected')
        #for client in clients:
        #    client.sendMessage(self.address[0] + u' - connected')
        clients.append(self)

    def handleClose(self):
        clients.remove(self)
        print(self.address, 'closed')
        #for client in clients:
        #    client.sendMessage(self.address[0] + u' - disconnected')


def send(message):
    for client in clients:
        client.sendMessage(json.dumps(message))


def send_spam():
    messages = []
    messages.append({"status": "Merjenje napetosti..."})
    messages.append({"progress": random.randint(0, 100)})
    messages.append({"status": "Odpri pokrov"})
    messages.append({"status": "Merjenje temperature..."})
    messages.append({"status": "Programiranje..."})
    messages.append({"good_count": random.randint(0, 1000)})
    messages.append({"bad_count": random.randint(0, 1000)})
    messages.append({"semafor1": [random.randint(0, 1), random.randint(0, 1), random.randint(0, 1)]})

    while True:
        id = random.randint(0, len(messages) - 1)
        message = json.dumps(messages[id])

        print(message)
        for client in clients:
            client.sendMessage(message)

        time.sleep(0.5)


def start_server():
    server = SimpleWebSocketServer('', 8000, SimpleChat)
    server.serveforever()
