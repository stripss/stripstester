import time
import serial
#import cv2
#from smbus2 import SMBusWrapper
#global img
import random
import devices
#import struct
#import numpy as np
import RPi.GPIO as GPIO
#import utils
import cv2
#import datetime
#import re
#import subprocess
import datetime
import numpy as np
import keyboard

def show_webcam(camname):
    cam = cv2.VideoCapture(camname)
    global img
    while True:
        ret_val, img = cam.read()

        roi_x = 80
        roi_y = 200
        roi_width = 440
        roi_height = 180

        roi = img[roi_y:roi_y + roi_height,roi_x:roi_width + roi_x]

        #roi = img
        # Convert BGR to HSV
        gs = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)

        # Set threshold and maxValue
        thresh = 100
        maxValue = 255

        th, dst = cv2.threshold(gs, 120, maxValue, cv2.THRESH_BINARY)
        th, dst2 = cv2.threshold(gs, 220, maxValue, cv2.THRESH_BINARY)
        '''
        # Basic threshold example
        led = []

        
        led.append(detect_led_state(dst,126,116,15))
        led.append(detect_led_state(dst,360,120,15))
        led.append(detect_led_state(dst,542,122,5))

        led.append(detect_led_state(dst,126,290,15))
        led.append(detect_led_state(dst,356,302,15))
        led.append(detect_led_state(dst,542,288,5))
        

        # Green lights
        # Thresh 100
        led.append(detect_led_state(dst,225,175,10)) # left
        led.append(detect_led_state(dst,380,170,10)) # right

        # Red lights
        # Thresh 200
        led.append(detect_led_state(dst2,260,170,10)) # left
        led.append(detect_led_state(dst2,340,170,10)) # right
        #led.append(detect_led_state(dst,250,100,25))
        '''
        #print(led)
        cv2.imshow('Threshold image', dst)
        cv2.imshow('Threshold2 image', dst2)
        cv2.imshow('Region of interest', roi)

        #time.sleep(0.1)
        if cv2.waitKey(1) == 27:
            break  # esc to quit
    cv2.destroyAllWindows()


def detect_led_state(th, x, y, rng):

    x = x - 80
    y = y - 80

    state = False

    black = 0
    white = 0

    cv2.circle(th, (x,y), rng-1, (255,255,255), 1)
    cv2.circle(th, (x,y), rng+1, (0,0,0), 1)

    for yy in range(-rng,rng):
        for xx in range(-rng,rng):
            #print(x+xx)
            #print(y+yy)
            pixel = th[y+yy][x+xx] % 254

            if pixel:
                white += 1
            else:
                black += 1

    # Return True if there is more white than black
    if white > black:
        state = True

    return state

def test_mcp():
    mcp = devices.MCP23017(0x20)

    mcp.clear_bit(0xFF)
    mcp.set_bit(0xC)

def multimeter():
    while True:
        print(multi.read().numeric_val)

def print_current_time():
    import pytz
    print(pytz.timezone("Europe/Ljubljana"))
    print(datetime.datetime.now())

def display_cam(camname):
    cv2.namedWindow("preview")
    vc = cv2.VideoCapture(camname)

    if vc.isOpened():  # try to get the first frame
        rval, frame = vc.read()
    else:
        rval = False

    x = 120
    y = 120
    h = 300
    w = 350

    while rval:
        '''
        if keyboard.is_pressed('f'):  # if key 'q' is pressed
            if keyboard.is_pressed('w'):#if key 'q' is pressed
                y = y - 1
                if y < 0:
                    y = 0

            if keyboard.is_pressed('a'):#if key 'q' is pressed
                x = x - 1
                if x < 0:
                    x = 0

            if keyboard.is_pressed('s'):#if key 'q' is pressed
                y = y + 1
                if y > 480:
                    y = 480

            if keyboard.is_pressed('d'):#if key 'q' is pressed
                x = x + 1
                if x > 640:
                    x = 640
        else:
            if keyboard.is_pressed('w'):  # if key 'q' is pressed
                h = h - 1
                if y < 0:
                    y = 0

            if keyboard.is_pressed('a'):  # if key 'q' is pressed
                w = w - 1
                if x < 0:
                    x = 0

            if keyboard.is_pressed('s'):  # if key 'q' is pressed
                h = h + 1
                if y > 480:
                    y = 480

            if keyboard.is_pressed('d'):  # if key 'q' is pressed
                w = w + 1
                if x > 640:
                    x = 640
        '''
        cv2.imshow("preview",frame[y:y+h, x:x+w])
        print("x: {}, y: {}, h: {}, w: {}" . format(x,y,h,w))
        #cv2.imshow("preview",frame)
        rval, frame = vc.read()

        key = cv2.waitKey(20)
        if key == 27:  # exit on ESC
            break

    cv2.destroyWindow("preview")
    vc.release()

