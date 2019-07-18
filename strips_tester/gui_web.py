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
import threading
import datetime
import logging

module_logger = logging.getLogger(".".join(("strips_tester", "gui_web")))

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
            test_device.update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"worker_id": data['worker_id'], "worker_type": data['worker_type'], "worker_comment": data['worker_comment']}})

            strips_tester.data['worker_id'] = data['worker_id']
            strips_tester.data['worker_type'] = data['worker_type']
            strips_tester.data['worker_comment'] = data['worker_comment']

            # Update other GUIs with current worker info (broadcast)
            send({"command": "set_worker_data", "worker_id": data['worker_id'], "worker_type": data['worker_type'], "worker_comment": data['worker_comment']})
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
        sendTo(self, {"command": "set_worker_data", "worker_id": strips_tester.data['worker_id'], "worker_type": strips_tester.data['worker_type'], "worker_comment": strips_tester.data['worker_comment']})

        if custom_parser:
            Parser = getattr(parser, "Parser")
            parser_in = Parser()
            parser_in.welcome(self)  # Parse command depending on test device


    def handleClose(self):
        clients.remove(self)
        print(self.address, 'closed')


def send(message):
    for client in clients:
        client.sendMessage(json.dumps(message))


def sendTo(client, message):
    client.sendMessage(json.dumps(message))

def send_ping():
    # Connect to DB with new temporary client
    # Send date to database. Client on HTTP will calculate duration of last ping received
    connection = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    database = connection["stripstester"]
    date = datetime.datetime.utcnow()

    database['test_device'].update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"status": date}})

    connection.close()
    threading.Timer(5, send_ping).start()

def update_address_info(server):
    addr = server.serversocket.getsockname()

    connection = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    database = connection["stripstester"]

    # Save current port to DB
    database['test_device'].update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"address": addr[1]}})
    connection.close()

    module_logger.info("[StripsTester] WebSocket server started on port {}" . format(addr[1]))

def start_server():
    server = SimpleWebSocketServer('', 8000, SimpleChat)
    update_address_info(server)  # Store address info to DB
    send_ping()  # Signal DB that TN is alive
    server.serveforever()
