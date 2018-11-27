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
#from .garo.stm32loader import CmdException
# from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task #, connect_to_wifi
from datetime import datetime
import numpy as np
#import strips_tester.postgrž

import cv2

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
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.open_all_relays()

    def run(self) -> (bool, str):
        if "START_SWITCH" in settings.gpios:
            module_logger.debug("Za nadaljevanje zapri pokrov")

            while True:
                # GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))

                if state_GPIO_SWITCH:
                    #module_logger.info("START_SWITCH pressed(lid closed)")
                    break
                time.sleep(0.1)
        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")
        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        self.relay_board.hid_device.close()






class ProductConfigTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)
        # global produt data structure defined in tester. Configure the product here for later use and write do DB
        self.product = strips_tester.current_product

    def run(self) -> (bool, str):
        if self.parse_2017_raw_scanned_string():
            return {"signal": [1, "ok", 5, "NA"]}
        else:
            return {"signal": [0, "fail", 5, "NA"]}

    def to_product_production_datetime(self, year: int = 2017, month: int = 1, day: int = 1):
        self.product.production_datetime = datetime.now()
        self.product.production_datetime.replace(year=(2000+year), month=month, day=day)


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
            # DO TEGA NE MORE PRITI, SAJ SE AVTOMATSKO SKENIRA KODA
            return False
        else:
            ss = self.product.raw_scanned_string

            self.to_product_production_datetime(year=int(ss[1:3]), month=int(ss[3:5]),day=int(ss[5:7]))
            self.product.serial = self.product.type.type << 32 | create_4B_serial(int(ss[1:3]), int(ss[3:5]), int(ss[5:7]), int(ss[7:12]))
            return True

    def tear_down(self):
        pass







class BarCodeReadTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):

        # powering up board meanwhile
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        GPIO.output(gpios["INTERIOR_LED"], G_LOW)

        print("Try to open camera")
        print("Hint: init camera at start for better performance?")
        vc = cv2.VideoCapture(0)


        while(vc.isOpened() == 0):  # try to get the first frame
            vc = cv2.VideoCapture(0)
            print("Connecting...")
            time.sleep(1)
        print("Camera opened")



        GPIO.output(gpios["INTERIOR_LED"], G_LOW)
        time.sleep(1)

        rval, frame = vc.read()
        #tim_start = time.clock()

        raw_scanned_string = ""
        from pylibdmtx.pylibdmtx import decode

        while(len(raw_scanned_string) == 0):
            rval, frame = vc.read()

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            res = cv2.inRange(hsv, np.array([0, 0, 80]), np.array([255, 150, 260]))
            res = cv2.bitwise_not(res)
            result = self.rotateImage(res, 70)
            roi = result[150:410, 190:440]
            cv2.imwrite("scanned_datamatrix.jpg",roi)

            print("Start decoding")
            raw_scanned_string = decode(roi)

            print("Decoded")
        #print("It took {} seconds".format(time.clock() - tim_start))
        print(raw_scanned_string)

        # Save successfully read image
        cv2.imwrite("scanned_datamatrix.jpg",roi)
        vc.release()
        GPIO.output(gpios["INTERIOR_LED"], G_HIGH)

        # Assign scanned string to strips_tester class

        raw_scanned_string = str(raw_scanned_string[0].data)[2:len(str(raw_scanned_string[0].data))-1]

        strips_tester.current_product.raw_scanned_string = raw_scanned_string

        # NAPISI TRY... CE NE USPE V 5X POSKUSIH RETURN FAIL ELSE RETURN TRUE + RAW SCANNED STRING
        # strips_tester.current_product.raw_scanned_string = 'M1806080087500004S2401877'

        return {"signal":[1, "ok", 5, "NA"]}



    def rotateImage(self,image, angle):
        image_center = tuple(np.array(image.shape[1::-1]) / 2)
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
        return result



    def tear_down(self):
        self.relay_board.open_relay(relays["Power"])
        self.relay_board.hid_device.close()






