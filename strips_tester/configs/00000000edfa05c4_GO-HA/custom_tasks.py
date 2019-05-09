## -*- coding: utf-8 -*-
import importlib
import logging
import sys
import time
import multiprocessing
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import *
from tester import Task
import cv2
import os
import numpy as np
import serial
import threading
import datetime
from ina219 import INA219

gpios = strips_tester.settings.gpios

class StartProcedureTask(Task):
    def set_up(self):
        pass

    def run(self) -> (bool, str):
        strips_tester.data['exist_left'] = True  # Assume it exists
        strips_tester.data['exist_right'] = True  # Assume it exists

        strips_tester.data['status_left'] = -1  # Untested
        strips_tester.data['status_right'] = -1  # Untested

        gui_web.send({"command": "title", "value": "GO-HA 2"})

        if "START_SWITCH" in settings.gpios:
            gui_web.send({"command": "status", "value": "Za testiranje pritisni tipko."})
            gui_web.send({"command": "progress", "value": "0"})

            while True:
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
                if not state_GPIO_SWITCH:
                    break

                time.sleep(0.01)

            gui_web.send({"command": "error", "value": -1})  # Clear all error messages
            gui_web.send({"command": "info", "value": -1})  # Clear all error messages
            gui_web.send({"command": "nests", "value": 2})

            gui_web.send({"command": "status", "value": "Testiranje v teku..."})
            # Set working LED
            GPIO.output(gpios["left_red_led"], True)
            GPIO.output(gpios["left_green_led"], True)
            GPIO.output(gpios["right_red_led"], True)
            GPIO.output(gpios["right_green_led"], True)

            for i in range(2):
                gui_web.send({"command": "blink", "which": i + 1, "value": (0, 0, 0)})
                gui_web.send({"command": "semafor", "which": i + 1, "value": (0, 1, 0)})

        # Move stepper to zero
        arduino = devices.ArduinoSerial('/dev/ttyUSB0', baudrate=9600)
        arduino.write("move 0")
        arduino.close()
        gui_web.send({"command": "progress", "value": "20"})

        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        pass




class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):
        strips_tester.data['result_ok'] = 0
        strips_tester.data['result_fail'] = 0

        for i in range(2):
            gui_web.send({"command": "semafor", "which": i + 1, "value": (0, 0, 0)})
            gui_web.send({"command": "blink", "which": i + 1, "value": (0, 0, 0)})

        # Disable all relays
        GPIO.output(gpios["relay1"], True)
        GPIO.output(gpios["relay2"], True)
        GPIO.output(gpios["relay3"], True)
        GPIO.output(gpios["relay4"], True)

        # Disable all lights
        GPIO.output(gpios["left_red_led"], False)
        GPIO.output(gpios["left_green_led"], False)
        GPIO.output(gpios["right_red_led"], False)
        GPIO.output(gpios["right_green_led"], False)

        gui_web.send({"command": "progress", "value": "100"})

        if strips_tester.data['exist_left']:
            if strips_tester.data['status_left'] == 1:  # test ok
                strips_tester.data['result_ok'] += 1

                # Turn left green on
                GPIO.output(gpios["left_green_led"], True)
                gui_web.send({"command": "semafor", "which": 1, "value": (0, 0, 1)})
            elif strips_tester.data['status_left'] == 0:  # test fail
                strips_tester.data['result_fail'] += 1

                GPIO.output(gpios["left_red_led"], True)
                gui_web.send({"command": "semafor", "which": 1, "value": (1, 0, 0)})

        if strips_tester.data['exist_right']:
            if strips_tester.data['status_right'] == 1:  # test ok
                strips_tester.data['result_ok'] += 1

                # Turn right green on
                GPIO.output(gpios["right_green_led"], True)
                gui_web.send({"command": "semafor", "which": 2, "value": (0, 0, 1)})
            elif strips_tester.data['status_right'] == 0:  # test fail
                strips_tester.data['result_fail'] += 1

                GPIO.output(gpios["right_red_led"], True)
                gui_web.send({"command": "semafor", "which": 2, "value": (1, 0, 0)})
        time.sleep(1)

        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        pass


