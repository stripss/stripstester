import time
import serial
# import cv2
# from smbus2 import SMBusWrapper
# global img
import random
import devices
# import struct
import numpy as np
import RPi.GPIO as GPIO
# import utils
import cv2
# import datetime
# import re
# import subprocess
import datetime
import multiprocessing
import threading
import pymongo
import strips_tester
import plotly
from plotly.graph_objs import Bar, Scatter, Layout, Figure

def insert_test_device(name, nests, address, description, author, date_of_creation):
    myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    mydb = myclient["stripstester"]
    mycol = mydb['test_device']

    if mycol.find_one({'name': name}) is None:  # Test device does not exist
        data = {'name': name, 'nests': nests, 'address': address, 'description': description, 'author': author, 'date_of_creation': date_of_creation, 'worker_id': -1, 'worker_type': -1}
        print("Test device {} is not found in database, so we create one.".format(name))

        x = mycol.insert_one(data)
    else:
        print("Test device {} is already in database.".format(name))


def main():
    #g = devices.GoDEXG300(port='/dev/godex', timeout=3.0)
    #print_sticker(1,g)
    #insert_test_device("GACS_A2 Bender", 1, "127.0.0.1", "Bender module", "Marcel Jancar", datetime.datetime.now())
    #insert_test_device("GO-HA-2", 2, "127.0.0.1", "GO Hall sensor test device", "Marcel Jancar", datetime.datetime.now())
    #g.close()
    '''    shifter = devices.HEF4094BT(24, 31, 26, 29)


    while True:
        shifter.set("K9", True)
        shifter.invertShiftOut()
        time.sleep(2)
        shifter.set("K9", False)
        shifter.invertShiftOut()
        time.sleep(2)
    '''


def print_sticker(test_status,printer):
    program = "S001"

    code = {}
    code['S001'] = 435545
    code['S002'] = 552943
    qc_id = -1

    date = datetime.datetime.now().strftime("%d.%m.%Y")

    if test_status == 1:  # Test OK
        inverse = '^L\n'
        darkness = '^H15\n'
    else:  # Test FAIL
        inverse = '^LI\n'
        darkness = '^H4\n'

    if qc_id != -1:
        qc = "QC {}".format(qc_id)
    else:
        qc = ""

    label = ('^Q9,3\n'
             '^W21\n'
             '{}'
             '^P1\n'
             '^S2\n'
             '^AD\n'
             '^C1\n'
             '^R12\n'
             '~Q+0\n'
             '^O0\n'
             '^D0\n'
             '^E12\n'
             '~R200\n'
             '^XSET,ROTATION,0\n'
             '{}'
             'Dy2-me-dd\n'
             'Th:m:s\n'
             'AA,8,10,1,1,0,0E,ID:{}     {}\n'
             'AA,8,29,1,1,0,0E,C-19_PL_UF_{}\n'
             'AA,8,48,1,1,0,0E,{}  {}\n'
             'E\n').format(darkness, inverse, code[program], " ", program, date, qc)

    print("a")
    printer.send_to_printer(label)
    time.sleep(1)

    #insert_test_device("Photointerrupter", 3, "192.168.88.227", "Interrupt switch", "Marcel Jancar", datetime.datetime.now())

    #arduino = devices.ArduinoSerial('/dev/arduino', baudrate=115200)
    #arduino.write("calibrate")
    #arduino.write("move 20")
    #while True:
    #    time.sleep(1)
    ##arduino.write("servo 3 0")
    #for i in range(10):
    #    arduino.write("servo 3 100")
    #    arduino.write("move 20")
    #    arduino.write("servo 3 0")
    #    arduino.write("move 0")
    #    arduino.write("move 20")
    #    arduino.write("servo 3 100")
    #    arduino.write("move 0")
    #arduino.write("move 20")
    #arduino.write("servo 3 100")
    #arduino.write("move 0")
    #arduino.close()
    '''
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(8, GPIO.OUT)
    GPIO.output(8, GPIO.HIGH)
    time.sleep(0.2)
    GPIO.output(8, GPIO.LOW)

    shifter = devices.HEF4094BT(24, 31, 26, 29)
    shifter.reset()

    which = 0
    shifter.set("K10", which)  # Segger SWIM Left
    shifter.set("K12", which)  # Segger RESET Left
    shifter.set("K13", which)  # Segger VCC Left
    shifter.set("K14", which)  # Segger GND Left
    shifter.set("K11", True)  # Segger RESET disable
    shifter.invertShiftOut()

    segger = devices.Segger("/dev/segger")
    segger.select_file("S001")
    print(segger.download())
    GPIO.output(7,GPIO.HIGH)
    segger.close()
    '''
    # insert_test_device("GO-HA-1",2,"127.0.0.1:8000","Gorenje Hall sensor","Marcel Jancar",datetime.datetime.now())
    '''
    a = [2,3,4]
    b = [5,6,7]
    trace1 = Bar(
        x=a,
        y=b,
        name="too")

    trace2 = Bar(
        x=b,
        y=a,
        name="tsd")

    data = [trace1,trace2]

    layout = Layout(
        barmode='group'
    )

    fig = Figure(data=data, layout=layout)

    plot = plotly.offline.plot(fig,filename='grouped-bar.html')
    '''

'''
myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
mydb = myclient["stripstester"]
#print(mydb.list_collection_names())
mycol = mydb['test_info']
mydata = mydb['test_data']

for x in mycol.find():
    print("Found new test: {}" . format(x))

    for y in mydata.find({"test_info": x['_id']}):
        print("  Its data: {}" . format(y))

led_gpio = [40, 37, 38, 35, 36, 33]
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Prepare GPIO list for visual test (left leds, right leds)
for current in led_gpio:
    GPIO.setup(current, GPIO.IN)
while True:
    state_list = []

    for current in range(len(led_gpio)):
        state_list.append(GPIO.input(led_gpio[current]))

        #print("{} -> [{}] {}".format(current, mask[current], state_list[-1]))

    print(state_list)
    time.sleep(0.1)
'''
if __name__ == '__main__':
    main()
