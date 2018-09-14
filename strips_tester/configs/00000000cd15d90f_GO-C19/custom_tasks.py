
import importlib
import logging
import sys
import time
import multiprocessing
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import settings, server
from tester import Task
import cv2
import os
import numpy as np
import serial
import threading
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays

# You may set global test level and logging level in config_loader.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)



class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.start_time = self.get_definition("start_time")
        self.end_time = self.get_definition("end_time")
        '''
        # Initialize NanoBoards
        self.nanoboard = self.use_device('NanoBoard')
        self.nanoboard_small = self.use_device('NanoBoardSmall')

        # Initialize LightBoard
        self.lightboard = self.use_device('LightBoard')

        time.sleep(self.start_time)

        for i in range(3):
            time.sleep(0.1)
            self.lightboard.set_led_status(0xFF)
            time.sleep(0.1)
            self.lightboard.set_led_status(0x00)

        self.nanoboard.test_float()

        print("Float 3.66 sent.")
        while True:
            time.sleep(0.1)
        '''

        return Task.TASK_OK

    def run(self) -> (bool, str):
        # Razklenitev 230VAC
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        # Lock test device
        GPIO.output(gpios['LOCK'], False)

        # BOARD DETECTION


        # Measure R3 for board detection
        resistance = self.nanoboard.probe(0)

        # Resistance should be less than 60ohms (47E)
        if resistance < 1000:
            strips_tester.left.exist = True

        resistance = self.nanoboard.probe(17)

        # Resistance should be less than 60ohms (47E)
        if resistance < 1000:
            strips_tester.right.exist = True

        # Probe POT1
        if strips_tester.left.exist:
            resistance = self.nanoboard.probe(5)

            # Map left servo to resistance value
            angle = 50
            self.nanoboard_small.servo(1,angle)

        # Probe POT1
        if strips_tester.right.exist:
            resistance = self.nanoboard.probe(23)

            # Map left servo to resistance value
            angle = 50
            self.nanoboard_small.servo(2,angle)

        # Lift servo platform
        self.nanoboard_small.MoveStepper(5)

        # Rotate potentiometers to zero
        self.nanoboard_small.servo(1,0)
        self.nanoboard_small.servo(2,0)

        strips_tester.product.add_measurement("R3", True, resistance)

        return Task.TASK_OK

    def tear_down(self):
        time.sleep(self.end_time)
        print("LEFT Exist: {}".format(strips_tester.left.exist))
        print("RIGHT Exist: {}".format(strips_tester.right.exist))



class EndProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # Initialize LightBoard
        self.lightboard = self.use_device('LightBoard')

    def run(self) -> (bool, str):

        if strips_tester.current_product.countbad:
            GPIO.output(gpios["BUZZER"],False)
            time.sleep(1)
            GPIO.output(gpios["BUZZER"], True)

        self.i2c.set_led_status(0xff)
        time.sleep(1)
        self.i2c.set_led_status(0x00)

        # 0 - off
        # 1 - red
        # 2 - green
        # 3 - yellow

        return {"signal": [1, "ok", 5, "NA",""]}

    def tear_down(self):
        pass


class VisualTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.mesurement_delay = 0.16
        self.measurement_results = {}

        self.camera = cv2.VideoCapture(0)  # video capture source camera
        self.threshold = 150

        self.roi_x = 80
        self.roi_y = 80
        self.roi_width = 490
        self.roi_height = 280

        self.led = []
        for i in range(6):
            self.led.append({}) # Append dictionary
            self.led[-1]['x'] = self.get_definition("led{}_posx" . format(i + 1))
            self.led[-1]['y'] = self.get_definition("led{}_posy" . format(i + 1))


    def run(self) -> (bool, str):

        time.sleep(1) # Wait camera to respond

        # skleni L in N
        # preveri sliko če svetijo led
        # pocakaj 2 sekundi
        # poglej ce so ugasnile ledice
        # tlivke ne smejo svetiti
        # zavrti potenciometre v drugo smer
        # glej da vse tri svetijo
        # izklopi L in N


        try:
            # Sklenitev 230VAC
            GPIO.output(gpios['FAZA'], False)
            GPIO.output(gpios['NULA'], False)

            # Preveri da svetijo vse LED (brez tlivk?)
            self.get_light_states()

            if self.check_mask([1,1,1,1,1,1]):
                print("Start OK")
            else:
                print("Start FAIL")

            time.sleep(5)

            # Preveri da ugasnejo vse luci
            self.get_light_states()

            if self.check_mask([0,0,1,0,0,1]):
                print("Mid OK")
            else:
                print("Mid FAIL")

            # Razklenitev 230VAC
            GPIO.output(gpios['FAZA'], True)
            GPIO.output(gpios['NULA'], True)

            # Preveri da ugasnejo vse luci
            self.get_light_states()

            if self.check_mask([0,0,0,0,0,0]):
                print("End OK")
            else:
                print("End FAIL")

            #return self.measurement_results
            return {"signal": [1, "ok", 2, "NA",""]}

        except Exception as err:
            server.send_broadcast({"text": {"text": "Napaka interne kamere! {}\n".format(err), "tag": "red"}})
            return {"signal": [1, "fail", 2, "NA",""]}

    def get_threshold_image(self):
        # Update few frames to get accurate image
        for refresh in range(5):
            ret, frame = self.camera.read()  # return a single frame in variable `frame`

        roi = frame[self.roi_y:self.roi_y + self.roi_height,self.roi_x:self.roi_width + self.roi_x] # Make region of interest
        grayscale = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) # Grayscale ROI

        # Make binary image from grayscale ROI
        th, dst = cv2.threshold(grayscale, self.threshold, 255, cv2.THRESH_BINARY)

        return dst

    def check_mask(self,mask):
        result = True
        for i in range(len(self.led)):
            if self.led[i]['state'] != mask[i] and mask[i] != -1:
                result = False
                break

        return result


    def get_light_states(self):
        img = self.get_threshold_image()

        for i in range(len(self.led)):
            self.led[i]['state'] = self.detect_led_state(img, int(self.led[i]['x']), int(self.led[i]['y']), 5)

    def detect_led_state(self, th, x, y, rng):
        x = x - self.roi_x
        y = y - self.roi_y

        state = False

        black = 0
        white = 0

        for yy in range(-rng, rng):
            for xx in range(-rng, rng):
                pixel = th[y + yy][x + xx] % 254

                if pixel:
                    white += 1
                else:
                    black += 1

        # Return True if there is more white than black
        if white > black:
            state = True

        return state

    def tear_down(self):
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)
        # GPIO.output(gpios['LOCK'],True)

        self.camera.release()




