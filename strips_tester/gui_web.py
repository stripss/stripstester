from SimpleWebSocketServer import SimpleWebSocketServer, WebSocket
import json
import time
import random
import subprocess
import importlib
from config_loader import Settings
import strips_tester
import pymongo
from bson import json_util

clients = []
settings = Settings()

custom_parser = False
try:
    parser = importlib.import_module("configs." + settings.get_setting_file_name() + ".parser")
    custom_parser = True
    # print("Custom parser detected.")
except ImportError:
    pass


class SimpleChat(WebSocket):
    def handleMessage(self):
        print(self.data)
        data = json.loads(self.data)

        # Global parsing (all test devices)

        if "shutdown" in data['command']:
            subprocess.Popen("/usr/bin/sudo /sbin/shutdown -h now".split(), stdout=subprocess.PIPE)

        if "reboot" in data['command']:
            subprocess.Popen("/usr/bin/sudo /sbin/reboot".split(), stdout=subprocess.PIPE)

        if "save_worker_data" in data['command']:
            # Connect to DB with new temporary client
            connection = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
            database = connection["stripstester"]

            test_device = database['test_device']
            test_device.update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"worker_id": data['worker_id'], "worker_type": data['worker_type']}})

            strips_tester.data['worker_id'] = data['worker_id']
            strips_tester.data['worker_type'] = data['worker_type']

            # Update other GUIs with current worker info (broadcast)
            send({"command": "set_worker_data", "worker_id": data['worker_id'], "worker_type": data['worker_type']})
            connection.close()  # Close pymongo connection

        if custom_parser:
            Parser = getattr(parser, "Parser")
            parser_in = Parser()
            parser_in.parse(self, data)  # Parse command depending on test device


    def handleConnected(self):
        clients.append(self)

        # Send custom HTML page based on GO-C19 page, if exists
        sendTo(self, {"command": "html", "value": ""})

        try:
            with open(strips_tester.settings.test_dir + '/custom.html', 'r') as custom_html:
                sendTo(self, {"command": "html", "value": custom_html.read()})
        except IOError:
            pass

        sendTo(self, {"command": "threaded", "value": strips_tester.settings.thread_nests})  # Tell GUI if tester is threaded
        sendTo(self, {"command": "nests", "value": strips_tester.data['test_device_nests']})

        sendTo(self, ({"command": "count", "good_count": strips_tester.data['good_count'], "bad_count": strips_tester.data['bad_count'], "good_count_today": strips_tester.data['good_count_today'],
                       "bad_count_today": strips_tester.data['bad_count_today']}))

        # Update worker info
        sendTo(self, {"command": "set_worker_data", "worker_id": strips_tester.data['worker_id'], "worker_type": strips_tester.data['worker_type']})

        if custom_parser:
            Parser = getattr(parser, "Parser")
            parser_in = Parser()
            parser_in.welcome(self)  # Parse command depending on test device


    def handleClose(self):
        clients.remove(self)
        print(self.address, 'closed')


class PingServer(WebSocket):
    def handleMessage(self):
        pass

    def handleConnected(self):
        pass

    def handleClose(self):
        pass


def send(message):
    for client in clients:
        client.sendMessage(json.dumps(message))


def sendTo(client, message):
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


def start_pingserver():
    print("Ping server started on port 8001")
    ping_server = SimpleWebSocketServer('', 8001, SimpleChat)
    ping_server.serveforever()
