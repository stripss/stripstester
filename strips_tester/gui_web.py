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
import http.server
import socketserver
import os
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
        try:
            print(self.data)
            data = json.loads(self.data)

            # Global parsing (all test devices)

            if "shutdown" in data['command']:
                subprocess.Popen("/usr/bin/sudo /sbin/shutdown -h now".split(), stdout=subprocess.PIPE)

            if "reboot" in data['command']:
                subprocess.Popen("/usr/bin/sudo /sbin/reboot".split(), stdout=subprocess.PIPE)

            if "save_worker_data" in data['command']:
                strips_tester.data['worker_id'] = data['worker_id']
                strips_tester.data['worker_type'] = data['worker_type']
                strips_tester.data['worker_comment'] = data['worker_comment']

                # Save worker data to LocalDB
                strips_tester.lock_local_db()  # Locks DB to this operation
                strips_tester.data['db_local_cursor'].execute('''UPDATE test_device SET worker_id = ?, worker_type = ?, worker_comment = ? WHERE name = ?''', (strips_tester.data['worker_id'],strips_tester.data['worker_type'],strips_tester.data['worker_comment'],strips_tester.settings.test_device_name))
                strips_tester.data['db_local_connection'].commit()
                strips_tester.release_local_db()  # Releases DB

                if strips_tester.data['db_connection'] is not None:
                    test_device_col = strips_tester.data['db_database']["test_device"]
                    test_worker_col = strips_tester.data['db_database']["test_worker"]

                    test_device_col.update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"worker_id": data['worker_id'], "worker_type": data['worker_type'], "worker_comment": data['worker_comment']}})

                    try:
                        strips_tester.data['good_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
                        strips_tester.data['bad_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']
                        strips_tester.data['comment_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['comment']

                    except (IndexError, TypeError):  # Pass exceptions if record does not exist in database
                        strips_tester.data['good_custom'] = 0
                        strips_tester.data['bad_custom'] = 0
                        strips_tester.data['comment_custom'] = ""
                else:
                    strips_tester.lock_local_db()  # Locks DB to this operation
                    result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_worker WHERE id = ?''', (strips_tester.data['worker_id'],)).fetchone()

                    if result:
                        strips_tester.data['good_custom'] = result['good']
                        strips_tester.data['bad_custom'] = result['bad']
                        strips_tester.data['comment_custom'] = result['comment']
                    else:
                        strips_tester.data['good_custom'] = 0
                        strips_tester.data['bad_custom'] = 0
                        strips_tester.data['comment_custom'] = ""

                    strips_tester.release_local_db()  # Releases DB

                # Update other GUIs with current worker info (broadcast)
                send({"command": "set_worker_data", "worker_id": data['worker_id'], "worker_type": data['worker_type'], "worker_comment": data['worker_comment']})
                send({"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})

            # Set custom counter data
            if "count_custom" in data['command']:
                strips_tester.data['good_custom'] = data['good_custom']
                strips_tester.data['bad_custom'] = data['bad_custom']
                strips_tester.data['comment_custom'] = data['comment_custom']

                if strips_tester.data['db_connection'] is not None:  # RemoteDB is accessible
                    # Get current worker
                    test_worker_col = strips_tester.data['db_database']["test_worker"]

                    # Set worker custom counter data (if not exist -> insert new column)
                    test_worker_col.update_one({"id": strips_tester.data['worker_id']}, {"$set": {"good": strips_tester.data['good_custom'], "bad": strips_tester.data['bad_custom'], "comment": strips_tester.data['comment_custom']}}, True)

                strips_tester.lock_local_db()  # Locks DB to this operation
                result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_worker WHERE id = ?''', (strips_tester.data['worker_id'],)).fetchone()

                # Update custom counter for worker
                if result:
                    print("worker with id {id} is updated" . format(id=strips_tester.data['worker_id']))
                    strips_tester.data['db_local_cursor'].execute('''UPDATE test_worker SET good = ?, bad = ?, comment = ? WHERE id = ?''', (strips_tester.data['good_custom'],strips_tester.data['bad_custom'],strips_tester.data['comment_custom'],strips_tester.data['worker_id'],))
                    strips_tester.data['db_local_connection'].commit()
                else:
                    print("worker with id {id} is not found yet so we create it" . format(id=strips_tester.data['worker_id']))
                    strips_tester.data['db_local_cursor'].execute('''INSERT INTO test_worker(id, good, bad, comment) VALUES(?,?,?,?)''', (strips_tester.data['worker_id'],strips_tester.data['good_custom'],strips_tester.data['bad_custom'],strips_tester.data['comment_custom'],))
                    strips_tester.data['db_local_connection'].commit()
                strips_tester.release_local_db()  # Releases DB


                # Broadcast new custom counter data
                send({"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})

            if custom_parser:
                Parser = getattr(parser, "Parser")
                parser_in = Parser()
                parser_in.parse(self, data)  # Parse command depending on test device

        except Exception as e:  # Error handle in this thread
            module_logger.error(e)

    def handleConnected(self):
        clients.append(self)

        sendTo(self, {"command": "html", "value": ""})

        try:
            with open(strips_tester.settings.test_dir + '/custom.html', 'r') as custom_html:
                sendTo(self, {"command": "html", "value": custom_html.read()})
        except IOError:  # Do nothing if file does not exist
            pass

        sendTo(self, {"command": "threaded", "value": strips_tester.settings.thread_nests})  # Tell GUI if tester is threaded
        sendTo(self, {"command": "nests", "value": strips_tester.settings.test_device_nests})

        sendTo(self, ({"command": "count", "good_count": strips_tester.data['good_count'], "bad_count": strips_tester.data['bad_count'], "good_count_today": strips_tester.data['good_count_today'],
                       "bad_count_today": strips_tester.data['bad_count_today']}))

        # Update worker info
        sendTo(self, {"command": "set_worker_data", "worker_id": strips_tester.data['worker_id'], "worker_type": strips_tester.data['worker_type'], "worker_comment": strips_tester.data['worker_comment']})

        # Custom counter info
        sendTo(self, {"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})

        try:
            strips_tester.data['first_user']
        except KeyError:
            strips_tester.data['first_user'] = True

            # Raise worker data modal
            sendTo(self, {"command": "confirm_worker_data"})

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
            strips_tester.test_devices_col.update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"status": date}})

        except (pymongo.errors.NetworkTimeout, pymongo.errors.ServerSelectionTimeoutError):
            module_logger.error("Lost connection to RemoteDB - switching to LocalDB")

            strips_tester.data['db_connection'] = None

            # Send notification that TN is working OFFLINE!
            send({"command": "offline"})

    threading.Timer(5, send_ping).start()

# Apply variable to memory so the next time test device turn on, this memory will be applied
def save_variable_to_db(name, value):
    if strips_tester.data['db_connection'] is not None:
        strips_tester.data['db_database']['test_device'].update_one({'name': strips_tester.settings.test_device_name}, {"$set": {'memory.{}' . format(name): value}}, True)

    strips_tester.lock_local_db()  # Locks DB to this operation
    result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_device''').fetchone()

    # Update global variable with last remote counters
    if result:
        memory = json.loads(result['memory'])
        memory[name] = value

        strips_tester.data['db_local_cursor'].execute('''UPDATE test_device SET memory = ?''',(str(json.dumps(memory)),))
        strips_tester.data['db_local_connection'].commit()

    strips_tester.release_local_db()  # Releases DB

    return

def get_ip_address():
    return subprocess.check_output(['hostname', '--all-ip-addresses']).decode()[:-2]

def update_address_info(server):
    port = server.serversocket.getsockname()[1]
    ip_address = "{}:{}" . format(get_ip_address(), port)

    if strips_tester.data['db_connection'] is not None:
        # Save current port to DB
        strips_tester.test_devices_col.update_one({"name": strips_tester.settings.test_device_name}, {"$set": {"address": ip_address}})

    module_logger.info("[StripsTester] WebSocket server started on {}" . format(ip_address))

def start_server(port):
    server = SimpleWebSocketServer('', port, SimpleChat)

    update_address_info(server)  # Store address info to DB
    send_ping()  # Signal DB that TN is alive
    server.serveforever()

class MyTCPServer(socketserver.TCPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

class HTTPServerHandler(http.server.SimpleHTTPRequestHandler):
    ROUTES = [
        ('/', 'index_local.html')
    ]

    # We like silence
    def log_message(self, format, *args):
        return

    def translate_path(self, path):
        # look up routes and get root directory
        for patt, rootDir in HTTPServerHandler.ROUTES:
            if path.startswith(patt):
                path = path[len(patt):]

                break

        # new path
        return "/strips_tester_project/StripsTester WEB/public/" + path

# HTTP Server serves as GUI backup if main GUI is not available due to connection lost
def start_http_server(port):
    http_server = MyTCPServer(('127.0.0.1', port), HTTPServerHandler)
    module_logger.info("[StripsTester] HTTP server started on port {}" . format(port))
    http_server.serve_forever()