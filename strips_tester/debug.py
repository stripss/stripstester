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


def main():
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