'''

class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.mesurement_delay = 0.16
        self.measurement_results = {}
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.mesurement_delay)

        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):

        # Test 12V
        module_logger.info("Testiranje 12V...")
        self.relay_board.close_relay(relays["12V"])
        time.sleep(0.2)

        if self.voltmeter.in_range(11.5,12.5):
            self.measurement_results['12V'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['12V'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["12V"])



        # Test 3.3V
        module_logger.info("Testiranje 3V3...")
        self.relay_board.close_relay(relays["3V3"])
        time.sleep(0.2)
        if self.voltmeter.in_range(3.0,3.6):
            self.measurement_results['3V3'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['3V3'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["3V3"])

        module_logger.info("Testiranje napetosti koncano.")
        print(self.measurement_results)

        return self.measurement_results

    def tear_down(self):
        self.relay_board.open_relay(relays["Power"])
        self.voltmeter.close()
        self.relay_board.hid_device.close()







class GACSTest(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.measurement_delay = 0.16
        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.measurement_delay)
        self.ampermeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", self.measurement_delay)
        self.temp_sensor = devices.LM75A(0)
        self.i2c = devices.MCP23017()

        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])

    def run(self):
        try:
            module_logger.info("Testiranje LED...")

            result = True
            additional_info = ""

            for ii in range(7):
                self.i2c.test_one_led(ii)

                if self.ampermeter.in_range(0.01,0.2) == False:
                    result = False

                resistor = 1.0
                current = (self.ampermeter.value / resistor) * 1000.0

                additional_info += str(current)
                additional_info += ","

                # Shut MCP off every time current is measured
                self.i2c.manual_off()

            if result == True:
                self.measurement_results["LED"] = [1, "ok", 5, "NA",additional_info]
            else:
                self.measurement_results["LED"] = [1, "fail", 5, "NA",additional_info]

            # Test Heater
            module_logger.info("Testiranje Heater...")

            result = True
            additional_info = ""

            self.i2c.turn_heater_on()
            self.relay_board.close_relay(relays["Heater"])
            time.sleep(0.2)

            if self.voltmeter.in_range(-0.2, 0.5) == False:
                result = False

            additional_info += str(self.voltmeter.value)
            additional_info += ","

            self.i2c.turn_heater_off()
            time.sleep(0.2)

            if self.voltmeter.in_range(11.5, 12.5) == False:
                result = False

            additional_info += str(self.voltmeter.value)

            self.relay_board.open_relay(relays["Heater"])

            if result == True:
                self.measurement_results["Heater"] = [1, "ok", 5, "NA",additional_info]
            else:
                self.measurement_results["Heater"] = [1, "fail", 5, "NA",additional_info]

        except Exception as ee:
            module_logger.info("MCP communication error: {}".format(ee))
            #module_logger.debug("Exception  % s in %s.", ee, type(self).__name__)

            return {"signal": [1, "fail", 5, "NA"]}

        try:
            module_logger.info("Testiranje Temperature...")
            if self.temp_sensor.in_range(20.0,40.0):
                self.measurement_results['temperature'] = [self.temp_sensor.value, "ok", 5, "C"]
            else:
                self.measurement_results['temperature'] = [self.temp_sensor.value, "fail", 5, "C"]

            print(self.measurement_results)
        except Exception as ee:
            module_logger.info("LM75A communication error: {}".format(ee))
            return {"signal": [1, "fail", 5, "NA"]}

        return self.measurement_results

    def tear_down(self):
        self.relay_board.open_relay(relays["Power"])
        self.relay_board.hid_device.close()
        self.voltmeter.close()
        self.ampermeter.close()













'''




