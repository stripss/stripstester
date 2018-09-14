
import time
import cv2
from smbus2 import SMBusWrapper
global img
import random


def show_webcam(mirror=False):
    cam = cv2.VideoCapture(0)
    global img
    while True:
        ret_val, img = cam.read()

        roi_x = 80
        roi_y = 80
        roi_width = 490
        roi_height = 280

        roi = img[roi_y:roi_y + roi_height,roi_x:roi_width + roi_x]

        #roi = img
        # Convert BGR to HSV
        gs = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)

        # Set threshold and maxValue
        thresh = 150
        maxValue = 255

        th, dst = cv2.threshold(gs, thresh, maxValue, cv2.THRESH_BINARY)

        # Basic threshold example
        led = []
        led.append(detect_led_state(dst,126,116,15))
        led.append(detect_led_state(dst,360,120,15))
        led.append(detect_led_state(dst,542,122,5))

        led.append(detect_led_state(dst,126,290,15))
        led.append(detect_led_state(dst,356,302,15))
        led.append(detect_led_state(dst,542,288,5))

        print(led)

        cv2.imshow('Threshold image', dst)
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


class Arduino:
    def __init__(self,address = 0x04):
        if isinstance(address, str):
            address = int(address,16)

        self.addr = address
        self.ready = 0

    # Ping MCP23017 to see if address is valid
    def moveStepper(self,index):
        if not index or index > 40:
            return

        with SMBusWrapper(1) as bus:
            result = False

            for i in range(20):
                # Set port A as output
                try:
                    bus.write_byte(0x04, 100)
                    time.sleep(0.1)
                    bus.write_byte(0x04, index)

                    result = True
                    self.ready = 0

                    break
                except OSError:
                    print("Write OS Error")
                    time.sleep(0.1)

            if not result:
                raise Exception

            print(self.ready)
            while not self.ready:
                try:
                    self.ready = bus.read_byte(0x04)
                    break
                except OSError:
                    print("Read OS Error")
                    time.sleep(0.1)

    def connect(self):
        with SMBusWrapper(1) as bus:
            result = False

            for i in range(20):
                # Set port A as output
                try:
                    bus.write_byte(0x04, 101)

                    result = True
                    self.ready = 0

                    break
                except OSError:
                    print("Write OS Error")
                    time.sleep(0.1)

            if not result:
                raise Exception

            while not self.ready:
                try:
                    self.ready = bus.read_byte(0x04)
                    break
                except OSError:
                    print("Read OS Error")
                    time.sleep(0.1)

    def disconnect(self):
        with SMBusWrapper(1) as bus:
            result = False


            for i in range(20):
                # Set port A as output
                try:
                    bus.write_byte(0x04, 102)

                    result = True
                    self.ready = 0

                    break
                except OSError:
                    print("Write OS Error")
                    time.sleep(0.1)

            if not result:
                raise Exception

            while not self.ready:
                try:
                    self.ready = bus.read_byte(0x04)
                    break
                except OSError:
                    print("Read OS Error")
                    time.sleep(0.1)

def check_arduino():
    arduino = Arduino(0x04)

    li1 = [18,19,20,30,10,15,16,17,18,24,27,2,7,8]

    arduino.disconnect()
    for i in range(30):
        arduino.moveStepper(i)

        arduino.connect()
        arduino.disconnect()


    arduino.disconnect()
def main():
    #check_arduino()
    show_webcam(mirror=True)


    #img = cv2.imread("C:/Users/marcelj/Desktop/strips_tester_project_git/strips_tester/MVCTEMP/Picture1.jpg") # reads image as grayscale
    #cv2.imshow('image',img)



    '''
    
        DIR = 20   # Direction GPIO Pin
        EN = 21   # Direction GPIO Pin
        STEP = 17  # Step GPIO Pin
        CW = 1     # Clockwise Rotation
        CCW = 0    # Counterclockwise Rotation
        SPR = 3500   # Steps per Revolution (360 / 7.5)
    
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(DIR, GPIO.OUT)
        GPIO.setup(STEP, GPIO.OUT)
        GPIO.setup(EN, GPIO.OUT)
        GPIO.output(DIR, CW)
    
        step_count = SPR
        delay = .001
    
        for i in range(4):
            GPIO.output(EN,GPIO.LOW)
            GPIO.output(DIR, 0)
            for x in range(step_count):
                GPIO.output(STEP, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(STEP, GPIO.LOW)
                time.sleep(delay)
    
            time.sleep(.5)
            GPIO.output(DIR, 1)
            for x in range(step_count):
                GPIO.output(STEP, GPIO.HIGH)
                time.sleep(delay)
                GPIO.output(STEP, GPIO.LOW)
                time.sleep(delay)
            GPIO.output(EN,GPIO.HIGH)
    
        GPIO.cleanup
        
    '''
if __name__ == '__main__':
    main()