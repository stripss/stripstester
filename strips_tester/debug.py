import time
import serial
#import cv2
#from smbus2 import SMBusWrapper
#global img
import random
import devices
#import struct
import numpy as np
import RPi.GPIO as GPIO
#import utils
import cv2
#import datetime
#import re
#import subprocess
import datetime
import multiprocessing
import threading


def main():
    print("Executing debug...")
   
	arduino = devices.ArduinoSerial("/dev/ttyACM0")
	arduino.write("calibrate")

	arduino.close()
   
	print("Debug done.");


if __name__ == '__main__':
    main()