class LockSimulator(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):

        tim = time.clock()
        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", 0.16)

        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])
        time.sleep(2)

    def measure_left_side(self):

        # LEFT SIDE
        self.relay_board.close_relay(relays["IN_relay_1"])
        self.relay_board.close_relay(relays["IN_relay_2"])

        self.relay_board.close_relay(relays["OUT_relay_3"])
        self.relay_board.open_relay(relays["OUT_relay_1"])

        # IZMERI OUT1+
        self.relay_board.close_relay(relays["OUT_relay_4"])
        volt_plus = self.voltmeter.read()

        # IZMERI OUT1+
        self.relay_board.close_relay(relays["OUT_relay_1"])
        volt_minus = self.voltmeter.read()

        self.relay_board.open_relay(relays["OUT_relay_4"])

        voltage = volt_plus - volt_minus
        return voltage

    def measure_right_side(self):
        # RIGHT SIDE
        self.relay_board.open_relay(relays["IN_relay_1"])
        self.relay_board.open_relay(relays["IN_relay_2"])

        self.relay_board.open_relay(relays["OUT_relay_3"])
        self.relay_board.open_relay(relays["OUT_relay_2"])

        # IZMERI OUT2+
        self.relay_board.close_relay(relays["OUT_relay_4"])

        volt_plus = self.voltmeter.read()

        # IZMERI OUT2-
        self.relay_board.close_relay(relays["OUT_relay_2"])
        volt_minus = self.voltmeter.read()

        self.relay_board.open_relay(relays["OUT_relay_4"])

        voltage = volt_plus - volt_minus
        return voltage

    def unlock(self):
        self.relay_board.open_relay(relays["Inv_relay_2"])
        time.sleep(0.2)
        self.relay_board.close_relay(relays["Inv_relay_1"])


    def lock(self):
        self.relay_board.open_relay(relays["Inv_relay_1"])
        time.sleep(0.2)
        self.relay_board.close_relay(relays["Inv_relay_2"])


    def run(self):
        for i in range(10):

            print("LOCK")
            self.lock()
            time.sleep(5)
            print("UNLOCK")
            self.unlock()
            time.sleep(5)

        while(1):
            pass

        print("UNLOCK POWER ON")
        self.unlock()

        leftunlock1 = self.measure_left_side()
        print("OUT1: {}V".format(leftunlock1))
        rightunlock1 = self.measure_right_side()
        print("OUT2: {}V".format(rightunlock1))

        print("LOCK POWER ON")
        self.lock()

        leftlock1 = self.measure_left_side()
        print("OUT1: {}V".format(leftlock1))
        rightlock1 = self.measure_right_side()
        print("OUT2: {}V".format(rightlock1))

        ## Izklopi napajanje
        #self.relay_board.open_relay(relays["Power"])
        #time.sleep(0.2)
#
        #print("LOCK POWER OFF")
        #leftlock0 = self.measure_left_side()
        #print("OUT1: {}V".format(leftlock0))
        #rightlock0 = self.measure_right_side()
        #print("OUT2: {}V".format(rightlock0))
#
        #print("UNLOCK POWER OFF")
        #self.unlock()
#
        #leftunlock0 = self.measure_left_side()
        #print("OUT1: {}V".format(leftunlock0))
        #rightunlock0 = self.measure_right_side()
        #print("OUT2: {}V".format(rightunlock0))

        #additional_info = str(leftunlock1) + "," + str(rightunlock1) + "," + str(leftlock1) + "," + str(rightlock1) + "," + str(leftlock0) + "," + str(rightlock0) + "," + str(leftunlock0) + "," + str(rightunlock0)

        result = False

        if result == True:
            self.measurement_results['Lock'] = [1, "ok", 5, "V",additional_info]
        else:
            self.measurement_results['Lock'] = [1, "fail", 5, "V",additional_info]
        return self.measurement_results

    def tear_down(self):
        self.relay_board.open_all_relays()
        self.voltmeter.close()
        self.relay_board.hid_device.close()



















class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):
        # Lock test device
        GPIO.output(gpios["LOCK"], G_LOW)

        strips_tester.current_product.test_status = all(strips_tester.current_product.task_results) and len(strips_tester.current_product.task_results)
        if strips_tester.current_product.test_status:
            GPIO.output(gpios["LIGHT_GREEN"], G_LOW)
            module_logger.debug("LIGHT_GREEN ON")
        else:
            GPIO.output(gpios["LIGHT_RED"], G_LOW)
            module_logger.debug("LIGHT_RED ON")

        return {"signal":[1, 'ok', 0, 'NA']}

    def tear_down(self):
        # Wait forever
        pass






class PowerOffTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.measurement_delay = 0.16
        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.measurement_delay)
        self.relay_board.open_all_relays()

    def run(self):
        result = True
        additional_info = ""

        self.relay_board.close_relay(relays["Power"])
        time.sleep(10)

        # read via I2C status red diode
        self.relay_board.close_relay(relays["LED_green_right"])
        time.sleep(0.2)

        if self.voltmeter.in_range(8.0,8.3) == False:
            result = False

        additional_info += str(self.voltmeter.value)
        additional_info += ","

        self.relay_board.open_relay(relays["LED_green_right"])
        self.relay_board.close_relay(relays["LED_green_left"])
        time.sleep(0.2)

        if self.voltmeter.in_range(8.0, 8.3) == False:
            result = False

        additional_info += str(self.voltmeter.value)
        additional_info += ","

        self.relay_board.open_relay(relays["LED_green_left"])

        # Disable power
        self.relay_board.open_relay(relays["Power"])

        # read via I2C status red diode
        print("TESTIRANJE RED LED")

        GPIO.output(gpios["LED_red_left"], G_LOW)
        time.sleep(0.2)

        if self.voltmeter.in_range(1.5,2.2) == False:

            result = False

        additional_info += str(self.voltmeter.value)
        additional_info += ","

        GPIO.output(gpios["LED_red_left"], G_HIGH)
        time.sleep(0.1)
        GPIO.output(gpios["LED_red_right"], G_LOW)
        time.sleep(0.2)

        if self.voltmeter.in_range(1.5,2.2) == False:
            result = False

        additional_info += str(self.voltmeter.value)
        additional_info += ","

        GPIO.output(gpios["LED_red_right"], G_HIGH)

        if result == True:
            self.measurement_results["LED_Board"] = [1, "ok", 5, "NA", additional_info]
        else:
            self.measurement_results["LED_Board"] = [1, "fail", 5, "NA", additional_info]

        # Safety PELV (lock stays locked until volt1 and volt2 are below threshold)
        threshold = 10.0
        volt1 = 999.0
        volt2 = 999.0

        print("Threshold for PELV: {}V".format(threshold))

        while(volt1 > threshold):
            self.relay_board.close_relay(relays["Vcc1"])
            time.sleep(0.2)
            print("Vcc1: {}V".format(volt1))
            volt1 = self.voltmeter.read()

        self.relay_board.open_relay(relays["Vcc1"])

        while(volt2 > threshold):
            self.relay_board.close_relay(relays["Vcc2"])
            time.sleep(0.2)
            print("Vcc2: {}V".format(volt2))
            volt2 = self.voltmeter.read()

        self.relay_board.open_relay(relays["Vcc2"])


        print("Lock UNLOCKED!")
        # Open lock
        GPIO.output(gpios["LOCK"], G_LOW)

        return self.measurement_results

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()





class RCTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.measurement_delay = 0.16
        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.measurement_delay)
        self.relay_board.open_all_relays()

    def run(self):
        result = True
        additional_info = ""



        x = np.array()
        y = np.array()

        constant = np.polyfit(x, np.log(y), 1)


        for i in range(10):
            np.append(x,i)
            np.append(y,self.voltmeter.read())
            time.sleep(0.5)


        # Safety PELV (lock stays locked until volt1 and volt2 are below threshold)
        threshold = 10.0
        volt1 = 999.0
        volt2 = 999.0

        module_logger.debug("Threshold for PELV: {}V".format(threshold))

        self.relay_board.close_relay(relays["Vcc1"])

        while(volt1 > threshold):
            time.sleep(0.2)
            print("Vcc1: {}V".format(volt1))
            volt1 = self.voltmeter.read()

        self.relay_board.open_relay(relays["Vcc1"])
        self.relay_board.close_relay(relays["Vcc2"])

        while(volt2 > threshold):
            self.relay_board.close_relay(relays["Vcc2"])
            time.sleep(0.2)
            print("Vcc2: {}V".format(volt2))
            volt2 = self.voltmeter.read()

        self.relay_board.open_relay(relays["Vcc2"])

        print("Lock UNLOCKED!")
        # Open lock
        GPIO.output(gpios["LOCK"], G_LOW)

        return {"signal":[1, 'ok', 0, 'NA']}

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()

