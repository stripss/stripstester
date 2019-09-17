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
import socket

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
            test_device_col = strips_tester.data['db_database']["test_device"]
            test_worker_col = strips_tester.data['db_database']["test_worker"]
            test_device_col.update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"worker_id": data['worker_id'], "worker_type": data['worker_type'], "worker_comment": data['worker_comment']}})

            strips_tester.data['worker_id'] = data['worker_id']
            strips_tester.data['worker_type'] = data['worker_type']
            strips_tester.data['worker_comment'] = data['worker_comment']

            # Update other GUIs with current worker info (broadcast)
            send({"command": "set_worker_data", "worker_id": data['worker_id'], "worker_type": data['worker_type'], "worker_comment": data['worker_comment']})

            try:
                strips_tester.data['good_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
                strips_tester.data['bad_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']
                strips_tester.data['comment_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['comment']

            except Exception as e:  # Pass exceptions if record does not exist in database
                strips_tester.data['good_custom'] = 0
                strips_tester.data['bad_custom'] = 0
                strips_tester.data['comment_custom'] = ""

            send({"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})

        if "count_custom" in data['command']:
            # Get current worker
            test_worker_col = strips_tester.data['db_database']["test_worker"]

            # Reset worker custom counter data
            test_worker_col.update_one({"id": strips_tester.data['worker_id']}, {"$set": {"good": data['good_custom'], "bad": data['bad_custom'], "comment": data['comment_custom']}}, True)

            try:
                # Get latest info from DB
                strips_tester.data['good_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
                strips_tester.data['bad_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']
                strips_tester.data['comment_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['comment']

            except Exception:
                pass

            # Broadcast new data
            send({"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})



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
        sendTo(self, {"command": "nests", "value": strips_tester.settings.test_device_nests})

        sendTo(self, ({"command": "count", "good_count": strips_tester.data['good_count'], "bad_count": strips_tester.data['bad_count'], "good_count_today": strips_tester.data['good_count_today'],
                       "bad_count_today": strips_tester.data['bad_count_today']}))

        # Update worker info
        sendTo(self, {"command": "set_worker_data", "worker_id": strips_tester.data['worker_id'], "worker_type": strips_tester.data['worker_type'], "worker_comment": strips_tester.data['worker_comment']})

        # Custom counter info
        sendTo(self, {"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})

        if custom_parser:
            Parser = getattr(parser, "Parser")
            parser_in = Parser()
            parser_in.welcome(self)  # Parse command depending on test device

    def handleClose(self):
        clients.remove(self)


def send(message):
    for client in clients:
        client.sendMessage(json.dumps(message))


def sendTo(client, message):
    client.sendMessage(json.dumps(message))

def send_ping():
    # Send date to database. Client on HTTP will calculate duration of last ping received
    date = datetime.datetime.utcnow()

    if strips_tester.data['db_connection'] is not None:
        try:
            strips_tester.data['db_database']['test_device'].update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"status": date}})

        except pymongo.errors.NetworkTimeout:
            module_logger.error("Lost connection to DB, switching to Local DB")

            strips_tester.data['db_connection'] = None

            # Send notification that TN is working OFFLINE!
            send({"command": "offline", "value": "127.0.0.1"})

    threading.Timer(5, send_ping).start()


def get_ip_address():
    #s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #s.connect(("8.8.8.8", 80))  # Connect to Google DNS
    #ip = s.getsockname()[0]
    ip = subprocess.check_output(['hostname', '--all-ip-addresses']).decode()[:-2]

    return ip

def update_address_info(server):
    port = server.serversocket.getsockname()[1]
    ip_address = "{}:{}" . format(get_ip_address(), port)

    if strips_tester.data['db_connection'] is not None:
        # Save current port to DB
        strips_tester.data['db_database']['test_device'].update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"address": ip_address}})

    module_logger.info("[StripsTester] WebSocket server started on {}" . format(ip_address))

def start_server():
    server = SimpleWebSocketServer('', 0, SimpleChat)

    update_address_info(server)  # Store address info to DB
    send_ping()  # Signal DB that TN is alive
    server.serveforever()