def rotateImage(image, angle):
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
    return result

def main():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    display_cam('/dev/logitech')
    #print_current_time()
    #v = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1",0.16)

    #relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
    #GPIO.setup(7, GPIO.OUT)
    #GPIO.output(7,False)
    #time.sleep(3)
    #GPIO.output(7,True)
    #relay_board.close_relay(8)
    #relay_board.close_relay(4)
    #relay_board.close_relay(11)
    #time.sleep(1)

    #relay_board.open_relay(4)
    #relay_board.open_relay(11)
    #relay_board.open_relay(8)
    #v.close()
    #display_cam('/dev/microsoft')
    #show_webcam('/dev/microsoft')
    #relay_board.open_all_relays()
    #relay_board.hid_device.close()

    #GPIO.output(11,True)
    '''
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    pin = 35
    GPIO.setup(pin, GPIO.OUT)

    GPIO.output(pin,True)

    time.sleep(1)
    GPIO.output(pin,False)

    GPIO.cleanup()

    #yoc = devices.Digi("VOLTAGE1-B5E9C.voltage1",0)

    multi = devices.DigitalMultiMeter("/dev/ohmmeter")
    arduino = devices.Arduino(0x04)
    arduino.calibrate()
    arduino.moveStepper(7)
    #arduino.send_command(108,100)

    arduino.relay(1)  # Ohmmeter mode
    arduino.connect()
    #arduino.servo(1,100)
    #arduino.send_command(108,100)
    for i in range(100):
        print(multi.read(1).numeric_val)
    #
    arduino.disconnect()
    multi.close()
    '''
    #test_mcp()
    #check_leds(0)
    #show_webcam()
    #check_arduino()
    #img = cv2.imread("C:/Users/marcelj/Desktop/strips_tester_project_git/strips_tester/MVCTEMP/Picture1.jpg") # reads image as grayscale
    #cv2.imshow('image',img)

    #volt = devices.DigitalMultiMeter('/dev/hidraw0')

    #3m = volt.read()

    #print(m)
    #volt.close()
    
'''
    #data = [0xa5,0xd5,0x9e,0x48]
    data = [165,213,158,72]

    b = []
    for item in data:
        b.append(hex(item))
    print(b)

    vstr = ''
    for item in b:
        vstr = vstr + item[2:] + " "

    print(vstr)
    e = bytearray.fromhex(vstr)
    print(struct.unpack('<f', e))
'''
def check_leds(side):
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
    GPIO.setup(12, GPIO.OUT) # faza
    GPIO.setup(16, GPIO.OUT) # nula


    GPIO.setup(22, GPIO.OUT)
    GPIO.setup(13, GPIO.OUT)
    GPIO.setup(15, GPIO.OUT)
    GPIO.setup(29, GPIO.OUT)

    if side:
        GPIO.output(22, False)
        GPIO.output(13, False)
        GPIO.output(15, False)
        GPIO.output(29, False)


    time.sleep(1)
    GPIO.output(12, False)
    GPIO.output(16, False)
    time.sleep(10)
    GPIO.output(12, True)
    GPIO.output(16, True)

if __name__ == '__main__':
    main()