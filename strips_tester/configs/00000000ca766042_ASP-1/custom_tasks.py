import RPi.GPIO as GPIO
import devices
from config_loader import *

from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task, timeout

import datetime
import numpy as np

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays
custom_data = strips_tester.settings.custom_data


class StartProcedureTask(Task):
    def run(self) -> (bool, str):
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        module_logger.info("Waiting for detection switch")

        # Wait for selection of program
        while True:
            try:
                strips_tester.data['program']
                break
            except KeyError:
                time.sleep(0.1)

        gui_web.send({"command": "status", "nest": 0, "value": "Za začetek testa priklopi modul"})
        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})

        # Wait for lid to close
        while self.lid_closed():
            time.sleep(0.01)

        time.sleep(0.5)

        # Assume that product exists, because the start switch is made this way
        strips_tester.data['exist'][0] = True

        # Set on working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)

        strips_tester.data['start_time'][0] = datetime.datetime.utcnow()  # Get start test date
        gui_web.send({"command": "time", "mode": "start", "nest": 0})  # Start count for test

        # Clear GUI
        gui_web.send({"command": "error", "nest": 0, "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "nest": 0, "value": -1})  # Clear all info messages

        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 0, 0)})

        # Set relays to NO
        GPIO.output(gpios['12V_AC'], GPIO.LOW)
        GPIO.output(gpios['12V_DC'], GPIO.LOW)
        GPIO.output(gpios['24V_AC'], GPIO.LOW)
        GPIO.output(gpios['24V_DC'], GPIO.LOW)
        GPIO.output(gpios['48V_AC'], GPIO.LOW)
        GPIO.output(gpios['48V_DC'], GPIO.LOW)

        return

    def tear_down(self):
        pass


class ReadSerial(Task):
    def set_up(self):
        pass

    def run(self):
        pass
        return

    def tear_down(self):
        pass


class PowerTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B572.voltage1", 0.16)
        self.ammeter = devices.YoctoVoltageMeter("YAMPMK01-EC255.current1", 0.16)
        pass

    def run(self):
        time.sleep(0.2)  # Relay debouncing

        if "12V" in strips_tester.data['program'][1]:
            GPIO.output(gpios['12V_DC'], GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpios['12V_AC'], GPIO.HIGH)
        elif "24V" in strips_tester.data['program'][1]:
            GPIO.output(gpios['24V_DC'], GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpios['24V_AC'], GPIO.HIGH)
        else:  # Assume it is 48V
            GPIO.output(gpios['48V_DC'], GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpios['48V_AC'], GPIO.HIGH)

        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje napetosti"})

        # Measure voltage
        num_of_tries = 5

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 12, 0.1, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Voltage is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti je izven območja: {}V".format(voltage)})
            self.add_measurement(0, False, "Voltage", voltage, "V")
        else:
            module_logger.info("Voltage in bounds: meas: %sV", voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti: {}V".format(voltage)})
            self.add_measurement(0, True, "Voltage", voltage, "V")

        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje toka"})

        # Measure current
        num_of_tries = 5

        currents = [int(s) for s in strips_tester.data['program'][2].split() if s.isdigit()]
        min_current = currents[0]
        max_current = currents[1]

        expected = (min_current + max_current) / 2
        tolerance = abs(min_current - max_current) / 2

        current = self.ammeter.read()
        while not self.in_range(current, expected, tolerance, False):
            num_of_tries = num_of_tries - 1

            current = self.ammeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Current is out of bounds: meas: %smA", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev toka je izven območja: {}mA".format(current)})
            self.add_measurement(0, False, "Current", current, "mA")
        else:
            module_logger.info("Current in bounds: meas: %smA", voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev toka: {}mA".format(current)})
            self.add_measurement(0, True, "Current", current, "V")

        return

    def tear_down(self):
        pass


class ProductConfigTask(Task):
    def set_up(self):
        module_logger.debug("ProductConfigTask init")

    def run(self):
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == -1:  # If product is marked as untested
                strips_tester.data['status'][0] = True

        return

    def tear_down(self):
        pass


class FinishProcedureTask(Task):
    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):
        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 1, 0)})
        gui_web.send({"command": "status", "nest": 0, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": 0, "value": "90"})

        # Set off working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.LOW)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.LOW)
        GPIO.output(gpios['BUZZER'], GPIO.HIGH)
        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0]:
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            else:
                GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        time.sleep(1)

        GPIO.output(gpios['BUZZER'], GPIO.LOW)

        # Set relays to NO
        GPIO.output(gpios['12V_AC'], GPIO.LOW)
        GPIO.output(gpios['12V_DC'], GPIO.LOW)
        GPIO.output(gpios['24V_AC'], GPIO.LOW)
        GPIO.output(gpios['24V_DC'], GPIO.LOW)
        GPIO.output(gpios['48V_AC'], GPIO.LOW)
        GPIO.output(gpios['48V_DC'], GPIO.LOW)

        # Wait for lid to open
        while not self.lid_closed():
            time.sleep(0.01)

        return

    def tear_down(self):
        pass
