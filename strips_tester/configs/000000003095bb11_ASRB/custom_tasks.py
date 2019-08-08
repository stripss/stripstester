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
        while not self.lid_closed():
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
            time.sleep(1)

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

            time.sleep(1)

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
        self.godex_found = False
        for i in range(10):
            try:
                self.godex = devices.GoDEXG300(port='/dev/godex', timeout=3.0)
                self.godex_found = True
                break
            except Exception as ee:
                print(ee)

                time.sleep(0.1)

        #self.godex = devices.Godex(port='/dev/usb/lp0', timeout=3.0)

    def run(self):
        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        if not self.godex_found:
            if strips_tester.data['exist'][0]:
                gui_web.send({"command": "error", "nest": 0, "value": "Tiskalnika ni mogoče najti!"})

            return

        # Lid is now opened.
        if strips_tester.data['exist'][0]:
            self.print_sticker(strips_tester.data['status'][0])

        return

    def print_sticker(self, test_status):
        qc_id = strips_tester.data['worker_id']

        date = datetime.datetime.now().strftime("%d.%m.%Y")

        if test_status == True:  # Test OK
            inverse = '^L\r'
            darkness = '^H15\r'
        elif test_status == False:  # Test FAIL
            inverse = '^LI\r'
            darkness = '^H4\r'
        else:
            return

        qc = "QC {}".format(strips_tester.data['worker_id'])

        label = ('^Q9,3\n'
                 '^W21\n'
                 '{}'
                 '^P1\n'
                 '^S2\n'
                 '^AD\n'
                 '^C1\n'
                 '^R12\n'
                 '~Q+0\n'
                 '^O0\n'
                 '^D0\n'
                 '^E12\n'
                 '~R200\n'
                 '^XSET,ROTATION,0\n'
                 '{}'
                 'Dy2-me-dd\n'
                 'Th:m:s\n'
                 'AA,8,10,1,1,0,0E,ID:{}     {}\n'
                 'AA,8,29,1,1,0,0E,C-19_PL_UF_{}\n'
                 'AA,8,48,1,1,0,0E,{}  {}\n'
                 'E\n').format(darkness, inverse, " ", " ", " ", date, qc)

        self.godex.send_to_printer(label)
        time.sleep(1)

    def tear_down(self):
        if self.godex_found:
            self.godex.close()

class FinishProcedureTask(Task):
    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):
        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 1, 0)})
        gui_web.send({"command": "status", "nest": 0, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": 0, "value": "90"})

        while self.lid_closed():
            time.sleep(0.01)

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


        return

    def tear_down(self):
        pass

