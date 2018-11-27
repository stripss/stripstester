## !/usr/bin/env python3
## -*- coding: utf-8 -*-
#


from web_project.web_app.models import *
from django.db import transaction

from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor
import json
from collections import OrderedDict
import datetime
from dateutil import parser
import pytz
import os

class GUI(LineReceiver):
    def __init__(self, factory):
        self.factory = factory
        self.server = self.factory.server
        self.test_device = self.factory.server.test_device
        self.users = self.factory.users

        self.id = None
        self.test_type = None

    def connectionMade(self):
        print("connection incoming")
        # self.factory was set by the factory's default buildProtocol:

    def connectionLost(self, reason):
        if self.id in self.users:
            if self.id == self.test_device.master_test_id:
                self.test_device.master_test_id = None  # Find new master id
                self.test_device.master_test_type = None

            if self.test_device.maintenance == self.id:  # Check if disconnected ID had maintenance
                self.test_device.maintenance = None
                self.send_broadcast({"command": "maintenance", "status": "dropped"})
                self.send_broadcast({"command": "text", "text": "Način vzdrževanja testne naprave končan. Lahko nadaljujete testiranje.\n", "tag": "yellow"})

                # Send old task result status
                self.send_broadcast({"command": "task_result", "result": "idle"})

            # Delete user data
            del self.users[self.id]
        print("Connection with ID {} lost: {}" . format(self.id, reason))

        if not len(self.users):
            self.test_device.status = self.test_device.STATUS_NO_CLIENTS
        else:
            # Retrieve new master id and test type (last on list)
            # Print that new master must be selected
            # Show button on TesterPage
            # Who clicks it first, gets the master

            self.test_device.master_test_id = None
            self.test_device.master_test_type = None

            self.send_broadcast({"command": "text", "text": "Glavni delavec se je izpisal. Če začnete testirati, boste prevzeli testno napravo.\n", "tag": "yellow"})

    def send(self, message):
        print("SEND: {}" . format(message))
        self.sendLine(json.dumps(message).encode())

    def send_broadcast(self, message):
        return self.factory.send_broadcast(message)

    def send_broadcast_ex(self, ex_user, message):
        return self.factory.send_broadcast_ex(ex_user, message)

    def lineReceived(self, line):
        message = json.loads(line.decode())
        print("RECIEVED: {}" . format(message))

        command = message['command']

        # GUI greets the server
        if command == "welcome":
            id = message['id']

            if id in self.users:
                # ID already exists, return disconnect
                self.send({"command": "user_exists"})
                print("User exists")
                self.transport.loseConnection()
            else:
                self.id = id
                self.test_type = message['test_type']

                self.users[self.id] = self  # Link this instance to user id

                count_query = TestDevice_Test.objects.using(self.test_device.db).filter(test_device_id=self.test_device.id, datetime__gte=self.test_device.countdate).values('id')
                count_good = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok=0).count()
                count_bad = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok__gt=0).count()

                count_query = TestDevice_Test.objects.using(self.test_device.db).filter(test_device_id=self.test_device.id, datetime__gte=self.test_device.countdate, employee=self.id).values('id')

                user_count_good = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok=0).count()
                user_count_bad = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok__gt=0).count()

                if self.test_device.status == self.test_device.STATUS_NO_CLIENTS:
                    self.test_device.status = self.test_device.STATUS_IDLE

                    self.test_device.master_test_id = self.id
                    self.test_device.master_test_type = self.test_type

                if self.test_device.master_test_id is None:
                    self.test_device.master_test_id = self.id
                    self.test_device.master_test_type = self.test_type

                    self.send_broadcast({"command": "text", "text": "Delavec '{}' je prevzel vlogo glavnega delavca.\n" . format(self.id), "tag": "yellow"})

                self.send({"command": "welcome"})  # Greet new GUI
                self.send({"command": "text", "text": "Pozdravljen uporabnik {}!\n" . format(self.id), "tag": "black"})

                # Send custom tasks to GUI
                self.send({"command": "tasks", "tasks": self.test_device.settings.task_execution_order})
                self.send({"command": "service", "data": self.test_device.service})
                self.send({"command": "calibration", "date": self.test_device.calibrationdate.isoformat()})
                self.send({"command": "count", "date": self.test_device.countdate.isoformat(), "good": user_count_good, "bad": user_count_bad, "good_global": count_good, "bad_global": count_bad})

                self.send({"command": "task_result", "result": self.test_device.result})

                if self.test_device.start_test is not None:
                    self.send({"command": "test_time", "start_test": self.test_device.start_test.isoformat(), "end_test": self.test_device.end_test})
                elif self.test_device.end_test is not None:
                    self.send({"command": "test_time", "start_test": self.test_device.start_test, "end_test": self.test_device.end_test.isoformat()})
                else:
                    self.send({"command": "test_time", "start_test": self.test_device.start_test, "end_test": self.test_device.end_test})

                if self.test_device.maintenance is not None:
                    self.send({"command": "maintenance", "status": "taken", "id": self.id})  # Tell new client maintenance status

        elif command == "text":  # What to do with text?
            pass

        elif command == "maintenance":
            status = message['status']

            if status == "request":  # User requests maintenance
                if self.test_device.maintenance is None:
                    self.test_device.maintenance = self.id  # Link user ID to maintenance

                    self.send({"command": "maintenance", "status": "ok"})  # Accept maintenance
                    self.send_broadcast({"command": "maintenance", "status": "taken", "id": self.id})  # Broadcast maintenance
                    self.send_broadcast({"command": "text", "text": "Poteka način vzdrževanja testne naprave. Trenutno ni mogoče testirati.\n", "tag": "yellow"})

                else:
                    self.send({"command": "maintenance", "status": "occupied", "id": self.test_device.maintenance})  # Refuse maintenance

            elif status == "drop":
                self.test_device.maintenance = None  # Maintenance not linked to any user
                self.send_broadcast({"command": "maintenance", "status": "dropped"})
                self.send_broadcast({"command": "text", "text": "Način vzdrževanja testne naprave končan. Lahko nadaljujete testiranje.\n", "tag": "yellow"})

                # Send old task result status
                self.send_broadcast({"command": "task_result", "result": "idle"})

        elif command == "count":
            self.test_device.countdate = parser.parse(message['date'])  # Parse datetime string to datetime
            TestDevice.objects.using(self.test_device.db).filter(id=self.test_device.id).update(countdate=self.test_device.countdate)

            count_query = TestDevice_Test.objects.using(self.test_device.db).filter(test_device_id=self.test_device.id, datetime__gte=self.test_device.countdate).values('id')
            count_good = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok=0).count()
            count_bad = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok__gt=0).count()

            # Send count info for each client
            for user in self.users:
                count_query = TestDevice_Test.objects.using(self.test_device.db).filter(test_device_id=self.test_device.id, datetime__gte=self.test_device.countdate, employee=self.users[user].id).values('id')

                user_count_good = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok=0).count()
                user_count_bad = TestDevice_Product.objects.using(self.test_device.db).filter(test_id__in=count_query, ok__gt=0).count()

                try:
                    # Send count to each user connected
                    self.users[user].send({"command": "count", "date": self.test_device.countdate.isoformat(), "good": user_count_good, "bad": user_count_bad, "good_global": count_good, "bad_global": count_bad})
                except KeyError:
                    pass  # Pass error if client disconnects right here

        elif command == "service":
            self.test_device.service = message['data']

            # Update test device DB
            TestDevice.objects.using(self.test_device.db).filter(id=self.test_device.id).update(service=self.test_device.service)

            # Broadcast new date to all clients
            self.send_broadcast({"command": "service", "data": self.test_device.service})

        elif command == "calibration":
            self.test_device.calibrationdate = parser.parse(message['date'])  # Parse datetime string to datetime

            # Update test device DB
            TestDevice.objects.using(self.test_device.db).filter(id=self.test_device.id).update(calibrationdate=self.test_device.calibrationdate)

            # Broadcast new date to all clients
            self.send_broadcast({"command": "calibration", "date": self.test_device.calibrationdate.isoformat()})

        elif command == "factory_reset":
            # Perform factory reset.. delete config_custom.json file
            try:
                os.remove(self.test_device.settings.custom_config_file)

                self.send({"command": "factory_reset", "status": "ok"})
            except OSError:
                self.send({"command": "factory_reset", "status": "fail"})

            # Reload tasks if test is not running
            if self.test_device.status != self.test_device.STATUS_START:
                self.test_device.settings.reload_tasks(self.test_device.settings.config_file, self.test_device.settings.custom_config_file)

                print("reloading tasks")
                '''
                for task_name in self.test_device.settings.task_execution_order:
                    server.send_broadcast({"task_update": {"task_slug": task_name, "task_enable": settings.task_execution_order[task_name]['enable']}})
                '''

        elif command == "tasks":
            # Server recieves updated tasks from GUI

            # Recreate server-like tasks

            # Broadcast updated tasks to clients
            self.send_broadcast({"command": "tasks", "tasks": self.task_execution_order})

        elif command == "start_test":
            if self.test_device.status == self.test_device.STATUS_START: # Test device working
                self.send({"command": "text", "text": "Test se že izvaja.\n", "tag": "red"})
            else:
                if self.test_device.maintenance is not None:
                    self.send({"command": "text", "text": "Naprava je v vzdrževalnem načinu.\n", "tag": "yellow"})
                else:
                    self.test_device.test_id = self.id
                    self.test_device.test_type = self.test_type

                    if self.test_device.master_test_id is None:
                        self.test_device.master_test_id = self.id
                        self.test_device.master_test_type = self.test_type

                        self.send_broadcast({"command": "text", "text": "Delavec '{}' je prevzel vlogo glavnega delavca.\n" . format(self.id), "tag": "yellow"})

                    self.test_device.status = self.test_device.STATUS_START

        else:  # Server does not recognize this command
            print("Unknown command.")


