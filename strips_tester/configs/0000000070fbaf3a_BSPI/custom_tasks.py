import RPi.GPIO as GPIO
import devices
from config_loader import *

from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task, timeout

import datetime
import numpy as np
from strips_tester import utils
import threading
import random

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays
custom_data = strips_tester.settings.custom_data


# You may set global test level and logging level in config_loader.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)


class StartProcedureTask(Task):
    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "value": "Za začetek testiranja vstavi kos.", "nest": self.nest_id})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "0"})

        module_logger.info("Waiting for detection switch")

        while not self.lid_closed():
            time.sleep(0.01)

        # Set working light on
        shifter = LED_Indicator()
        shifter.set(int(custom_data['led_green_' + str(self.nest_id + 1)], 16))
        shifter.set(int(custom_data['led_red_' + str(self.nest_id + 1)], 16))

        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "25"})
        strips_tester.data['start_time'][self.nest_id] = datetime.datetime.utcnow()  # Get start test date
        gui_web.send({"command": "time", "mode": "start", "nest": self.nest_id})  # Start count for test
        gui_web.send({"command": "error", "nest": self.nest_id, "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "nest": self.nest_id, "value": -1})  # Clear all info messages

        gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (0, 1, 0), "blink": (0, 0, 0)})

        time.sleep(1)  # Delay for DUT insertion

        return

    def tear_down(self):
        pass



class LED_Indicator:
    # This is custom class for Photointerrupter. Due to the concurrency, we must sync nests to signal LED lights via Shifter

    def __init__(self):
        strips_tester.data['lock'].acquire()  # Concurrency writing
        try:
            strips_tester.data['shifter']
        except KeyError:
            strips_tester.data['shifter'] = 0x00

        strips_tester.data['lock'].release()

    def set(self, mask):
        strips_tester.data['lock'].acquire()  # Concurrency writing
        strips_tester.data['shifter'] = strips_tester.data['shifter'] | mask  # Assign shifter global memory
        #print("set {} to {}" . format(mask,strips_tester.data['shifter']))
        self.shiftOut()
        strips_tester.data['lock'].release()

    def clear(self, mask):
        strips_tester.data['lock'].acquire()  # Concurrency writing
        strips_tester.data['shifter'] = strips_tester.data['shifter'] & ~mask  # Assign shifter global memory
        self.shiftOut()
        strips_tester.data['lock'].release()

    def byte_to_binary(self, n):
        return ''.join(str((n & (1 << i)) and 1) for i in reversed(range(8)))

    def shiftOut(self):
        GPIO.output(gpios['OE'], 1)
        GPIO.output(gpios['LATCH'], 0)

        byte = self.byte_to_binary(strips_tester.data['shifter'])
        for x in range(8):
            GPIO.output(gpios['DATA'], int(byte[x]))
            GPIO.output(gpios['CLOCK'], 1)
            GPIO.output(gpios['CLOCK'], 0)

        GPIO.output(gpios['LATCH'], 1)

# Perform product detection
class InitialTest(Task):
    def set_up(self):
        pass

    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "nest": self.nest_id, "value": "Test preklopov stikala"})  # Clear all info messages
        interrupt = 0

        GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.LOW)
        GPIO.output(gpios['DIR_' + str(self.nest_id + 1)], GPIO.LOW)

        old_state = GPIO.input(gpios.get('SIGNAL_' + str(self.nest_id + 1)))

        module_logger.info("Stepper motor begin to trigger interrupts")
        debounce_step = 0

        for steps in range(3000):
            state = GPIO.input(gpios.get('SIGNAL_' + str(self.nest_id + 1)))

            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.HIGH)
            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.LOW)
            time.sleep(0.0001)

            # Distance between gear teeth - so and strings from plastic do not trigger switch. Also serves as debounce
            dist_between_gear = 10
            num_of_interrupts = 10
            if not old_state and state:
                if abs(debounce_step - steps) > dist_between_gear:

                    interrupt += 1

                    if interrupt == num_of_interrupts:
                        break

                    debounce_step = steps

            old_state = state
        GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.HIGH)

        module_logger.info("Trigger interrupts done")

        strips_tester.data['exist'][self.nest_id] = True

        if interrupt > 5:
            module_logger.info("Switches OK, detected {}" . format(interrupt))
            self.add_measurement(self.nest_id, True, "switches", interrupt, "")
            gui_web.send({"command": "info", "nest": self.nest_id, "value": "Preklopi OK. ({})" . format(interrupt)})
        else:
            module_logger.error("Switches FAIL, detected {}" . format(interrupt))
            self.add_measurement(self.nest_id, False, "switches", interrupt, "")
            gui_web.send({"command": "error", "nest": self.nest_id, "value": "Nezadostno število preklopov! ({})" . format(interrupt)})

        return

    def tear_down(self):
        pass


class ProductConfigTask(Task):
    def set_up(self):
        pass

    def run(self):
        if strips_tester.data['exist'][self.nest_id]:
            if strips_tester.data['status'][self.nest_id] == -1:
                strips_tester.data['status'][self.nest_id] = True

        return

    def tear_down(self):
        pass

class Calibration(Task):
    def set_up(self):
        pass

    def run(self):
        module_logger.info("Calibration of stepper motor")
        offset = 100
        GPIO.output(gpios['DIR_' + str(self.nest_id + 1)], GPIO.HIGH)  # Reverse stepper direction

        GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.LOW)

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=2)  # 2 seconds timeout
        while GPIO.input(gpios['LIMIT_' + str(self.nest_id + 1)]):
            if datetime.datetime.now() > end_time:
                module_logger.error("Stepper cannot be calibrated! Reached timeout of 2 seconds")

                gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (1, 0, 0), "blink": (1, 0, 0)})
                gui_web.send({"command": "error", "nest": self.nest_id, "value": "Kalibracija motorja ni uspela!"})

                break

            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.HIGH)
            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.LOW)

            time.sleep(0.0001)

        GPIO.output(gpios['DIR_' + str(self.nest_id + 1)], GPIO.LOW)  # Reverse stepper direction
        for i in range(offset):
            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.HIGH)
            GPIO.output(gpios['STEP_' + str(self.nest_id + 1)], GPIO.LOW)
            time.sleep(0.00015)

        GPIO.output(gpios['ENABLE_' + str(self.nest_id + 1)], GPIO.HIGH)

        module_logger.info("Calibration done")

    def tear_down(self):
        pass

class FinishProcedureTask(Task):
    def set_up(self):
        pass

    def run(self):
        gui_web.send({"command": "status", "nest": self.nest_id, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "90"})

        gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (0, 0, 0)})

        shifter = LED_Indicator()
        shifter.clear(int(custom_data['led_green_' + str(self.nest_id + 1)], 16))
        shifter.clear(int(custom_data['led_red_' + str(self.nest_id + 1)], 16))

        if strips_tester.data['exist'][self.nest_id]:
            if strips_tester.data['status'][self.nest_id]:
                shifter.set(int(custom_data['led_green_' + str(self.nest_id + 1)], 16))
                gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (0, 0, 1)})
            else:
                shifter.set(int(custom_data['led_red_' + str(self.nest_id + 1)], 16))
                gui_web.send({"command": "semafor", "nest": self.nest_id, "value": (1, 0, 0)})

        gui_web.send({"command": "progress", "nest": self.nest_id, "value": "100"})

        module_logger.info("Waiting for product to be removed")

        while self.lid_closed():
            time.sleep(0.01)

        time.sleep(1)
        return

    def tear_down(self):
        pass

