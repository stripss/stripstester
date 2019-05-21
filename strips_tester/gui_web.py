from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import json
import time
import random
import subprocess
import logging
from subprocess import Popen, PIPE
from os import kill
import os
import signal
import importlib
from config_loader import Settings

clients = []
settings = Settings()

custom_parser = False
try:
    parser = importlib.import_module("configs." + settings.get_setting_file_name() + ".parser")
    custom_parser = True
    print("Custom parser detected.")
except ImportError:
    pass

class SimpleChat(WebSocket):
    def handleMessage(self):
        print(self.data)
        data = json.loads(self.data)

        # Global parsing (all test devices)

        if "shutdown" in data['command']:
            subprocess.Popen("/usr/bin/sudo /sbin/shutdown -h now".split(), stdout=subprocess.PIPE)

        if custom_parser:
            Parser = getattr(parser, "Parser")
            parser_in = Parser(clients)
            answer = parser_in.parse(data)  # Parse command depending on test device

            if answer:
                send({"command": "status", "value": answer})

    def handleConnected(self):
        print(self.address, 'connected')
        #for client in clients:
        #    client.sendMessage(self.address[0] + u' - connected')
        clients.append(self)

        if custom_parser:
            Parser = getattr(parser, "Parser")
            parser_in = Parser(clients)
            parser_in.welcome()  # Parse command depending on test device


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
