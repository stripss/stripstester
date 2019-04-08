
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
        self.lightboard = devices.MCP23017()

        time.sleep(self.get_definition("start_time"))

    def run(self) -> (bool, str):
        GPIO.output(gpios["BUZZER"], True)
        GPIO.output(gpios["VCC"], True)
        GPIO.output(gpios["SIDE"], True)
        GPIO.output(gpios["SERVO"], True)

        time.sleep(0.1)

        # Hide all indicator lights
        self.lightboard.clear_bit(0xFFFF)

        # Working yellow LED lights
        self.lightboard.set_bit(0x0F)

        return type(self).__name__

    def tear_down(self):
        time.sleep(self.get_definition("end_time"))



class EndProcedureTask(Task):

    def set_up(self):
        self.lightboard = devices.MCP23017()

    def run(self) -> (bool, str):

        GPIO.output(gpios["SERVO"], True)


        beep = False
        if strips_tester.product[0].exist:
            if strips_tester.product[0].ok: # Product is bad
                beep = True
                self.lightboard.set_bit(0x02) # Red left light
            else:
                self.lightboard.set_bit(0x01) # Green left light
        else:
            self.lightboard.clear_bit(0x03) # No left light

        if strips_tester.product[1].exist:
            if strips_tester.product[1].ok:  # Product is bad
                beep = True
                self.lightboard.set_bit(0x08)  # Red right light
            else:
                self.lightboard.set_bit(0x04)  # Green right light
        else:
            self.lightboard.clear_bit(0x0C)  # No right light

        if not strips_tester.product[0].exist and not strips_tester.product[1].exist:
            beep = True

        if beep:
            GPIO.output(gpios["BUZZER"],False)
            time.sleep(1)
            GPIO.output(gpios["BUZZER"], True)


        # 0 - off
        # 1 - red
        # 2 - green
        # 3 - yellow

        return type(self).__name__

    def tear_down(self):
        pass








class VoltageTest(Task):

    def set_up(self):
        self.voltmeter = INA219(0.1)
        self.voltmeter.configure()

        self.i2c = devices.MCP23017()

        # Define custom definitions
        self.max_voltage = self.get_definition("max_voltage")
        self.min_voltage = self.get_definition("min_voltage")
        self.tolerance = self.get_definition("tolerance")


    def run(self) -> (bool, str):
        sleep = 0.2

        GPIO.output(gpios["VCC"], False) # Turn VCC ON
        GPIO.output(gpios["SIDE"], False) # Measure other side
        time.sleep(sleep)

        # Predpostavimo, da je servo na 0 (magnet na levi)

        # Measure left voltage with magnet
        voltage = self.voltmeter.voltage()
        if voltage < 1 or voltage > 1.2:
            self.server.send_broadcast({"command": "text", "text": "Zaznan levi kos.\n", "tag": "black"})

            strips_tester.product[0].exist = True

            # Kos obstaja, magnet je pri levem kosu
            if not self.in_range(voltage, self.min_voltage - self.tolerance,self.min_voltage + self.tolerance):
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"})
                strips_tester.product[0].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_WARNING, voltage)
            else:
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"})
                strips_tester.product[0].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_OK, voltage)
        else:
            self.server.send_broadcast({"command": "text", "text": "Ni zaznanega levega kosa.\n", "tag": "grey"})

        # Measure right voltage with no magnet
        GPIO.output(gpios["SIDE"], True)
        time.sleep(sleep)


        voltage = self.voltmeter.voltage()
        if voltage < 1 or voltage > 1.2:  # Means that there is piece and it was fault first time
            self.server.send_broadcast({"command": "text", "text": "Zaznan desni kos.\n", "tag": "black"})

            strips_tester.product[1].exist = True

            if not self.in_range(voltage, self.max_voltage - self.tolerance,self.max_voltage + self.tolerance):
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_WARNING, voltage)
            else:
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_OK, voltage)

        # Premik magneta na desno stran
        GPIO.output(gpios["SERVO"], False)
        time.sleep(2)

        voltage = self.voltmeter.voltage()
        if voltage < 1 or voltage > 1.2:
            self.server.send_broadcast({"command": "text", "text": "Zaznan desni kos.\n", "tag": "black"})

            if not strips_tester.product[1].exist:
                strips_tester.product[1].exist = True
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"})
                self.server.send_broadcast({"command": "text", "text": "Desnemu kosu manjka upor 0R.\n", "tag": "red"})

                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_WARNING, voltage)
            else:
                strips_tester.product[1].exist = True

                if not self.in_range(voltage, self.min_voltage - self.tolerance, self.min_voltage + self.tolerance):
                    self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"})
                    strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_WARNING, voltage)
                else:
                    self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"})
                    strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_OK, voltage)

        else:
            if strips_tester.product[1].exist:  # Means that there is piece and it was fault first time
                self.server.send_broadcast({"command": "text", "text": "Zaznan desni kos.\n", "tag": "black"})

                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"})
                self.server.send_broadcast({"command": "text", "text": "Desnemu kosu manjka upor 0R.\n", "tag": "red"})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_WARNING, voltage)
            else:
                self.server.send_broadcast({"command": "text", "text": "Ni zaznanega desnega kosa.\n", "tag": "grey"})


        if strips_tester.product[0].exist:
            GPIO.output(gpios["SIDE"], False)  # Measure other side
            time.sleep(sleep)
            voltage = self.voltmeter.voltage()

            if not self.in_range(voltage, self.max_voltage - self.tolerance,self.max_voltage + self.tolerance):
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"})
                strips_tester.product[0].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_WARNING, voltage)
            else:
                self.server.send_broadcast({"command": "text", "text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_OK, voltage)

        time.sleep(sleep)

        GPIO.output(gpios["VCC"], True)
        GPIO.output(gpios["SIDE"], True)

        return type(self).__name__

    def in_range(self,voltage,min,max):
        if (min < voltage < max):
            return True
        else:
            return False



    def tear_down(self):
        pass


