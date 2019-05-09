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

    godex = devices.Godex('/dev/usb/lp0')

    label = ('^Q9,3\n'
             '^W21\n'
             '^H4\n'
             '^P1\n'
             '^S2\n'
             '^AD\n'
             '^C1\n'
             '^R0\n'
             '~Q-8\n'
             '^O0\n'
             '^D0\n'
             '^E12\n'
             '~R255\n'
             '^XSET,ROTATION,0\n'
             '^L\n'
             'Dy2-me-dd\n'
             'Th:m:s\n'
             'AD,24,14,1,1,0,0E,GoLabel\n'
             'E\n')

    godex.send_to_printer(label)
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
