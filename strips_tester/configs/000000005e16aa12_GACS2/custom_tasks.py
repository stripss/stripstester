import importlib
import logging
import sys
import time
import multiprocessing

import serial
import struct
#import wifi
import RPi.GPIO as GPIO
import devices
from config_loader import *
# sys.path.append("/strips_tester_project/garo/")
from .garo.stm32loader import CmdException
# from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task #, connect_to_wifi
from .garo import Flash
from datetime import datetime
import numpy as np
import strips_tester.postgr


module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays


# You may set global test level and logging level in config_loader.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)


# checks if lid is opened
# prevents cyclic import, because gpios aren't available on import time
class LidOpenCheck:
    def __init__(self):
        # if lid is opened
        state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
        if not state_GPIO_SWITCH:
            module_logger.error("Lid opened /")
            strips_tester.current_product.task_results.append(False)
            strips_tester.emergency_break_tasks = True
        else:
            module_logger.debug("Lid closed")


class BarCodeReadTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        #self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        #self.reader = devices.Honeywell1400(path="/dev/hidraw2", max_code_length=50)
        self.camera_device = devices.CameraDevice(Xres=640, Yres=480)
        self.meshloader = devices.MeshLoaderToList('/strips_tester_project/strips_tester/configs/0000000005e16aa11_MVC2/Mask.json')

    def run(self) -> (bool, str):
        module_logger.info("Prepared for reading matrix code:")
        # global current_product
        #raw_scanned_string = self.reader.wait_for_read() # use scanned instead of camera
        module_logger.info("Code read successful")
        #img = self.camera_device.take_one_picture()
        #center = self.meshloader.matrix_code_location["center"]
        #width = self.meshloader.matrix_code_location["width"]
        #height = self.meshloader.matrix_code_location["height"]
        #raw_scanned_string = utils.decode_qr(img[center[0]-height//2:center[0]+height//2+1, center[1]-width//2:center[1]+width//2+1, :]) # hard coded, add feature to mesh generator
        #strips_tester.current_product.raw_scanned_string = raw_scanned_string
        strips_tester.current_product.raw_scanned_string = 'M1706080087500004S2401877'
        module_logger.debug("%s", strips_tester.current_product)
        GPIO.output(gpios["LIGHT_GREEN"], G_LOW)

        return {"signal":[1, "ok", 5, "NA"]}

    def tear_down(self):
        self.camera_device.close()


class ProductConfigTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)
        # global produt data structure defined in tester. Configure the product here for later use and write do DB
        self.product = strips_tester.current_product

    def run(self) -> (bool, str):
        serial = self.parse_2017_raw_scanned_string()
        if serial:
            self.product.serial = serial
            self.product.save()
            return {"signal": [1, "ok", 5, "NA"]}
        else:
            return {"signal": [0, "fail", 5, "NA"]}

    def to_product_production_datetime(self, year: int = 2017, month: int = 1, day: int = 1):
        self.product.production_datetime = datetime.now()
        self.product.production_datetime.replace(year=(2000+year), month=month, day=day)
        self.product.save()

    def parse_2017_raw_scanned_string(self):
        """ example:
        M 170607 00875 000 04 S 2401877
        M = oznaka za material
        170607 = datum: leto, mesec, dan
        00875 = pet mestna serijska številka – števec, ki se za vsako tiskanino povečuje za 1
        000 = trimestna oznaka, ki se bo v prihodnosti uporabljala za nastavljanje stroja za valno spajkanje, po potrebi pa tudi kaj drugega
        04 = število tiskanin v enem panelu – podatek potrebuje iWare
        S = oznako potrebuje iWare za označevanje SAOP kode
        2401877 =  SAOP koda tiskanine"""

        def create_4B_serial(year, month, day, five_digit_serial):
            day_number = day - 1 + (month - 1) * 31 + year * 366
            day_number %= 2 ** 14  # wrap around every 44 years
            part_1 = day_number << 18
            part_2 = five_digit_serial
            serial = part_1 | part_2
            return serial

        if not self.product.raw_scanned_string:
            logging.error("Not scanned yet!")
            return False
        else:
            ss = self.product.raw_scanned_string
            self.to_product_production_datetime(year=int(ss[1:3]), month=int(ss[3:5])+1,day=int(ss[5:7]))
            serial = self.product.type << 32 | create_4B_serial(int(ss[1:3]), int(ss[3:5]), int(ss[5:7]), int(ss[7:12]))
            return serial

    def tear_down(self):
        pass