class FlashMCU(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.measurement_results = {}

        self.file = self.get_definition("file")

        # Segger serial communication configuration
        self.ser = serial.Serial(
            port='/dev/ttyUSB0',
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )


    def run(self) -> (bool, str):
        # Check if product exists
        # Nalozi glede na to

        try:
            server.send_broadcast({"text": {"text": "Nalaganje programa '{}'.\n" . format(self.file), "tag": "black"}})
            result = False

            for i in range(3):
                if not result:
                    # DELETE 3 FILES .ini, .cfg, .dat
                    # MAKE NEW FILES

                    answer = self.send_command("SELECT {}".format(self.file))

                    if "OK" in answer:
                        answer = self.send_command("AUTO")

                        if "OK" in answer:
                            result = True

                    #print(answer)

            if not result:
                raise Exception

            server.send_broadcast({"text": {"text": "Modul uspešno sprogramiran!", "tag": "green"}})

            return {"signal": [1, "ok", 2, "NA", ""]}

        except Exception as err:
            print(err)
            server.send_broadcast({"text": {"text": "Programiranje ni uspelo! {}\n".format(err), "tag": "red"}})
            return {"signal": [1, "fail", 2, "NA",""]}


    # Get response from Segger programmer via RS232
    def send_command(self,cmd):
        cmd = '#' + cmd + '\r'
        # eliminate OK from SELECT command
        self.ser.write(cmd.encode("ascii"))

        # Sleep for half a second to send serial commands and get answer
        time.sleep(0.5)

        response = self.get_response()

        return response

    # Get response from Segger programmer via RS232
    def get_response(self):
        out = ''

        while self.ser.inWaiting():
            out += (self.ser.read(size=1)).decode()

        result1 = out.split("#")

        for i in result1:
            if '\r\n' in result1[i]:
                result1[i] = result1[i][0:-4]

        return result1[1:]

    def tear_down(self):
        # Close serial connection with Segger
        self.ser.close()


class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.mesurement_delay = 0.16
        self.measurement_results = {}

        self.i2c = self.use_device('light_panel')
        self.voltmeter = self.use_device('voltmeter')

        # Measure order
        # Expected values imported from definitions
        # Position, Mode (0 - VOLT, 1 - OHM, EXPECTED)
        self.measure_order = {
            (0, 1, self.get_definition("R3")), # R3
            (1, 1, self.get_definition("R4")), # R4
            (2, 1, self.get_definition("R5")), # R5
            (3, 0, self.get_definition("Z1")), # Z1
            (4, 0, self.get_definition("D1")), # D1
            (5, 1, self.get_definition("P1")), # P1
            (6, 1, self.get_definition("R2")), # R2
            (7, 0, self.get_definition("5V")), # 5V
            (8, 1, self.get_definition("R1")), # R1
            (9, 1, self.get_definition("R9")), # R9
            (10,0, self.get_definition("Uvcap")), # Uvcap
            (11,1, self.get_definition("R8")) # R8
        }

        self.tolerance = self.get_definition("tolerance")

        self.arduino_big = devices.Arduino(0x04)
        self.arduino_small = devices.Arduino(0x06)



    def run(self) -> (bool, str):
        # Razklenitev L in N
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        # POTREBNO DISCHARGATI VEZJE

        self.arduino_big.calibrate()

        # for i in self.measure_order:
        # check if measuring is 1 (ohmmeter)
        # measure, check expected value
        # append to measurement result


        # Sklenitev L in N
        GPIO.output(gpios['FAZA'], False)
        GPIO.output(gpios['NULA'], False)

        # for i in self.measure_order:
        # check if measuring is 0 (voltmeter)
        # measure, check expected value
        # append to measurement result

        # Razklenitev L in N
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)


        return {"signal": [1, "ok", 2, "NA", ""]}

    def valmap(self,value, istart, istop, ostart, ostop):
        return ostart + (ostop - ostart) * ((value - istart) / (istop - istart))

    def measure(self,index,type):
        self.arduino_big.MoveStepper(index)
        self.arduino_big.connect()
        measurement = self.arduino.measure()
        self.arduino_big.disconnect()

        return measurement

    def tear_down(self):
        self.arduino_big.disconnect()
        pass
