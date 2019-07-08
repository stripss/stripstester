import importlib
import logging
import sys
import time
import multiprocessing
import Colorer
import os
import random
import serial
import struct
# import wifi
import RPi.GPIO as GPIO
import devices
from config_loader import *
# sys.path.append("/strips_tester_project/garo/")

from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task  # , connect_to_wifi

import datetime
import numpy as np
from strips_tester import utils
import threading
import random

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
        self.nest_id = 0
    def run(self) -> (bool, str):
        start_switch = "START_SWITCH_1"
        if start_switch in settings.gpios:
            module_logger.info("Za nadaljevanje zapri pokrov")

            gui_web.send({"command": "status", "value": "Za začetek testiranja pritisni tipko."})  # Clear all info messages
            gui_web.send({"command": "progress", "nest": self.nest_id, "value": "0"})

            while True:
                # GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                state_GPIO_SWITCH = GPIO.input(gpios.get(start_switch))
                if not state_GPIO_SWITCH:
                    # module_logger.info("START_SWITCH pressed(lid closed)")
                    break

                time.sleep(0.01)

            for self.nest_id in range(strips_tester.data['test_device_nests']):
                gui_web.send({"command": "progress", "nest": self.nest_id, "value": "25"})
                strips_tester.data['start_time'][self.nest_id] = datetime.datetime.now()  # Get start test date
                gui_web.send({"command": "time", "mode": "start", "nest": self.nest_id})  # Start count for test
                gui_web.send({"command": "error", "nest": self.nest_id, "value": -1})  # Clear all error messages
                gui_web.send({"command": "info", "nest": self.nest_id, "value": -1})  # Clear all info messages

                gui_web.send({"command": "blink", "which": self.nest_id + 1, "value": (0, 0, 0)})
                gui_web.send({"command": "semafor", "which": self.nest_id + 1, "value": (0, 1, 0)})

        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")
        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        pass



# Perform product detection
class InitialTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        strips_tester.data['measurement'][0][type(self).__name__] = {}
        strips_tester.data['measurement'][1][type(self).__name__] = {}
        strips_tester.data['measurement'][2][type(self).__name__] = {}

    def run(self) -> (bool, str):
        for nest_id in range(3):
            self.nest_id = nest_id
            gui_web.send({"command": "status", "value": "Blinkanje LED diod"})  # Clear all info messages
            gui_web.send({"command": "progress", "nest": self.nest_id, "value": "34"})
            for i in range(random.randint(2,30)):
                GPIO.output(gpios['LED_OUT_' + str(self.nest_id + 1)], GPIO.HIGH)
                time.sleep(0.1)
                GPIO.output(gpios['LED_OUT_' + str(self.nest_id + 1)], GPIO.LOW)
                time.sleep(0.1)

            gui_web.send({"command": "progress", "nest": self.nest_id, "value": "69"})
            gui_web.send({"command": "info", "nest": self.nest_id, "value": "Testiranje LED diode"})

            gui_web.send({"command": "status", "value": "Testiranje BLDC motorja"})  # Clear all info messages
            GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.LOW)
            acc = 0.005
            for i in range(3600):
                if acc > 0:
                    acc = acc - 0.00001
                GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.HIGH)
                GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.LOW)
                time.sleep(0.0001 + acc)
            GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.HIGH)
            gui_web.send({"command": "progress", "nest": self.nest_id, "value": "100"})

            gui_web.send({"command": "status", "value": "Konfiguracija..."})  # Clear all info messages
            gui_web.send({"command": "info", "nest": self.nest_id, "value": "Motor BLDC testiran"})
            strips_tester.data['exist'][self.nest_id] = True
            time.sleep(0.5)
        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        pass

class ProductConfigTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("ProductConfigTask init")

    def run(self):
        for self.nest_id in range(3):
            if strips_tester.data['exist'][self.nest_id]:
                if strips_tester.data['status'][self.nest_id] == -1:
                    strips_tester.data['status'][self.nest_id] = random.randint(0,1)

        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        pass

class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):

        for self.nest_id in range(3):
            gui_web.send({"command": "semafor", "which": self.nest_id + 1, "value": (0, 0, 0)})

            if strips_tester.data['exist'][self.nest_id]:
                if strips_tester.data['status'][self.nest_id]:
                    gui_web.send({"command": "semafor", "which": self.nest_id + 1, "value": (0, 0, 1)})
                else:
                    gui_web.send({"command": "semafor", "which": self.nest_id + 1, "value": (1, 0, 0)})
                    gui_web.send({"command": "error", "nest": self.nest_id, "value": "napetost na {} izven obmocja!" . format(self.nest_id + 1)})  # Clear all error messages

        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        pass