class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def run(self) -> (bool, str):
        if "START_SWITCH" in settings.gpios:
            module_logger.info("Waiting for START_SWITCH...")
            while True:
                # GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
                if state_GPIO_SWITCH:
                    module_logger.info("START_SWITCH pressed(lid closed)")
                    break
                time.sleep(0.1)
        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")
        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        pass


class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.mesurement_delay = 0.14
        self.measurement_results = {}
        self.voltmeter = devices.YoctoVoltageMeter(self.mesurement_delay)

    def run(self) -> (bool, str):
        #Vc
        self.relay_board.close_relay(relays["Vc"])
        if self.voltmeter.in_range(13.5, 16.5):
            self.measurement_results['Vc'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['Vc'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["Vc"])
        # 12V
        self.relay_board.close_relay(relays["12V"])
        if self.voltmeter.in_range(11, 13):
            self.measurement_results['12V'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['12V'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["12V"])
        # 5V
        self.relay_board.close_relay(relays["5V"])
        if self.voltmeter.in_range(4.5, 5.5):
            self.measurement_results['5V'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['5V'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["5V"])
        # 3V3
        self.relay_board.close_relay(relays["3V3"])
        if self.voltmeter.in_range(3.0, 3.8):
            self.measurement_results['3V3'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['3V3'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["3V3"])

        LidOpenCheck()
        return self.measurement_results

    def tear_down(self):
        self.voltmeter.close()
        self.relay_board.hid_device.close()


class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("FinishProcedureTask init")
        self.relay_board = devices.SainBoard16(0x0416, 0x5020, initial_status=0x0000)

    def run(self):
        strips_tester.current_product.test_status = all(strips_tester.current_product.task_results) and len(strips_tester.current_product.task_results)
        if strips_tester.current_product.test_status:
            GPIO.output(gpios["LIGHT_GREEN"], G_HIGH)
            module_logger.debug("LIGHT_GREEN ON")
        else:
            self.relay_board.close_relay(relays["LIGHT_RED"])
            module_logger.debug("LIGHT_RED ON")

        return {"signal":[1, 'ok', 0, 'NA']}

    def tear_down(self):
        self.relay_board.close()


class PrintSticker(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.g = devices.GoDEXG300(port='/dev/ttyUSB0', timeout=3.0)

    def run(self):
        label=('^Q10,3\r'
                '^W21\r'
                '^H5\r'
                '^P1\r'
                '^S2\r'
               '^AD\r'
               '^C1\r'
               '^R0\r'
               '~Q+0\r'
               '^O0\r'
               '^D0\r'
               '^E12\r'
               '~R200\r'
               '^XSET,ROTATION,0\r'
               '^L\r'
               'Dy2-me-dd\r'
               'Th:m:s\r'
               'XRB115,14,3,0,{}\r'
               '{}\r'
               'ATC,13,43,14,14,0,0E,C,0,{}, fw{}\r'
               'ATA,17,13,25,25,0,0E,A,0,{}\r'
               'ATC,12,63,14,14,0,0E,C,0,SN {}\r'
               'E\r').format(len(str(strips_tester.current_product.serial)),
                            strips_tester.current_product.serial,
                            strips_tester.current_product.product_name,
                            strips_tester.current_product.hw_release,
                            "PASS" if strips_tester.current_product.test_status else "FAIL",
                            hex(strips_tester.current_product.serial))
        self.g.send_to_printer(label)
        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        self.g.close()


class GACSTestLed(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        pass

    def run(self):
        try:
            devices.MCP23017.test_led()
        except Exception as ee:
            module_logger.debug("Exception  % s in %s.", ee, type(self).__name__)
            return ("LED", 0, "fail", 1, "bool")

        # user_key = input("Press S if LED ok :  ")
        # if user_key.lower() == 's':
        module_logger.info("PRITISNI ZELENI GUMB ČE SO LED OK, RDEČI GUMB V PRIMERU NAPAKE")
        return ("LED", 1, "ok", 1, "bool")

    def tear_down(self):
        pass