class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = INA219(0.1)
        self.voltmeter.configure()
        self.measurement_results = {}

    def run(self) -> (bool, str):
        gui_web.send({"command": "progress", "value": "10"})
        GPIO.output(gpios["relay1"], False) # Measure left side
        GPIO.output(gpios["relay2"], False) # Turn VCC ON
        GPIO.output(gpios["relay3"], True)
        GPIO.output(gpios["relay4"], True) # Measure left side
        normal_left_off = self.measure()
        GPIO.output(gpios["relay3"], False) # Measure left side
        hall_left_off = self.measure()
        gui_web.send({"command": "progress", "value": "20"})

        GPIO.output(gpios["relay1"], True) # Measure left side
        GPIO.output(gpios["relay4"], False) # Measure left side
        hall_right_on = self.measure()
        gui_web.send({"command": "progress", "value": "30"})
        GPIO.output(gpios["relay3"], True) # Measure left side
        normal_right_on = self.measure()
        gui_web.send({"command": "progress", "value": "40"})

        # Move stepper to end
        arduino = devices.ArduinoSerial('/dev/ttyUSB0', baudrate=9600)
        arduino.write("move 5000")
        arduino.close()

        normal_right_off = self.measure()
        gui_web.send({"command": "progress", "value": "50"})
        GPIO.output(gpios["relay3"], False) # Measure left side
        hall_right_off = self.measure()
        gui_web.send({"command": "progress", "value": "60"})

        GPIO.output(gpios["relay4"], True) # Measure left side
        GPIO.output(gpios["relay1"], False) # Measure right side
        hall_left_on = self.measure()
        gui_web.send({"command": "progress", "value": "70"})

        GPIO.output(gpios["relay3"], True) # Measure left side
        normal_left_on = self.measure()
        gui_web.send({"command": "progress", "value": "80"})

        GPIO.output(gpios["relay2"], True) # Turn VCC FF

        gui_web.send({"command": "progress", "value": "90"})

        if 0.5 < hall_left_off < 1 and 0.5 < hall_left_on < 1 and 4.0 < normal_left_off < 5.0 and 4.5 < normal_left_on < 5.0:
            strips_tester.data['exist_left'] = False

        if 0.5 < hall_right_off < 1 and 0.5 < hall_right_on < 1 and 4.5 < normal_right_off < 5.0 and 4.5 < normal_right_on < 5.0:
            strips_tester.data['exist_right'] = False

        if strips_tester.data['exist_left']:
            strips_tester.data['status_left'] = 1

            if self.in_range(normal_left_off,4.5,1,False):
                self.measurement_results["normal_left_off"] = [normal_left_off, "ok", 0, "V"]
                gui_web.send({"command": "info", "value": "Meritev napetosti levega hall senzorja brez magneta: {}V\n".format(normal_left_off)})
            else:
                gui_web.send({"command": "error", "value": "Meritev napetosti levega hall senzorja brez magneta: {}V\n".format(normal_left_off)})
                self.measurement_results["normal_left_off"] = [normal_left_off, "fail", 0, "V"]
                strips_tester.data['status_left'] = 0

            if self.in_range(normal_left_on,0,0.5,False):
                self.measurement_results["normal_left_on"] = [normal_left_on, "ok", 0, "V"]
                gui_web.send({"command": "info", "value": "Meritev napetosti levega hall senzorja v okolici magneta: {}V\n".format(normal_left_on)})
            else:
                gui_web.send({"command": "error", "value": "Meritev napetosti levega hall senzorja v okolici magneta: {}V\n".format(normal_left_on)})
                self.measurement_results["normal_left_on"] = [normal_left_on, "fail", 0, "V"]
                strips_tester.data['status_left'] = 0

        if strips_tester.data['exist_right']:
            strips_tester.data['status_right'] = 1

            if self.in_range(normal_right_off,4.5,1,False):
                self.measurement_results["normal_right_off"] = [normal_right_off, "ok", 0, "V"]
                gui_web.send({"command": "info", "value": "Meritev napetosti desnega hall senzorja brez magneta: {}V\n".format(normal_right_off)})
            else:
                gui_web.send({"command": "error", "value": "Meritev napetosti desnega hall senzorja brez magneta: {}V\n".format(normal_right_off)})
                self.measurement_results["normal_right_off"] = [normal_right_off, "fail", 0, "V"]
                strips_tester.data['status_right'] = 0

            if self.in_range(normal_right_on,0,0.5,False):
                self.measurement_results["normal_right_on"] = [normal_right_on, "ok", 0, "V"]
                gui_web.send({"command": "info", "value": "Meritev napetosti desnega hall senzorja v okolici magneta: {}V\n".format(normal_right_on)})
            else:
                gui_web.send({"command": "error", "value": "Meritev napetosti desnega hall senzorja v okolici magneta: {}V\n".format(normal_right_on)})
                self.measurement_results["normal_right_on"] = [normal_right_on, "fail", 0, "V"]
                strips_tester.data['status_right'] = 0

        return self.measurement_results

    def tear_down(self):
        pass

    def measure(self,tag = "none"):
        sleep = 0.2
        time.sleep(sleep)
        voltage = self.voltmeter.voltage()
        #print("{}: {}V" . format(tag,voltage))
        return voltage

    def in_range(self, value, expected, tolerance, percent=True):
        if percent:
            tolerance_min = expected - expected * (tolerance / 100.0)
            tolerance_max = expected + expected * (tolerance / 100.0)
        else:
            tolerance_min = expected - tolerance
            tolerance_max = expected + tolerance

        if value > tolerance_min and value < tolerance_max:
            return True
        else:
            return False