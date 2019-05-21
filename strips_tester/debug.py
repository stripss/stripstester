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



def insert_test_device(name, nests, address, description, author, date_of_creation):
    myclient = pymongo.MongoClient("mongodb://172.30.129.19:27017/")
    mydb = myclient["stripstester"]
    mycol = mydb['test_device']
    mycol.drop()

    if mycol.find_one({'name': name}) is None:  # Test device does not exist
        data = {'name': name, 'nests': nests, 'address': address, 'description': description, 'author': author, 'date_of_creation': date_of_creation, 'worker_id': -1, 'worker_type': -1}
        print("Test device {} is not found in database, so we create one." . format(name))

        x = mycol.insert_one(data)
    else:
        print("Test device {} is already in database.".format(name))


def main():

    insert_test_device("GO-C19",2,"127.0.0.1:8000","Gorenje C19 sensor","Marcel Jancar",datetime.datetime.now())

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

    while True:
        shifter = devices.HEF4094BT(13, 15, 7, 11)

        shifter.writeraw([0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        time.sleep(1)
        shifter.writeraw([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
        time.sleep(1)

        
        for i in range(1,17):
            shifter.set("L{}".format(i), True)
            shifter.invertShiftOut()
            time.sleep(0.1)
            shifter.set("L{}".format(i), False)
            shifter.invertShiftOut()
            time.sleep(0.1)
    '''
if __name__ == '__main__':
    main()
