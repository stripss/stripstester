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
        gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        module_logger.info("Waiting for detection switch")

        # Wait for lid to close
        dut_detect = not GPIO.input(gpios['DUT_DETECT'])
        while not self.lid_closed() or not dut_detect:
            dut_detect = not GPIO.input(gpios['DUT_DETECT'])
            time.sleep(0.01)

        # Set on working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)

        strips_tester.data['start_time'][0] = datetime.datetime.utcnow()  # Get start test date
        gui_web.send({"command": "time", "mode": "start", "nest": 0})  # Start count for test

        # Clear GUI
        gui_web.send({"command": "error", "nest": 0, "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "nest": 0, "value": -1})  # Clear all info messages

        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 0, 0)})

        return

    def tear_down(self):
        pass

# Perform product detection
class VisualTest(Task):
    def set_up(self):
        self.safety_check()  # Check if lid is opened
        self.gui_progress = 10
        self.relay_wait = 0.2

    def run(self):
        strips_tester.data['exist'][0] = True  # Replace with DUT detection switch

        gui_web.send({"command": "progress", "nest": 0, "value": self.gui_progress})
        gui_web.send({"command": "status", "nest": 0, "value": "Testiranje sekvenc..."})

        # Output sequence to trigger
        sequence_output = [[1], [2], [2,3], [3], [1,2]]

        # Input sequence to detect
        sequence_input = [[1,4], [2,5], [2,5,3], [3,5], [1,2,6]]

        for current_seq in range(5):
            sequence_result = []

            for current_relay in range(3):
                if current_relay + 1 in sequence_output[current_seq]:
                    GPIO.output(gpios['IN_IV' + str(current_relay + 1)], GPIO.HIGH)
                else:
                    GPIO.output(gpios['IN_IV' + str(current_relay + 1)], GPIO.LOW)

            module_logger.info("Relays {} triggered. Waiting for response ({})..." . format(sequence_output[current_seq], sequence_input[current_seq]))
            time.sleep(self.relay_wait)

            self.gui_progress += 10
            gui_web.send({"command": "progress", "nest": 0, "value": self.gui_progress})

            # Relays are switched, now look for output
            for current_led in range(6):
                led_request = (current_led + 1 in sequence_input[current_seq]) * 1

                gpio_response = (GPIO.input(gpios[custom_data['pin_order'][current_led]])) * 1

                sequence_result.append(gpio_response)

                if gpio_response == led_request:
                    module_logger.info("Input {} is measured {}, needed to be {}. Sequence: {}" . format(current_led, gpio_response, led_request, current_seq))
                    gui_web.send({"command": "info", "nest": 0, "value": "Sekvenca {} ustrezna - {} naj bi imel vrednost {}, izmerjeno {}" . format(current_seq, custom_data['pin_order'][current_led], led_request, gpio_response)})
                    self.add_measurement(0, True, "sek_{}_{}".format(current_seq, custom_data['pin_order'][current_led]), "OK", "")
                else:
                    module_logger.error("Input {} is measured {}, needed to be {}! Sequence: {}" . format(current_led, gpio_response, led_request, current_seq))
                    gui_web.send({"command": "error", "nest": 0, "value": "Sekvenca {} neustrezna - {} naj bi imel vrednost {}, izmerjeno {}" . format(current_seq, custom_data['pin_order'][current_led], led_request, gpio_response)})
                    self.add_measurement(0, False, "sek_{}_{}" . format(current_seq, custom_data['pin_order'][current_led]), "FAIL", "")

            # Shut off all relays
            for current_relay in range(3):
                GPIO.output(gpios['IN_IV' + str(current_relay + 1)], GPIO.LOW)

            time.sleep(self.relay_wait)

            self.gui_progress += 5
            gui_web.send({"command": "progress", "nest": 0, "value": self.gui_progress})
        return

    def tear_down(self):
        for current_relay in range(3):
            GPIO.output(gpios['IN_IV' + str(current_relay + 1)], GPIO.LOW)


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


class PrintSticker(Task):
    def set_up(self):
        self.godex = devices.Godex()

    def run(self):
        if not self.godex.found:
            if strips_tester.data['exist'][0]:
                gui_web.send({"command": "error", "nest": 0, "value": "Tiskalnika ni mogoče najti!"})

            return

        # Lid is now opened.
        if self.is_product_ready(0):
            self.print_sticker(strips_tester.data['status'][0])

        return

    def print_sticker(self, test_status):
        date = datetime.datetime.now()
        date_week = date.strftime("%V/%y")  # Generate calendar week
        date_full = date.strftime("%y%m%d")  # Generate full date

        if test_status == True:  # Test OK
            inverse = '^L\r'
            darkness = '^H4\r'
        elif test_status == False:  # Test FAIL
            inverse = '^LI\r'
            darkness = '^H15\r'
        else:
            return

        datamatrix = '10000002803301111{}93167542' . format(date_full)
        serial = "{:08d}" . format(self.get_new_serial())

        self.add_measurement(0, True, "serial", serial, "")

        label = ('^Q13,3\n'
                '^W38\n'
                '^H4\n'
                '^P1\n'
                '^S2\n'
                '^AD\n'
                '^C1\n'
                '^R0\n'
                '~Q-8\n'
                '^O0\n'
                '^D0\n'
                '^E12\n'
                '~R255\n'
                '^XSET,ROTATION,0\n'
                '^L\n'
                'Dy2-me-dd\n'
                'Th:m:s\n'
                'XRB25,16,4,0,32\n'
                '{}\n'
                'AB,120,24,1,1,0,0E,Gorenje 803301\n'
                'AB,120,49,1,1,0,0E,{}\n'
                'AB,120,74,1,1,0,0E,{}\n'
                'AB,120,0,1,1,0,0E,RELAY CARD\n'
                'E\n').format(datamatrix, date_week, serial)

        self.godex.send_to_printer(label)
        time.sleep(1)

    def tear_down(self):
        self.godex.close()

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
        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0]:
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            else:
                GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        # Wait for lid to open
        while self.lid_closed():
            time.sleep(0.01)

        return

    def tear_down(self):
        pass

