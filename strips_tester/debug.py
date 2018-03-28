#
#import utils
#import time
#
#import devices
#
## !/usr/bin/env python3
## -*- coding: utf-8 -*-
#



import socket
import json
import time


def send(data):
    data = json.dumps(data)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('localhost', 1234))

    client.send(data.encode())

    client.shutdown(socket.SHUT_RDWR)
    client.close()


send({"tester_init": "true"})
send({"count": {"good": 53, "bad": 62}})
send({"test": {"text": "Tester initialized...\n", "tag": "purple"}})
time.sleep(2)
send({"task": {"task_name": "Branje QR kode", "task_state": "idle"}})
send({"task": {"task_name": "Meritev napetosti", "task_state": "idle"}})
send({"task": {"task_name": "Meritev upornosti", "task_state": "idle"}})
send({"task": {"task_name": "Meritev kapacitivnosti", "task_state": "idle"}})
send({"task": {"task_name": "Meritev grelca", "task_state": "idle"}})
send({"task": {"task_name": "Simulacija porabnika", "task_state": "idle"}})
send({"task": {"task_name": "Tiskanje nalepke", "task_state": "idle"}})


send({"text": {"text": "Začetek meritve QR kode...\n", "tag": "black"}})
time.sleep(5)
send({"text": {"text": "QR koda prebrana!\n", "tag": "green"}})
send({"task_update": {"task_number": 0, "task_state": "ok"}})
send({"text": {"text": "Meritev napetosti...\n", "tag": "black"}})
time.sleep(2)
send({"text": {"text": "Izmerjenih 6.95V. Meritev neuspešna!\n", "tag": "red"}})
send({"task_update": {"task_number": 1, "task_state": "fail"}})
send({"text": {"text": "Merjenje upornosti...\n", "tag": "black"}})
time.sleep(4)
send({"text": {"text": "Izmerjenih 22ohm.\n", "tag": "green"}})
send({"task_update": {"task_number": 2, "task_state": "ok"}})
send({"text": {"text": "Merjenje kondenzatorja...\n", "tag": "black"}})
time.sleep(1)
send({"text": {"text": "Še kar poteka...\n", "tag": "black"}})
time.sleep(1)
send({"text": {"text": "Še kar poteka...\n", "tag": "black"}})
time.sleep(1)
send({"text": {"text": "Še kar poteka...\n", "tag": "black"}})
time.sleep(1)
send({"text": {"text": "Kapacitivnost: 100uF. Meritev uspešna!\n", "tag": "green"}})
send({"task_update": {"task_number": 3, "task_state": "ok"}})
send({"text": {"text": "Meritev grelca...\n", "tag": "black"}})
time.sleep(2)
send({"text": {"text": "Grelec deluje!\n", "tag": "green"}})
send({"task_update": {"task_number": 4, "task_state": "ok"}})
send({"text": {"text": "Simulacija v teku...\n", "tag": "black"}})
time.sleep(2)
send({"text": {"text": "Ne najdem simulatorja!\n", "tag": "red"}})
send({"task_update": {"task_number": 5, "task_state": "fail"}})
send({"text": {"text": "Tiskanje nalepke...\n", "tag": "black"}})
time.sleep(1)
send({"task_update": {"task_number": 6, "task_state": "ok"}})
send({"text": {"text": "Stiskano!\n", "tag": "green"}})
send({"text": {"text": "Opozorilo: Tonerja bo kmalu zmanjkalo.\n", "tag": "yellow"}})
send({"text": {"text": "Konec simulacije...\n", "tag": "black"}})


#client.send(data.encode())
#data = json.dumps({"task_update": {"task_number": 0, "task_state": "ok", "task_name": "Merjenje upornosti"}})
#client.send(data.encode())
#data = json.dumps({"task_update": {"task_number": 0, "task_name": "Meritev faze", "task_state": "idle"}})
#client.send(data.encode())
#data = json.dumps({"text": "Merjenje napetosti...\n"})
#client.send(data.encode())
#data = json.dumps({"task": {"task_name": "Meritev upornosti", "task_state": "idle"}})
#client.send(data.encode())

