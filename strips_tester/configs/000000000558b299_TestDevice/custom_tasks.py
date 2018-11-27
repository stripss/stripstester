
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
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays

# DONE
class StartProcedureTask(Task):
    def set_up(self):
        # Initialize NanoBoards
        pass

    def run(self) -> (bool, str):

        for current in range(2):
            strips_tester.product[current].exist = True
            strips_tester.product[current].add_measurement
            strips_tester.product[current].serial = self.configure_serial(current)

        for i in range(10):
            self.server.send_broadcast({"command": "text", "text": "Test poteka...\n", "tag": "black"})
            time.sleep(1)

        return type(self).__name__


    def tear_down(self):

        time.sleep(self.get_definition("end_time"))

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def configure_serial(self,product):
        # Get last ID from DB
        last_test_id = strips_tester.TestDevice_Product.objects.last().test_id

        serial = str(last_test_id) + str(product)
        # Serial should look like 20150 and 20151

        return serial

# ALMOST DONE
# - needs right indicators to light up
class EndProcedureTask(Task):

    def set_up(self):
        # Initialize LightBoard
        pass

    def run(self) -> (bool, str):
        self.server.send_broadcast({"command": "text", "text": "Odprite pokrov in odstranite testirane kose.\n", "tag": "black"})

        time.sleep(2)
        return type(self).__name__

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def tear_down(self):
        GPIO.output(gpios['LOCK'],True)

class VisualTest(Task):

    def set_up(self):
        pass

    def run(self) -> (bool, str):
        time.sleep(5)

        return type(self).__name__

    def tear_down(self):
        pass

class PrintSticker(Task):

    def set_up(self):
        pass

    def run(self):
        self.server.send_broadcast({"command": "text", "text": "Označite kose s pripadajočimi natisnjenimi nalepkami:\n", "tag": "black"})
        pass
        return type(self).__name__

    def tear_down(self):
        pass

class FlashMCU(Task):

    def set_up(self):
        pass

    def run(self) -> (bool, str):
        pass
        return type(self).__name__

    def tear_down(self):
        # Close serial connection with Segger
        pass

class VoltageTest(Task):

    def set_up(self):
        # Initialize Voltmeter
        time.sleep(3)

    def run(self) -> (bool, str):
        pass

        return type(self).__name__

    def tear_down(self):
        pass