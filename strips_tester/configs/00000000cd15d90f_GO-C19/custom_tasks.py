
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
        self.i2c = self.use_device('light_panel')

        self.start_time = self.get_definition("start_time")
        self.end_time = self.get_definition("end_time")


    def run(self) -> (bool, str):
        time.sleep(self.start_time)

        for i in range(50):
            time.sleep(0.01)
            self.i2c.set_led_status(0xFF)
            time.sleep(0.01)
            self.i2c.set_led_status(0x00)

            # Preklopi releje za sklenitev LED
            # pripelji stepper za branje potenciometrov
            # skleni napetost 230VAC (sklene se tudi 5V, jo tudi izmeri)
            # pomeri se napetost 5V na obeh kosih (ce je uspesno se operacije nadaljujejo) to napetost si zapomni
            # predpostavimo da je kos nesprogramiran (brez LED in podobno)
            # preberi potenciometer (izmeri P1 prva plata)
            # preberi potenciometer (izmeri P1 druga plata)
            # izklopi 230VAC


            # ICT testi kar se tice upornosti
            # upori - meritev padca napetosti skozi vsiljenih 5V


            ### MERITVE MED LIVE         POWER
        # diode - meritev napetosti (0.7V da je ok)
        # kondenzatorji - meritev napetosti

        # zapelji vodilni stepper gor
        # obrni oba potenciometra na 0

        # preklopi bremena za programiranje
            # sprogramiraj prvi kos in nato drugega
            # (kako skleniti vse 4 kontakte s programatorjem?)
            # PROGRAMATOR JE LAHKO VES CAS PRIKLOPLJEN, SAJ JE OPTICNO IZOLIRAN

            # (mogoce da ostane na 230VAC in se ga sprogramira vmes (programator pripelje SWIM in GND na test pinih)

            # preklopi na bremena
            # skleni 230VAC
            # preglej s kamero ledice (obe tiskanine)
            # ce uspe, zavrti potenciometra desno
            # glej da vse ledice zasvetijo
            # razkleni napetost
            # zapelji stepper dol
            # good / bad kos, buzzer



        return {"signal": [1, "ok", 5, "NA",""]}

    def tear_down(self):
        time.sleep(self.end_time)



class EndProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.i2c = devices.MCP23017()
        pass

    def run(self) -> (bool, str):


        if strips_tester.current_product.countbad:
            GPIO.output(gpios["BUZZER"],False)
            time.sleep(1)
            GPIO.output(gpios["BUZZER"], True)

        self.i2c.set_led_status(0xff)
        time.sleep(1)
        self.i2c.set_led_status(0x0f)

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

        self.i2c = devices.MCP23017()

        self.camera = cv2.VideoCapture(0)  # video capture source camera

        self.led = []
        for i in range(6):
            self.led.append({}) # Append dictionary
            self.led[-1]['x'] = self.get_definition("led{}_posx" . format(i + 1))
            self.led[-1]['y'] = self.get_definition("led{}_posy" . format(i + 1))

    def run(self) -> (bool, str):
        try:
            for i in range(5):
                ret, frame = self.camera.read()  # return a single frame in variable `frame`

                roi = frame[50:400, 120: 440]

                # Convert image to grayscale
                gs = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)

                # Set threshold for binary
                threshold = 240

                th, dst = cv2.threshold(gs, threshold, 255, cv2.THRESH_BINARY)

                for i in range(6):
                    self.led[i]['state'] = self.detect_led_state(dst, 80, 140, 5)

                print(self.led)

                time.sleep(0.1)
            #return self.measurement_results
            return {"signal": [1, "ok", 2, "NA",""]}

        except Exception as err:
            server.send_broadcast({"text": {"text": "Napaka interne kamere! {}\n".format(err), "tag": "red"}})
            return {"signal": [1, "fail", 2, "NA",""]}

    def detect_led_state(self, th, x, y, rng):
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
        self.camera.release()




class FlashMCU(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.measurement_results = {}

        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "file" in definition['slug']:
                self.file = definition['value']

        # Segger serial communication configuration

        self.ser = serial.Serial(
            port='/dev/ttyUSB0',
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS
        )


    def run(self) -> (bool, str):
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

        #self.i2c = self.use_device('light_panel')
        #self.stepper = self.use_device('stepper')
        self.voltmeter = self.use_device('voltmeter')

        self.arduino = devices.Arduino(0x05)



    def run(self) -> (bool, str):

        #for i in range(4):
        #    self.arduino.moveStepper(2+i)
        #    self.arduino.connect()
        #    self.arduino.disconnect()

        self.arduino.calibrate()

        #for i in range(100):
        #    volt = self.voltmeter.read()

        #    angle = self.valmap(volt, 0.0, 5.0, 0.0, 180.0)
        #    print(volt)
        #    print(angle)
        #self.arduino.servo1(angle)


        #self.arduino.disconnect()

        '''
        try:

            self.stepper.set_mode(1)
            vin = self.voltmeter.read()
            print("Input voltage: {}V".format(vin))

            for i in range(3,10):
                self.stepper.move(i)

                self.stepper.connect()
                volt = self.voltmeter.read()
                print(volt)
                r1 = 100.58
                if volt:
                    if vin == volt:
                        r2 = 0
                    else:
                        r2 = r1 / ((vin / volt) - 1)
                else:
                    r2 = "inf"

                #r1 = r2 * ((vin - volt) - 1)
                #r2 = r1 * buffer
                print("R = {}kohm" . format(r2))
                self.stepper.disconnect()
                #print(volt)

            self.stepper.set_mode(0)

            
            for a in range(len(moves)):
                self.stepper.set_mode(relay[a])
                #print("Preklop na {}".format(relay[a]))
                self.stepper.move(moves[a])
                #print("Pomik na {}".format(moves[a]))

                if relay[a]:
                    time.sleep(0.06)
                    self.i2c.set_led_status(0xFF)
                    time.sleep(0.06)
                    self.i2c.set_led_status(0x0F)

                self.stepper.connect()
                volt = self.voltmeter.read()
                self.stepper.disconnect()
                print(volt)
            

            return {"signal": [1, "ok", 2, "NA",""]}
        except Exception:
            return {"signal": [1, "fail", 2, "NA",""]}
        '''

        return {"signal": [1, "ok", 2, "NA", ""]}

    def valmap(self,value, istart, istop, ostart, ostop):
        return ostart + (ostop - ostart) * ((value - istart) / (istop - istart))


    def tear_down(self):
        self.arduino.disconnect()
        pass