class GUIFactory(Factory):
    def __init__(self, server):
        self.users = {}  # maps user names to Chat instances
        self.server = server

    def buildProtocol(self, addr):
        print(self.users)
        return GUI(self)

    def startFactory(self):
        print("Server GUI ready")

    def send_broadcast(self, message):
        print("SEND BROADCAST: {}" . format(message))
        for user in self.users:
            try:
                self.users[user].sendLine(json.dumps(message).encode())
            except KeyError:
                pass

    def send_broadcast_ex(self, ex_user, message):
        for user in self.users:
            if ex_user != self.users[user]:
                self.users[user].sendLine(json.dumps(message).encode())

class Server:
    def __init__(self, test_device_handler):
        self.test_device = test_device_handler
        self.factory = GUIFactory(self)

    def start(self):
        endpoint = TCP4ServerEndpoint(reactor, 8888)
        endpoint.listen(self.factory)

        reactor.run(installSignalHandlers=False)

    # Redirect broadcast to factory
    def send_broadcast(self, message):
        return self.factory.send_broadcast(message)

    # Redirect broadcast_ex to factory
    def send_broadcast_ex(self, ex_user, message):
        return self.factory.send_broadcast(ex_user, message)


'''


import socket
import json
import time
import threading
import multiprocessing
import os
from collections import OrderedDict
import datetime
import subprocess

if __name__ != "__main__":
    import struct
    import importlib
    import strips_tester


class Server():
    # ServerData

    def __init__(self):
        self.send_queue = multiprocessing.Queue(0)
        self.startt = False
        self.afterlock = 0
        self.export = -1

        self.master = False
        self.master_id = -1
        self.master_test_type = 0
        self.clientdata = {}
        self.num_of_clients = 0
        self.clients_connected = 0
        self.maintenance = -1
        self.test_user_id = -1
        self.test_user_type = -1
        self.DB = strips_tester.check_db_connection()

        self.test_device_id = strips_tester.TestDevice.objects.using(strips_tester.DB).get(name=strips_tester.settings.test_device_name).id

        self.result = "idle"
        self.start_test = 0
        self.end_test = 0
            
    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)

        # Setup TCP socket
        try:
            self.server.bind(("0.0.0.0", 80)) # Server always established on test device so it is localhost fixed
            self.server.listen(5)

            #print("TCP Recieve thread started!")
            self.recieve_thread = threading.Thread(target=self.connection_handler)
            self.recieve_thread.setDaemon(True)
            self.recieve_thread.start()

            #print("TCP Send thread started!")
            self.send_thread = threading.Thread(target=self.send_process)
            self.send_thread.setDaemon(True)
            self.send_thread.start()

            print("TCP Server started!")

        except Exception as error:
            print(error)

    def send(self,client_number,data):
        # Add message to queue so it won't interfere with other threads
        msg = {}
        msg['client'] = client_number
        msg['data'] = data

        self.send_queue.put(msg)


    def send_broadcast(self,data):
        for client_number in range(self.num_of_clients):
            if self.clientdata[client_number]['connected']:
                self.send(client_number,data)



    def recieve_process(self,client_number): # Recieve data from each GUI
        id = 0

        while self.clientdata[client_number]['run']:
            #print("Thread with id: {} is talking...".format(id))

            try:
                data = self.recv_one_message(client_number)

                if data: #data detected
                    #print(data)
                    msg = json.loads(data.decode())

                    if "welcome" in msg:  # GUI connected, introducing itself
                        # server return if client is master or not
                        id = msg['welcome']['id']


                        # Store info of current user
                        self.clientdata[client_number]['id'] = id
                        self.clientdata[client_number]['test_type'] = msg['welcome']['test_type']

                        # Check if existing id_num exists
                        for client_number1 in range(self.num_of_clients):
                            if client_number1 != client_number and self.clientdata[client_number1]['connected']:
                                if self.clientdata[client_number1]['id'] == id:
                                    self.send(client_number,{'tester_init': {'id': -1}}) # send -1 if client must shut down due to existion

                                    print("Close GUI: duplicate - GUI must send close message")


                        if self.master == False:
                            print("New master client GUI detected, ID: {}".format(id))

                            self.master = True
                            self.master_id = id  # Assign new master of test device
                        else:  # Master client exist
                            print("New client GUI detected, ID: {}".format(id))

                        self.send(client_number, {'tester_init': {'id': self.master_id}})
                        self.send(client_number, {'maintenance': self.maintenance})

                        for task_name, values in strips_tester.settings.task_execution_order.items():
                            if "name" not in values:
                                pass

                            if "desc" not in values:
                                values['desc'] = "unknown"

                            if "enable" not in values:
                                values['enable'] = 1

                            self.send(client_number,{"task": {"task_name": values['name'], "task_state": "idle", "task_description": values['desc'], "task_enable": values['enable'], "task_slug": task_name, "task_info": ""}})

                            for keys2 in values:
                                if keys2 == 'definition':
                                    for p in values['definition']:
                                        for i in p:
                                            if "name" not in p:
                                                pass

                                            if "extra_info" not in p:
                                                extra_info = ""
                                            else:
                                                extra_info = p['extra_info']

                                        self.send(client_number, {"definition": {"definition_task": task_name, "definition_name": p['name'], "definition_slug": p['slug'], "definition_desc": p['desc'], "definition_value": p['value'], "definition_unit": p['unit'], "definition_extra_info": extra_info}})

                        ''
                        if len(extra_info_buffer):  # If buffer is not empty
                            for i in extra_info_buffer:
                                start_pos = i.find("D[")

                                if start_pos != -1:
                                    end_pos = i.find("]",start_pos)

                                    if end_pos != -1:
                                        temp_slug = settings.get_definition(i[start_pos,end_pos])


                            self.send(client_number, {"extra_info": extra_info_buffer})
                        ''

                        query = strips_tester.TestDevice.objects.using(strips_tester.DB).get(name=strips_tester.settings.test_device_name)

                        # Send statistics to newly connected user

                        # Get all tests with this TN
                        count_query = strips_tester.TestDevice_Test.objects.using(strips_tester.DB).filter(test_device_id=query.id, datetime__gte=query.countdate)

                        good = 0
                        bad = 0
                        for current_test in count_query:
                            # Send statistics information
                            good = good + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok=0).count()
                            bad = bad + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok__gt=0).count()

                        count_query_user = count_query.filter(employee=id)

                        user_good = 0
                        user_bad = 0
                        for current_test in count_query_user:
                            # Send statistics information
                            user_good = user_good + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok=0).count()
                            user_bad = user_bad + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok__gt=0).count()

                        self.send(client_number,{"count": {"good": user_good, "bad": user_bad,"good_global": good, "bad_global": bad, "countdate": query.countdate}})
                        self.send(client_number,{"calibration": query.calibrationdate})
                        self.send(client_number,{"path_manual": query.manual})
                        self.send(client_number,{"service": query.service})
                        self.send(client_number,{"task_result": self.result})
                        self.send(client_number,{'esd': True})
                        self.send(client_number,{'high_voltage': True})

                        if self.startt:
                            self.send(client_number,{"test_time": {"start_test": self.start_test}})  # If test has already begun
                        else:
                            if self.start_test:
                                self.send(client_number, {"test_time": {"start_test": self.start_test, "end_test": self.end_test}})  # If test has already begun

                    if "close" in msg:
                        print("Close GUI: normal")
                        self.close_gui(client_number)

                    if "stop_test_device" in msg:
                        if self.startt:
                            self.send(client_number,{"text": {"text": "[StripsTester] Not implemented yet (will be in v1.3).\n", "tag": "grey"}})
                        else:
                            self.send(client_number,{"text": {"text": "Test se še ni začel.\n", "tag": "red"}})

                    if "start_test_device" in msg:
                        if self.startt:
                            self.send(client_number,{"text": {"text": "Test se že izvaja.\n", "tag": "red"}})
                        else:
                            if self.maintenance == -1:
                                self.startt = True

                                # Assign which user is making a test
                                self.test_user_id = self.clientdata[client_number]['id']
                                self.test_user_type = self.clientdata[client_number]['test_type']
                            else:
                                self.send(client_number,{"text": {"text": "Naprava je v vzdrževalnem načinu.\n", "tag": "yellow"}})


                    if "task_update" in msg:
                        #print("Task update received!")

                        if os.path.exists(strips_tester.settings.config_file):
                            file_path = strips_tester.settings.config_file
                            # Open file, read all TN settings
                            if os.path.exists(strips_tester.settings.custom_config_file):
                                file_path = strips_tester.settings.custom_config_file

                            data = ""
                            with open(file_path, 'r') as data_file:
                                try:
                                    data = json.load(data_file,object_pairs_hook=OrderedDict)

                                    # Update enable attribute on task
                                    data['task_execution_order'][msg['task_update']['task_slug']]['enable'] = msg['task_update']['task_enable']

                                    # Update TesterPage for clients
                                    self.send_broadcast({"task_update": {"task_slug": msg['task_update']['task_slug'], "task_enable": msg['task_update']['task_enable']}})

                                except Exception as error:
                                    print("[StripsError]: Cannot read from 'config.json' file.")

                            # remove config.json file and replace it with new (updated) one.
                            try:
                                os.remove(strips_tester.settings.custom_config_file)
                            except OSError:
                                pass

                            with open(strips_tester.settings.custom_config_file, 'w') as data_file:
                                try:
                                    data = json.dump(data,data_file, indent=4)

                                except Exception as error:
                                    print("[StripsError]: Cannot write to 'custom_config.json' file.")

                            #print("NEW DATA: {}".format(data))
                        else:
                            # Missing file!
                            print("Datoteke 'config.json' ni mogoce najti!")

                        strips_tester.settings.reload_tasks(strips_tester.settings.config_file, strips_tester.settings.custom_config_file)
                        # update tasks.strips file

                    if "definition_update" in msg:
                        #  Client changed definition. Update server file and forward definition update to clients (broadcast)

                        #print("Definition update received!")

                        # update config.json file

                        if os.path.exists(strips_tester.settings.config_file):
                            file_path = strips_tester.settings.config_file
                            # Open file, read all TN settings
                            if os.path.exists(strips_tester.settings.custom_config_file):
                                file_path = strips_tester.settings.custom_config_file

                            data = ""
                            try:

                                #if "extra_info" in msg['definition_update']['definition_task']]['definition']
                                # if extra info is found with that definition, send task_update to update subtext in all guis

                                with open(file_path, 'r') as data_file:

                                    data = json.load(data_file,object_pairs_hook=OrderedDict)

                                    self.send_broadcast({"definition_update": {"definition_task": msg['definition_update']['definition_task'], "definition_slug": msg['definition_update']['definition_slug'], "definition_value": msg['definition_update']['definition_value']}})

                                    for position, item in enumerate(data['task_execution_order'][msg['definition_update']['definition_task']]['definition']):

                                        if msg['definition_update']['definition_slug'] in item['slug']:
                                            data['task_execution_order'][msg['definition_update']['definition_task']]['definition'][position]['value'] = msg['definition_update']['definition_value']

                            except Exception as error:
                                print("[StripsError]: Cannot read from 'config.json' file.")

                            # remove config.json file and replace it with new (updated) one.
                            try:
                                os.remove(strips_tester.settings.custom_config_file)
                            except OSError:
                                pass

                            try:
                                with open(strips_tester.settings.custom_config_file, 'w') as data_file:

                                    data = json.dump(data,data_file, indent=4)

                            except Exception as error:
                                print("[StripsError]: Cannot write to custom_config.json file.")

                            #print("NEW DATA: {}".format(data))
                        else:
                            # Missing file!
                            print("Datoteke 'config.json' ni mogoče najti!")

                        strips_tester.settings.reload_tasks(strips_tester.settings.config_file, strips_tester.settings.custom_config_file)


                    if "service" in msg:
                        self.send_broadcast({"service": msg['service']})
                        strips_tester.queue.put(msg)  # put to master queue

                    if "test_running" in msg: # Check if test is running
                        if self.startt:
                            self.send(client_number, {"test_running": True})
                        else:
                            self.send(client_number, {"test_running": False})

                    if "maintenance" in msg: # Trigger TN to be in maintenance mode (no tests allowed)
                        self.maintenance = msg['maintenance']
                        self.send_broadcast({"maintenance": self.maintenance})

                        if self.maintenance != -1: # Sets TN in maintenance mode
                            self.result = "maintenance"
                        else: # Release TN from maintenance mode
                            self.result = "idle"

                        self.send_broadcast({"task_result": self.result})

                    if "factory_reset" in msg: # Trigger TN to make factory default settings
                        msg['factory_reset'] = client_number
                        strips_tester.queue.put(msg)  # put to master queue so it cannot be restored mid-testing

                    if "make_log" in msg: # Trigger TN to store log data and send it to client
                        msg['make_log']['id'] = client_number
                        strips_tester.queue.put(msg)  # put to master queue

                    if "set_count" in msg:
                        strips_tester.queue.put(msg)  # put to master queuee

                    if "calibration" in msg:
                        self.send_broadcast({"calibration": msg['calibration']})
                        strips_tester.queue.put(msg)  # put to master queue

                    if "shutdown" in msg:
                        self.send_broadcast({"shutdown": True})
                        strips_tester.queue.put(msg)  # put to master queue

                    if "ping" in msg:
                        self.clientdata[client_number]['last_ping'] = time.time()
                        self.send(client_number,{"ping_answer": msg['ping']})  # Reply with same message
            except socket.error:
                self.close_gui(client_number)

            time.sleep(0.001)
        return

    def close_gui(self,client_number):
        print("SOCKET CLOSING: {}" . format(client_number))

        self.clientdata[client_number]['run'] = False
        self.clientdata[client_number]['connected'] = False
        self.clients_connected = self.clients_connected - 1

        if self.clientdata[client_number]['id'] == self.master_id:  # if master client disconnected
            self.master = False
            self.master_id = -1

            print("Client and master {} closed connection.".format(self.clientdata[client_number]['id']))

            self.send_broadcast({"text": {"text": "Delavec, ki izvaja test se je izpisal. Če želite testirati se ponovno prijavite.\n", "tag": "black"}})
        else:
            print("Client {} closed connection.".format(self.clientdata[client_number]['id']))

        if self.maintenance == self.clientdata[client_number]['id']:
            self.send_broadcast({"maintenance": -1})  # release maintenance mode
            self.maintenance = -1

    def make_gui(self,socket):
        # Find new id for storage informations
        self.clientdata[self.num_of_clients] = {}

        self.clientdata[self.num_of_clients]['connected'] = True
        self.clientdata[self.num_of_clients]['socket'] = socket  # Assign socket to this instance
        self.clientdata[self.num_of_clients]['address'] = socket.getpeername()  # Assign socket to this instance
        self.clientdata[self.num_of_clients]['id'] = -1  # Until requested otherwise
        self.clientdata[self.num_of_clients]['last_ping'] = time.time()
        self.clientdata[self.num_of_clients]['run'] = True

        self.clientdata[self.num_of_clients]['thread'] = threading.Thread(target=self.recieve_process, args=(self.num_of_clients,))
        self.clientdata[self.num_of_clients]['thread'].daemon = True
        self.clientdata[self.num_of_clients]['thread'].start()

        self.num_of_clients = self.num_of_clients + 1
        self.clients_connected = self.clients_connected + 1

    def recvall(self,sock, count):
        # Empty whole buffer
        buf = b''

        # Loop this code until all bytes have arrived (count)
        while count:
            sock.settimeout(5)  # Set timeout to 5 seconds (so it will be timeout in case of not recieving for more than 5 seconds)
            newbuf = sock.recv(count)
            sock.settimeout(None)
            if not newbuf: return ""
            buf += newbuf
            count -= len(newbuf)
        return buf

    def recv_one_message(self,client_number):
        if self.clientdata[client_number]['connected']:
            #print("Client {} is connected, so we recv message." . format(client_number))

            sock = self.clientdata[client_number]['socket']
            try:
                lengthbuf = self.recvall(sock, 4)

                if lengthbuf:
                    length, = struct.unpack('!I', lengthbuf)

                    return self.recvall(sock, length) # Return whole message
                else:
                    return ""

            except Exception as err:
                # Close GUI connection because it cant send to him
                print("Close GUI: not recieved 5 seconds")
                self.close_gui(client_number)


    def send_one_message(self, client_number, data):
        #print("choose: {}" . format(client_number))

        # sock will always be found, but may not be connected
        if self.clientdata[client_number]['connected']:
            #print("Client {} is connected, so we send message." . format(client_number))

            sock = self.clientdata[client_number]['socket']
            length = len(data)
            try:
                sock.sendall(struct.pack('!I', length))
                sock.sendall(data)
            except Exception as err:
                print("Close GUI {}: cant send to him" . format(client_number))
                print(err)
                self.close_gui(client_number)
        else:

            print("Client {} is not connected, so we skip." . format(client_number))

    def get_connection_by_id(self, id):
        # Check if existing id_num exists
        for client_number in range(self.num_of_clients):
            if self.clientdata[client_number]['id'] == id:
                return client_number

        return -1

    def get_client_number_from_address(self, address):
        # Check if existing id_num exists
        for client_number in range(self.num_of_clients):
            #print("loop socket: {}" . format(self.clientdata[client_number]['address']))
            #print("constant connection: {} " . format(address))

            if self.clientdata[client_number]['address'] == address:  # If addresses are same
                return client_number

        return -1

    def connection_handler(self):
        #print("TCP Server thread started!")

        while True:
            try:
                connection, addr = self.server.accept() # accept new GUI

                print("New client detected: {} with address {}" . format(connection,addr))

                self.make_gui(connection)
            except socket.error as msg:
                print("Socket error! {}".format(msg))
                break


    # Send thread: so multiple threads send only one
    # This thread can be active whole time, as its part of test device
    def send_process(self):
        while True:
            if not self.send_queue.empty():  # Something is in the send queue
                msg = self.send_queue.get()  # Get ID and message

                client_number = msg['client']
                data = json.dumps(msg['data'],default=str)
                #print("send_one_message to {}: {}" . format(client_number,data))
                self.send_one_message(client_number, data.encode())
            time.sleep(0.001)



    def close(self):
        # shutdown the socket
        try:
            self.server.shutdown(socket.SHUT_RDWR)
            self.server.close()

        except:
            # Prevent errors such as client already closed.
            pass

        self.server.close()
'''