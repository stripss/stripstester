#
#import utils
#import time
#
#import devices
#
## !/usr/bin/env python3
## -*- coding: utf-8 -*-
#




'''


Make SEND QUEUE for sending messages without interrupt


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
            
    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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

    def send(self,connection,data):
        # Add message to queue so it won't interfere with other threads
        msg = {}
        msg['connection'] = connection
        msg['data'] = data

        self.send_queue.put(msg)


    def send_broadcast(self,data):
        for client_number in range(self.num_of_clients):
            if self.clientdata[client_number]['connected']:
                self.send(client_number,data)



    def recieve_process(self,connection): # Recieve data from each GUI
        id = 0

        while True:
            #print("Thread with id: {} is talking...".format(id))

            try:
                data = self.recv_one_message(self.clientdata[connection]['connection'])

                if data: #data detected
                    msg = json.loads(data.decode())

                    if "welcome" in msg:  # GUI connected, introducing itself
                        # server return if client is master or not
                        id = msg['welcome']['id']

                        #DB = tester.check_db_connection()
                        #print("Echo tester mode from server: " . format(tester.TestDevice.objects.using(DB).get(name=tester.settings.test_device_name)))

                        # Check if existing id_num exists
                        for client_number in range(self.num_of_clients):
                            if client_number != connection and self.clientdata[client_number]['connected']:
                                if self.clientdata[client_number]['id'] == id:
                                    self.send(connection,{'tester_init': {'id': -1}}) # send -1 if client must shut down due to existion

                                    raise socket.error


                        # Store info of current user
                        self.clientdata[connection]['id'] = id
                        self.clientdata[connection]['test_type'] = msg['welcome']['test_type']

                        if self.master == False:
                            print("New master client GUI detected, ID: {}".format(id))

                            self.master = True
                            self.master_id = id  # Assign new master of test device
                        else:  # Master client exist
                            print("New client GUI detected, ID: {}".format(id))

                        self.send(connection,{'tester_init': {'id': self.master_id}})
                        self.send(connection,{'maintenance': self.maintenance})

                        if __name__ == "__main__":
                            # Showcase
                            self.send(connection, {"task": {"task_name": "Branje QR kode", "task_state": "idle", "task_description": "Kamera prebere QR kodo", "task_enable": True}})
                            self.send(connection, {"definition": {"definition_name": "Resolucija", "task_number": 0, "definition_value": 15, "definition_unit": "dpi"}})
                            self.send(connection, {"definition": {"definition_name": "Čas merjenja", "task_number": 0, "definition_value": 22, "definition_unit": "s"}})
                            self.send(connection, {"task": {"task_name": "Meritev napetosti", "task_state": "idle", "task_description": "Merjenje napetosti na uporu", "task_enable": True}})
                            self.send(connection, {"task": {"task_name": "Meritev upornosti", "task_state": "idle", "task_description": "Meritev upornosti R32", "task_enable": True}})
                            self.send(connection, {"task": {"task_name": "Meritev kapacitivnosti", "task_state": "idle", "task_description": "Meritev kapacitivnosti C103", "task_enable": True}})
                            self.send(connection, {"task": {"task_name": "Meritev grelca", "task_state": "idle", "task_description": "Preveri stanje grelca na plošči", "task_enable": True}})
                            self.send(connection, {"definition": {"definition_name": "R(min)", "task_number": 4, "definition_value": 2.5, "definition_unit": "ohm"}})
                            self.send(connection, {"definition": {"definition_name": "R(max)", "task_number": 4, "definition_value": 5.1, "definition_unit": "ohm"}})
                            self.send(connection, {"task": {"task_name": "Simulacija porabnika", "task_state": "idle", "task_description": "Simulator požene simulacijo žarnice",
                                                            "task_enable": True}})
                            self.send(connection, {"task": {"task_name": "Tiskanje nalepke", "task_state": "idle", "task_description": "Tisk QC nalepke za modul", "task_enable": True}})
                        else:
                            custom_tasks = importlib.import_module("configs." + strips_tester.settings.get_setting_file_name() + ".custom_tasks")

                            for task_name, values in strips_tester.settings.task_execution_order.items():
                                if "name" not in values:
                                    pass

                                if "desc" not in values:
                                    values['desc'] = "unknown"

                                if "enable" not in values:
                                    values['enable'] = 1

                                self.send(connection,{"task": {"task_name": values['name'], "task_state": "idle", "task_description": values['desc'], "task_enable": values['enable'], "task_slug": task_name, "task_info": ""}})

                                for keys2 in values:
                                    if keys2 == 'definition':
                                        for p in values['definition']:
                                            for i in p:
                                                if "name" not in p:
                                                    pass

                                            self.send(connection, {"definition": {"definition_task": task_name, "definition_name": p['name'], "definition_slug": p['slug'], "definition_desc": p['desc'], "definition_value": p['value'], "definition_unit": p['unit']}})

                        query = strips_tester.TestDevice.objects.using(strips_tester.DB).get(name=strips_tester.settings.test_device_name)

                        # Send statistics to newly connected user

                        # Get all tests with this TN
                        count_query = strips_tester.TestDevice_Test.objects.using(strips_tester.DB).filter(test_device_id=query.id, datetime__gte=query.countdate)

                        good = 0
                        bad = 0
                        for current_test in count_query:
                            # Send statistics information
                            good = good + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok=True).count()
                            bad = bad + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok=False).count()

                        count_query_user = count_query.filter(employee=id)

                        user_good = 0
                        user_bad = 0
                        for current_test in count_query_user:
                            # Send statistics information
                            user_good = user_good + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok=True).count()
                            user_bad = user_bad + strips_tester.TestDevice_Product.objects.using(strips_tester.DB).filter(test_id=current_test.id, ok=False).count()

                        self.send(connection,{"count": {"good": user_good, "bad": user_bad,"good_global": good, "bad_global": bad, "countdate": query.countdate}})
                        self.send(connection,{"calibration": query.calibrationdate})
                        self.send(connection,{"path_manual": query.manual})
                        self.send(connection,{"service": query.service})
                        self.send(connection,{"task_result": self.result})
                        self.send(connection,{'esd': True})
                        self.send(connection,{'high_voltage': True})

                    if "close" in msg:
                        raise socket.error # End socket thread

                    if "stop_test_device" in msg:
                        if self.startt:
                            self.send(connection,{"text": {"text": "TEST PREKINJEN!\n", "tag": "red"}})
                        else:
                            self.send(connection,{"text": {"text": "TEST SE ŠE NI ZAČEL!\n", "tag": "red"}})

                    if "start_test_device" in msg:
                        if self.startt:
                            self.send(connection,{"text": {"text": "Test se že izvaja.\n", "tag": "red"}})
                        else:
                            if self.maintenance == -1:
                                self.startt = True

                                # Assign which user is making a test
                                self.test_user_id = self.clientdata[connection]['id']
                                self.test_user_type = self.clientdata[connection]['test_type']
                            else:
                                self.send(connection,{"text": {"text": "Naprava je v vzdrževalnem načinu.\n", "tag": "yellow"}})


                    if "task_update" in msg:
                        print("Task update received!")

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


                        # update tasks.strips file

                    if "definition_update" in msg:
                        print("Definition update received!")

                        # update config.json file

                        if os.path.exists(strips_tester.settings.config_file):
                            file_path = strips_tester.settings.config_file
                            # Open file, read all TN settings
                            if os.path.exists(strips_tester.settings.custom_config_file):
                                file_path = strips_tester.settings.custom_config_file

                            data = ""
                            try:
                                with open(file_path, 'r') as data_file:

                                    data = json.load(data_file,object_pairs_hook=OrderedDict)

                                    #print("OLD DATA: {}".format(data))
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

                    if "service" in msg:
                        self.send_broadcast({"service": msg['service']})
                        strips_tester.queue.put(msg)  # put to master queue

                    if "test_running" in msg: # Check if test is running
                        if self.startt:
                            self.send(connection, {"test_running": True})
                        else:
                            self.send(connection, {"test_running": False})

                    if "maintenance" in msg: # Trigger TN to be in maintenance mode (no tests allowed)
                        self.maintenance = msg['maintenance']
                        self.send_broadcast({"maintenance": self.maintenance})

                        if self.maintenance != -1: # Sets TN in maintenance mode
                            self.result = "maintenance"
                        else: # Release TN from maintenance mode
                            self.result = "idle"

                        self.send_broadcast({"task_result": self.result})

                    if "factory_reset" in msg: # Trigger TN to make factory default settings
                        msg['factory_reset'] = connection
                        strips_tester.queue.put(msg)  # put to master queue so it cannot be restored mid-testing

                    if "make_log" in msg: # Trigger TN to store log data and send it to client
                        msg['make_log']['id'] = connection
                        strips_tester.queue.put(msg)  # put to master queue

                    if "set_count" in msg:
                        strips_tester.queue.put(msg)  # put to master queuee

                    if "calibration" in msg:
                        self.send_broadcast({"calibration": msg['calibration']})
                        strips_tester.queue.put(msg)  # put to master queue

                    if "shutdown" in msg:
                        strips_tester.queue.put(msg)  # put to master queue





            except socket.error:
                self.clientdata[connection]['connected'] = False
                self.clients_connected = self.clients_connected - 1

                if self.clientdata[connection]['id'] == self.master_id:  # if master client disconnected
                    self.master = False
                    self.master_id = -1

                    print("Client and master {} closed connection." . format(id))

                    self.send_broadcast({"text": {"text": "Delavec, ki izvaja test se je izpisal. Če želite testirati se ponovno prijavite.\n", "tag": "black"}})
                else:
                    print("Client {} closed connection." . format(id))

                if self.maintenance == self.clientdata[connection]['id']:
                    self.send_broadcast({"maintenance": -1})  # release maintenance mode
                    self.maintenance = -1

                return

            time.sleep(0.01)

    def recvall(self,sock, count):
        buf = b''
        while count:
            newbuf = sock.recv(count)
            if not newbuf: return None
            buf += newbuf
            count -= len(newbuf)
        return buf

    def recv_one_message(self,sock):
        lengthbuf = self.recvall(sock, 4) # Recieve buffer size message
        length, = struct.unpack('!I', lengthbuf) # Unpack oncoming buffer length
        return self.recvall(sock, length) # Recieve whole message

    def send_one_message(self, sock, data):
        length = len(data)
        sock.sendall(struct.pack('!I', length))
        sock.sendall(data)

    def get_connection_by_id(self, id):
        # Check if existing id_num exists
        for client_number in range(self.num_of_clients):
            if self.clientdata[client_number]['id'] == id:
                return client_number

        return -1

    def connection_handler(self):
        #print("TCP Server thread started!")

        while True:
            try:
                connection, addr = self.server.accept() # accept new GUI

                print("New client detected: {} with address {}" . format(connection,addr))

                #Find new id for storage informations
                self.clientdata[self.num_of_clients] = {}

                self.clientdata[self.num_of_clients]['connected'] = True
                self.clientdata[self.num_of_clients]['connection'] = connection
                self.clientdata[self.num_of_clients]['id'] = -1  # Until requested otherwise
                self.clientdata[self.num_of_clients]['thread'] = threading.Thread(target=self.recieve_process, args=(self.num_of_clients,))
                self.clientdata[self.num_of_clients]['thread'].daemon = True
                self.clientdata[self.num_of_clients]['thread'].start()

                self.num_of_clients = self.num_of_clients + 1
                self.clients_connected = self.clients_connected + 1
            except socket.error as msg:
                print("Socket error! {}".format(msg))
                break


    # Send thread: so multiple threads send only one
    def send_process(self):
        while True:
            if not self.send_queue.empty(): # something is in the send queue
                msg = self.send_queue.get() # get ID and message

                connection = msg['connection']
                data = json.dumps(msg['data'],default=str)

                self.send_one_message(self.clientdata[connection]['connection'], data.encode())
            time.sleep(0.01)



    def close(self):
        # shutdown the socket
        try:
            self.server.shutdown(socket.SHUT_RDWR)

        except:
            pass

        self.server.close()
