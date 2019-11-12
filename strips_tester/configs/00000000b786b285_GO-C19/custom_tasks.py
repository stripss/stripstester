import importlib
import logging
import sys
import time
import multiprocessing
import Colorer
import os

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

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays


# checks if lid is opened

def get_program_number():  # Flash program selector
    try:
        program = strips_tester.data['program_number']
    except KeyError:
        program = "S001"
        strips_tester.data['program_number'] = program

    return program


class StartProcedureTask(Task):
    def run(self) -> (bool, str):
        gui_web.send({"command": "title", "value": "GO-C19 ({})".format(get_program_number())})

        if "START_SWITCH" in settings.gpios:
            module_logger.info("Za nadaljevanje zapri pokrov")

            gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})

            for i in range(2):
                gui_web.send({"command": "progress", "nest": i, "value": "0"})

            while True:
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
                if state_GPIO_SWITCH:
                    break

                time.sleep(0.01)

            for i in range(2):
                gui_web.send({"command": "error", "nest": i, "value": -1})  # Clear all error messages
                gui_web.send({"command": "info", "nest": i, "value": -1})  # Clear all error messages
                gui_web.send({"command": "semafor", "nest": i, "value": (0, 1, 0), "blink": (0, 0, 0)})

                strips_tester.data['start_time'][i] = datetime.datetime.utcnow()  # Get start test date
                gui_web.send({"command": "time", "mode": "start", "nest": i})  # Start count for test

            GPIO.output(gpios['GREEN_LEFT'], True)
            GPIO.output(gpios['RED_LEFT'], True)
            GPIO.output(gpios['GREEN_RIGHT'], True)
            GPIO.output(gpios['RED_RIGHT'], True)

            self.start_buzzer_thread = threading.Thread(target=self.start_buzzer)
            self.start_buzzer_thread.start()

            GPIO.output(gpios['LN_RELAY'], GPIO.HIGH)  # Disable L and N
        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")

        return

    def start_buzzer(self):
        for i in range(3):
            GPIO.output(gpios['BUZZER'], True)
            time.sleep(0.1)
            GPIO.output(gpios['BUZZER'], False)
            time.sleep(0.1)

    def tear_down(self):
        pass


# Perform product detection
class InitialTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-B5E9C.voltage1", 0.16)
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)

        self.segger_found = False
        for i in range(10):
            try:
                self.segger = devices.Segger("/dev/segger")
                self.segger_found = True
                break
            except Exception as ee:
                print("Segger error: {} " . format(ee))

                time.sleep(0.1)

    def run(self) -> (bool, str):

        if not self.segger_found:
            gui_web.send({"command": "error", "value": "Programatorja ni mogoče najti!"})
            self.end_test()
            return

        self.segger.select_file(get_program_number())  # Select S001 binary file

        if not lid_closed():
            gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!"})
            self.end_test()
            return

        self.shifter.reset()

        # Lock test device
        self.shifter.set("K9", True)
        self.shifter.invertShiftOut()

        flip_left = False
        flip_right = False
        stop = False

        gui_web.send({"command": "status", "value": "Detekcija modulov..."})

        # Initiate servo calibration
        self.calibration_thread = threading.Thread(target=self.calibration)
        self.calibration_thread.start()

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "5"})

        self.power_on()  # Power on board (external 5V)

        self.flash_process = threading.Thread(target=self.flashMCU, args=(0,))

        self.shifter.set("K11", True)  # Segger RESET enable

        self.shifter.set("K10", False)  # Segger SWIM Left
        self.shifter.set("K12", False)  # Segger RESET Left
        self.shifter.set("K13", False)  # Segger VCC Left
        self.shifter.set("K14", False)  # Segger GND Left
        self.shifter.invertShiftOut()


        voltage_left = self.detect_voltage("M7", "M3")

        if self.in_range(voltage_left, 5.0, 10):
            strips_tester.data['exist'][0] = True

            module_logger.info("left product detected with %sV of power supply", voltage_left)
            gui_web.send({"command": "info", "nest": 0, "value": "Zaznan kos na napetosti {}V".format(voltage_left)})
        else:
            gui_web.send({"command": "info", "nest": 0, "value": "Ni zaznanega kosa: {}V".format(voltage_left)})

        if strips_tester.data['exist'][0]:
            trimmer_left = self.measure_voltage1("M7", "L4")
            angle = round((trimmer_left / voltage_left) * 100.0, 2)
            # print("Trimmer: {}%, {}V" . format(int(angle),trimmer_left))

            if angle < 5 or angle > 95:
                if angle > 95:
                    flip_left = True

                self.flash_process.start()

                self.measure_voltage(0, "vCap", "M7", "M1", 1.8, 10)
                self.measure_voltage(0, "vR1", "L3", "M5", -1.9, 0.3, False)

                expected_voltage = - voltage_left + trimmer_left
                success = self.measure_voltage(0, "vR2", "L4", "M5", expected_voltage, 1, False)

                if not success:
                    stop = True

                # Wait flashing to be done.
                self.flash_process.join()
            else:
                module_logger.error("left trimmer not in end position! ({}%)".format(angle))
                gui_web.send({"command": "error", "nest": 0, "value": "Potenciometer na levem kosu ni na končnem položaju ({}%).".format(angle)})

                self.add_measurement(0, False, "Trimmer", angle, "deg", True)
                stop = True
        else:
            gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0)})

        # Make process for right side programming
        self.flash_process = threading.Thread(target=self.flashMCU, args=(1,))

        # 5V right
        self.shifter.set("K10", True)  # Segger SWIM Right
        self.shifter.set("K12", True)  # Segger RESET Right
        self.shifter.set("K13", True)  # Segger VCC Right
        self.shifter.set("K14", True)  # Segger GND Right
        self.shifter.invertShiftOut()

        gui_web.send({"command": "status", "value": "Detekcija desnega kosa..."})
        voltage_right = self.detect_voltage("L11", "L7")

        if self.in_range(voltage_right, 5.0, 10):
            strips_tester.data['exist'][1] = True

            module_logger.info("right product detected with %sV of power supply", voltage_right)
            gui_web.send({"command": "info", "nest": 1, "value": "Zaznan kos na napetosti {}V".format(voltage_right)})
        else:
            gui_web.send({"command": "info", "nest": 1, "value": "Ni zaznanega kosa: {}V".format(voltage_right)})

        if strips_tester.data['exist'][1]:
            trimmer_right = self.measure_voltage1("K8", "L11")
            angle = round((trimmer_right / voltage_right) * 100.0, 2)
            # print("Trimmer: {}%, {}V".format(int(angle), trimmer_right))

            if angle < 5 or angle > 95:
                if angle > 95:
                    flip_right = True

                self.flash_process.start()

                self.measure_voltage(1, "vCap", "L5", "L11", 1.8, 10)
                self.measure_voltage(1, "vR1", "K7", "L9", -1.9, 0.3, False)

                expected_voltage = - voltage_right + trimmer_right
                success = self.measure_voltage(1, "vR2", "K8", "L9", expected_voltage, 1, False)

                if not success:
                    stop = True

                # Wait flashing to be done.
                self.flash_process.join()
            else:
                module_logger.error("right trimmer not in end position! ({}%)".format(angle))
                gui_web.send({"command": "error", "nest": 1, "value": "Potenciometer na desnem kosu ni na končnem položaju ({}%).".format(angle)})
                self.add_measurement(1, False, "Trimmer", angle, "deg", True)

                stop = True
        else:
            gui_web.send({"command": "semafor", "nest": 1, "value": (0, 0, 0)})

        gui_web.send({"command": "status", "value": "Kalibracija..."})

        self.shifter.set("K10", False)  # Segger SWIM Left
        self.shifter.set("K12", False)  # Segger RESET Left
        self.shifter.set("K13", False)  # Segger VCC Left
        self.shifter.set("K14", False)  # Segger GND Left
        self.shifter.set("K11", False)  # Segger RESET disable
        self.shifter.invertShiftOut()

        self.power_off()
        self.calibration_thread.join()  # Wait for servo to calibrate

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "15"})

        if not stop:
            if flip_left and flip_right:
                # Flip both servos
                self.nanoboard_small.write("servo 3 100", 10)
            else:
                if flip_left:
                    # Flip left
                    self.nanoboard_small.write("servo 1 100", 10)

                if flip_right:
                    # Flip right
                    self.nanoboard_small.write("servo 2 100", 10)

        return

    def power_on(self):
        GPIO.output(gpios['POWER'], GPIO.HIGH)

    def power_off(self):
        GPIO.output(gpios['POWER'], GPIO.LOW)

    def calibration(self):
        self.nanoboard_small.write("offset 20", 3)
        self.nanoboard_small.write("endoffset 20", 3)
        self.nanoboard_small.write("calibrate", 10)


    def detect_voltage(self, testpad1, testpad2):
        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        for i in range(3):
            voltage = self.voltmeter.read()

            #print("Detect Voltage: {}V".format(voltage))
            if voltage > 4.5:  # DUT detected
                break

        self.shifter.set(testpad1, False)
        self.shifter.set(testpad2, False)
        self.shifter.invertShiftOut()

        time.sleep(0.01)

        return voltage

    def measure_voltage1(self, testpad1, testpad2):
        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        for i in range(3):
            voltage = self.voltmeter.read()
            print("Voltage: {}V".format(voltage))

        self.shifter.set(testpad1, False)
        self.shifter.set(testpad2, False)
        self.shifter.invertShiftOut()

        time.sleep(0.01)

        return voltage

    def measure_voltage(self, nest, name, testpad1, testpad2, expected, tolerance=15, percent=True, result=False):
        # if not self.is_product_ready(nest):
        #     return

        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        num_of_tries = 10

        voltage = self.voltmeter.read()

        while not self.in_range(voltage, expected, tolerance, percent):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            print("   Retrying... {}V".format(voltage))

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("%s out of bounds: meas:%sV", name, voltage)
            gui_web.send({"command": "error", "nest": nest, "value": "Meritev napetosti {} je izven območja: {}V".format(name, voltage)})
            self.add_measurement(nest, False, name, voltage, "V", end_task=True)  # Cannot determine servo position
        else:
            module_logger.info("%s in bounds: meas:%sV", name, voltage)
            gui_web.send({"command": "info", "nest": nest, "value": "Meritev napetosti {}: {}V".format(name, voltage)})
            self.add_measurement(nest, True, name, voltage, "V")

        self.shifter.set(testpad1, False)
        self.shifter.set(testpad2, False)
        self.shifter.invertShiftOut()

        time.sleep(0.01)

        if result:
            if not num_of_tries:
                return -1
            else:
                return voltage

        if not num_of_tries:
            return False

        return True

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

    def flashMCU(self, nest):  # functional

        GPIO.output(gpios['SEGGER_RELAY'], GPIO.LOW)

        gui_web.send({"command": "status", "value": "Programiranje..."})

        status = self.segger.download()

        if status:
            module_logger.info("flashing ok ({})".format(get_program_number()))
            gui_web.send({"command": "info", "nest": nest, "value": "Programiranje uspelo {}.".format(get_program_number())})
            self.add_measurement(nest, True, "Flashing", get_program_number())
        else:
            module_logger.warning("error flashing ({})".format(get_program_number()))
            gui_web.send({"command": "error", "nest": nest, "value": "Programiranje ni uspelo {}.".format(get_program_number())})
            self.add_measurement(nest, False, "Flashing", get_program_number())

        GPIO.output(gpios['SEGGER_RELAY'], GPIO.HIGH)

        gui_web.send({"command": "progress", "nest": nest, "value": "10"})

        return status

    def tear_down(self):
        try:
            self.voltmeter.close()
            self.segger.close()
            self.nanoboard_small.close()
        except AttributeError:
            pass


# Perform resistance test and trimmer zeroing
class ICT_ResistanceTest(Task):
    def set_up(self):
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)

        for i in range(5):
            try:
                #self.ohmmeter = devices.DigitalMultiMeter("/dev/ohmmeter")
                self.ohmmeter = devices.YoctoBridge('YWBRIDG1-114706.weighScale1', 0.6)

                break
            except Exception:
                time.sleep(0.2)

    def run(self) -> (bool, str):
        if not lid_closed():
            gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!"})
            self.end_test()
            return

        if not strips_tester.data['exist'][0] and not strips_tester.data['exist'][1]:  # Move to the next task if no products
            self.end_test()
            return

        gui_web.send({"command": "status", "value": "ICT Meritev upornosti..."})

        # Lock test device
        self.shifter.set("K9", True)
        self.shifter.invertShiftOut()

        #self.ohmmeter.set_signal_range(0, 300000)

        # Initiate servo calibration
        self.servo_thread = threading.Thread(target=self.zero_trimmers)
        self.servo_thread.start()

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "20"})

        self.power_off()  # Just to make sure

        self.make_short_on("M5", "M7")  # We make sure capacitors are discharged
        self.make_short_on("L9", "L7")  # We make sure capacitors are discharged

        if self.is_product_ready(0):
            self.shifter.set("K13", True)  # Segger VCC Right
            self.shifter.set("K14", True)  # Segger GND Right
            self.shifter.set("K12", True)  # Segger RESET Left
            self.shifter.invertShiftOut()

            self.measure_resistance(0, "R3", "L2", "M13", 47, 30)
            self.measure_resistance(0, "R9", "M16", "M9", 180)
            self.measure_resistance(0, "R8", "M10", "M8", 220)

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "30"})

        if self.is_product_ready(1):
            self.shifter.set("K13", False)  # Segger VCC Right
            self.shifter.set("K14", False)  # Segger GND Right
            self.shifter.set("K12", False)  # Segger RESET Left
            self.shifter.invertShiftOut()

            self.ohmmeter.sensor1.set_excitation(2)
            self.measure_resistance(1, "R3", "K6", "L16", 47, 30)
            self.measure_resistance(1, "R9", "L13", "K4", 180)
            self.measure_resistance(1, "R8", "K3", "L12", 220)

            self.ohmmeter.sensor1.set_excitation(1)
            self.measure_resistance(1, "R4", "L15", "K6", 220000, 10)
            self.measure_resistance(1, "R5", "L14", "K5", 220000, 10)

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "40"})

        if self.is_product_ready(0):
            self.ohmmeter.sensor1.set_excitation(2)
            self.shifter.set("K13", True)  # Segger VCC Right
            self.shifter.set("K14", True)  # Segger GND Right
            self.shifter.set("K12", True)  # Segger RESET Left
            self.shifter.invertShiftOut()

            self.ohmmeter.sensor1.set_excitation(1)
            self.measure_resistance(0, "R4", "L2", "M14", 220000, 10)
            self.measure_resistance(0, "R5", "L1", "M15", 220000, 10)

        self.make_short_off("M5", "M7")  # We make sure capacitors are discharged
        self.make_short_off("L9", "L7")  # We make sure capacitors are discharged

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "50"})

        self.servo_thread.join()  # Wait until trimmers are zeroed

        return

    def zero_trimmers(self):
        # Assuming servos are already in position as the trimmers
        # BUG -> if servo is over the 50, it wont turn

        self.nanoboard_small.write("move 22", 10)
        self.nanoboard_small.write("servo 3 0", 10)  # Zero both servos

        # Platforma naj ostane gor

        return

    def measure_resistance(self, nest, name, testpad1, testpad2, expected, tolerance=20):
        if not self.is_product_ready(nest):  # Skip other measurements
            return

        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        num_of_tries = 5

        resistance = self.ohmmeter.get_resistance()

        while not self.in_range(resistance, expected, tolerance):
            num_of_tries = num_of_tries - 1

            resistance = self.ohmmeter.get_resistance()

            print("   Retrying... {}ohm".format(resistance))

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("%s out of bounds: meas:%sohm", name, resistance)
            gui_web.send({"command": "error", "nest": nest, "value": "Meritev upornosti {} je izven območja: {}ohm".format(name, resistance)})
            self.add_measurement(nest, False, name, resistance, "ohm")
        else:
            module_logger.info("%s in bounds: meas:%sohm", name, resistance)
            gui_web.send({"command": "info", "nest": nest, "value": "Meritev upornosti {}: {}ohm".format(name, resistance)})
            self.add_measurement(nest, True, name, resistance, "ohm")

        self.shifter.set(testpad1, False)
        self.shifter.set(testpad2, False)
        self.shifter.invertShiftOut()

        time.sleep(0.01)

        return

    def power_off(self):
        GPIO.output(gpios['POWER'], GPIO.LOW)

    def make_short(self, vccpad, gndpad):
        time.sleep(0.01)
        self.shifter.set(vccpad, True)
        self.shifter.set(gndpad, True)
        self.shifter.invertShiftOut()
        time.sleep(0.1)
        self.shifter.set(vccpad, False)
        self.shifter.set(gndpad, False)
        self.shifter.invertShiftOut()
        time.sleep(0.01)

    def make_short_on(self, vccpad, gndpad):
        #self.shifter.set(vccpad, True)
        self.shifter.set(gndpad, True)
        self.shifter.invertShiftOut()

    def make_short_off(self, vccpad, gndpad):
        #self.shifter.set(vccpad, False)
        self.shifter.set(gndpad, False)
        self.shifter.invertShiftOut()

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

    def tear_down(self):
        self.ohmmeter.close()
        self.nanoboard_small.close()


# Perform voltage and visual test
class ICT_VoltageVisualTest(Task):
    def set_up(self):
        for i in range(3):
            try:
                self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-B5E9C.voltage1", 0.16)  # Rectified DC Voltage
                break
            except Exception:
                time.sleep(0.2)

        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)
        self.led_gpio = [40, 37, 38, 35, 36, 33]

        '''
            FUNCTIONAL TEST: power on (LN)
            imidietaly check LEDs (timeout 2s)
            check when led turn off (timeout 3s)
            rotate servos on 100%
            check leds if turn on (timeout 5s)

        '''

        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        # Prepare GPIO list for visual test (left leds, right leds)
        for current in self.led_gpio:
            GPIO.setup(current, GPIO.IN)

    def run(self) -> (bool, str):
        if not lid_closed():
            gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!"})
            self.end_test()
            return

        if not self.is_product_ready(0) and not self.is_product_ready(1):  # Move to the next task if no products
            self.end_test()
            return

        gui_web.send({"command": "status", "value": "Vizualni pregled LED diod"})

        # Lock test device
        self.shifter.set("K9", True)
        self.shifter.invertShiftOut()

        self.power_off()  # We make sure that test device is galvanic isolated from product
        self.shifter.set("K11", False)  # Segger RESET disable (so both MCU are running)

        self.shifter.invertShiftOut()

        GPIO.output(gpios['SEGGER_RELAY'], GPIO.HIGH)
        time.sleep(0.5)

        # skleni L, N

        GPIO.output(gpios['LN_RELAY'], GPIO.LOW)

        # self.shifter.set("K16", True)  # L
        # self.shifter.set("K15", True)  # N
        # self.shifter.invertShiftOut()

        module_logger.info("VISUAL TEST STARTING...")
        # Initiate ICT voltage test
        self.ict_thread = threading.Thread(target=self.ICTVoltageACTest)
        self.ict_thread.start()

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "60"})

        visual_start = self.check_mask([0, 0, 1], 2)

        if self.is_product_ready(0):
            if not visual_start[0]:
                module_logger.error("VisualStart LEFT")
                gui_web.send({"command": "error", "nest": 0, "value": "Napaka LED diod na levem kosu (VisualStart)"})
            else:
                module_logger.info("VisualStart LEFT")
                gui_web.send({"command": "info", "nest": 0, "value": "Test LED diod na levem kosu (VisualStart) ustrezen"})

            self.add_measurement(0, visual_start[0], "VisualStart", visual_start[0], "")

        if self.is_product_ready(1):
            if not visual_start[1]:
                module_logger.error("VisualStart RIGHT")
                gui_web.send({"command": "error", "nest": 1, "value": "Napaka LED diod na desnem kosu (VisualStart)"})
            else:
                module_logger.info("VisualStart RIGHT")
                gui_web.send({"command": "info", "nest": 1, "value": "Test LED diod na desnem kosu (VisualStart) ustrezen"})

            self.add_measurement(1, visual_start[1], "VisualStart", visual_start[1], "")

        # Wait until leds are off
        visual_off = self.check_mask([1, 1, 1], 4)
        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "70"})

        if self.is_product_ready(0):
            if not visual_off[0]:
                module_logger.error("VisualOff LEFT")
                gui_web.send({"command": "error", "nest": 0, "value": "Napaka LED diod na levem kosu (VisualOff)"})
                self.add_measurement(0, False, "VisualOff", "Led stays on", "")
            else:
                module_logger.info("VisualOff LEFT")
                gui_web.send({"command": "info", "nest": 0, "value": "Test LED diod na levem kosu (VisualOff) ustrezen"})

        if self.is_product_ready(1):
            if not visual_off[1]:
                module_logger.error("VisualOff RIGHT")
                gui_web.send({"command": "error", "nest": 1, "value": "Napaka LED diod na desnem kosu (VisualOff)"})
                self.add_measurement(1, False, "VisualOff", "Led stays on", "")
            else:
                module_logger.info("VisualOff RIGHT")
                gui_web.send({"command": "info", "nest": 1, "value": "Test LED diod na desnem kosu (VisualOff) ustrezen"})

        # Check for errors
        visual_err = self.check_mask([0, 1, 1], 1)
        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "80"})

        if self.is_product_ready(0):
            if visual_err[0]:
                module_logger.info("VisualError LEFT")
                gui_web.send({"command": "error", "nest": 0, "value": "Napaka LED diod na level kosu (VisualError)"})
                self.add_measurement(0, False, "VisualOff", "Led in error state", "")
            else:
                gui_web.send({"command": "info", "nest": 0, "value": "Test LED diod na levem kosu (VisualError) ustrezen"})
                self.add_measurement(0, True, "VisualOff", "OK", "")

        if self.is_product_ready(1):
            if visual_err[1]:
                module_logger.info("VisualError RIGHT")
                self.add_measurement(1, False, "VisualOff", "Led in error state", "")
                gui_web.send({"command": "error", "nest": 1, "value": "Napaka LED diod na desnem kosu (VisualError)"})
            else:
                self.add_measurement(1, True, "VisualOff", "OK", "")
                gui_web.send({"command": "info", "nest": 1, "value": "Test LED diod na desnem kosu (VisualError) ustrezen"})

        self.nanoboard_small.write("servo 3 100", 10)
        self.nanoboard_small.write("move 0", 10)

        visual_on = self.check_mask([0, 0, 0], 4)

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "90"})

        if self.is_product_ready(0):
            if not visual_on[0]:
                module_logger.error("VisualOn LEFT")
                gui_web.send({"command": "error", "nest": 0, "value": "Napaka LED diod na levem kosu (VisualOn)"})
            else:
                module_logger.info("VisualOn LEFT")
                gui_web.send({"command": "info", "nest": 0, "value": "Test LED diod na levem kosu (VisualOn) ustrezen"})

            self.add_measurement(0, visual_on[0], "VisualOn", visual_on[0], "")

        if self.is_product_ready(1):
            if not visual_on[1]:
                module_logger.error("VisualOn RIGHT")
                gui_web.send({"command": "error", "nest": 1, "value": "Napaka LED diod na desnem kosu (VisualOn)"})
            else:
                module_logger.info("VisualOn RIGHT")
                gui_web.send({"command": "info", "nest": 1, "value": "Test LED diod na desnem kosu (VisualOn) ustrezen"})

            self.add_measurement(1, visual_on[1], "VisualOn", visual_on[1], "")

        self.ict_thread.join()  # Wait until ICT voltage test is finished

        # razkleni L, N
        # self.shifter.set("K16", False)  # L
        # self.shifter.set("K15", False)  # N
        GPIO.output(gpios['LN_RELAY'], GPIO.HIGH)
        # self.shifter.invertShiftOut()

        return

    def ICTVoltageACTest(self):
        if self.is_product_ready(0):
            self.measure_voltage(0, "Z1", "M3", "M6", 2.1, 0.5)

        if self.is_product_ready(1):
            self.measure_voltage(1, "Z1", "L10", "L7", 2.1, 0.5)

        if self.is_product_ready(0):
            self.measure_voltage(0, "D1", "M4", "M7", 2.2, 0.5)

        if self.is_product_ready(1):
            self.measure_voltage(1, "D1", "L8", "L11", 2.2, 0.5)

        if self.is_product_ready(0):
            self.measure_voltage(0, "5V", "M3", "M7", 4.7, 0.5)

        if self.is_product_ready(1):
            self.measure_voltage(1, "5V", "L7", "L11", 4.7, 0.5)

            #
            # if voltage_5v == -1 or voltage_d1 == -1 or voltage_z1 == -1:
            #     strips_tester.data['status_right'] = 0
            #     strips_tester.data['status'][1] = False

    def check_mask(self, mask=[], duration=0):
        end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration)

        while datetime.datetime.utcnow() < end_time:
            state_list = []

            for current in range(len(self.led_gpio)):
                state_list.append(GPIO.input(self.led_gpio[current]))

                # print("{} -> [{}] {}".format(current, mask[current], state_list[-1]))

            #print(state_list, end='')
            #print(" should be ", end='')
            #print(mask)

            time.sleep(0.05)

            # Test only DUT which exist and is not fail
            result = [not strips_tester.data['exist'][0] or (strips_tester.data['status'][0] is False), not strips_tester.data['exist'][1] or (strips_tester.data['status'][1] is False)]

            for mask_num in range(2):
                # print(mask[mask_num * 3:mask_num * 3 + 3])
                # print(state_list[mask_num * 3:mask_num * 3 + 3])
                if not result[mask_num]:
                    if np.all(mask == state_list[mask_num * 3:mask_num * 3 + 3]):  # Mask is same as input
                        result[mask_num] = True

            if all(result):
                break

        return result

    def power_on(self):
        GPIO.output(gpios['POWER'], GPIO.HIGH)

    def power_off(self):
        GPIO.output(gpios['POWER'], GPIO.LOW)

    def measure_voltage(self, nest, name, testpad1, testpad2, expected, tolerance=15):
        if not self.is_product_ready(nest):
            return

        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        num_of_tries = 10

        voltage = self.voltmeter.read()

        while not self.in_range(voltage, expected, tolerance, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            print("   Retrying... {}V".format(voltage))

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("%s out of bounds: meas:%sV", name, voltage)
            gui_web.send({"command": "error", "nest": nest, "value": "Meritev napetosti {} je izven območja: {}V".format(name, voltage)})
            self.add_measurement(nest, False, name, voltage, "V")
            voltage = -1
        else:
            module_logger.info("%s in bounds: meas:%sV", name, voltage)
            gui_web.send({"command": "info", "nest": nest, "value": "Meritev napetosti {}: {}V".format(name, voltage)})
            self.add_measurement(nest, True, name, voltage, "V")

        self.shifter.set(testpad1, False)
        self.shifter.set(testpad2, False)
        self.shifter.invertShiftOut()

        time.sleep(0.01)

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

    def tear_down(self):
        self.voltmeter.close()
        self.nanoboard_small.close()


class ProductConfigTask(Task):
    def set_up(self):
        module_logger.debug("ProductConfigTask init")

    def run(self):
        for current_nest in range(strips_tester.settings.test_device_nests):
            if strips_tester.data['exist'][current_nest]:
                if strips_tester.data['status'][current_nest] == -1:
                    strips_tester.data['status'][current_nest] = True

        return

    def tear_down(self):
        pass


class FinishProcedureTask(Task):
    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

        self.shifter = devices.HEF4094BT(24, 31, 26, 29)

    def run(self):
        for i in range(2):
            gui_web.send({"command": "semafor", "nest": i, "value": (0, 0, 0), "blink": (0, 0, 0)})
            gui_web.send({"command": "progress", "nest": i, "value": "95"})

        GPIO.output(gpios['GREEN_LEFT'], False)
        GPIO.output(gpios['RED_LEFT'], False)
        GPIO.output(gpios['GREEN_RIGHT'], False)
        GPIO.output(gpios['RED_RIGHT'], False)

        GPIO.output(gpios['BUZZER'], True)

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == True:
                GPIO.output(gpios['GREEN_LEFT'], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            elif strips_tester.data['status'][0] == False:
                GPIO.output(gpios['RED_LEFT'], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        if strips_tester.data['exist'][1]:
            if strips_tester.data['status'][1] == True:
                GPIO.output(gpios['GREEN_RIGHT'], True)
                gui_web.send({"command": "semafor", "nest": 1, "value": (0, 0, 1)})
            elif strips_tester.data['status'][1] == False:
                GPIO.output(gpios['RED_RIGHT'], True)
                gui_web.send({"command": "semafor", "nest": 1, "value": (1, 0, 0)})

        self.start_buzzer_thread = threading.Thread(target=self.start_buzzer)
        self.start_buzzer_thread.start()

        # wait for open lid
        if not strips_tester.data['exist'][0] and not strips_tester.data['exist'][1]:
            gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
            module_logger.info("Za konec testa odpri pokrov")
        else:
            module_logger.info("Za tiskanje nalepke odpri pokrov")
            gui_web.send({"command": "status", "value": "Za tiskanje nalepke odpri pokrov"})

        while lid_closed():
            time.sleep(0.01)

        return

    def start_buzzer(self):
        time.sleep(1)
        GPIO.output(gpios['BUZZER'], False)

    def tear_down(self):
        self.shifter.reset()


class EndCalibration(Task):
    # If mid-test fail, calibrate servos so they don't stay in the product
    def set_up(self):
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)

    def run(self):
        self.calibration()
        #self.calibration_thread = threading.Thread(target=self.calibration)
        #self.calibration_thread.start()

        return

    def calibration(self):
        self.nanoboard_small.write("calibrate", 10)

    def tear_down(self):
        self.nanoboard_small.close()


class PrintSticker(Task):
    def set_up(self):
        self.godex = devices.Godex(port_serial="/dev/godex")  # If autoselect choose serial, port to godex (Arduino interference)

        # self.godex_found = False
        # for i in range(10):
        #     try:
        #         self.godex = devices.GoDEXG300(port='/dev/godex', timeout=3.0)
        #         self.godex_found = True
        #         break
        #     except Exception as ee:
        #         print(ee)
        #
        #         time.sleep(0.1)

        # self.godex = devices.Godex(port='/dev/usb/lp0', timeout=3.0)
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)

    def run(self):
        # Unlock test device
        self.shifter.set("K9", False)
        self.shifter.invertShiftOut()

        for i in range(2):
            gui_web.send({"command": "progress", "nest": i, "value": "100"})
            # gui_web.send({"command": "semafor", "nest": i, "blink": (0, 1, 0)})

        # wait for open lid
        if not strips_tester.data['exist'][0] and not strips_tester.data['exist'][1]:
            gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
            module_logger.info("Za konec testa odpri pokrov")
        else:
            module_logger.info("Za tiskanje nalepke odpri pokrov")
            gui_web.send({"command": "status", "value": "Za tiskanje nalepke odpri pokrov"})

        if not self.godex.found:
            for current_nest in range(2):
                if strips_tester.data['exist'][current_nest]:
                    gui_web.send({"command": "error", "nest": current_nest, "value": "Tiskalnika ni mogoče najti!"})
            return

        # Lid is now opened.
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] != -1:  # if product was tested
                try:
                    self.print_sticker(strips_tester.data['status'][0])
                except Exception:
                    pass

        if strips_tester.data['exist'][1]:
            if strips_tester.data['status'][1] != -1:  # if product was tested
                try:
                    self.print_sticker(strips_tester.data['status'][1])
                except Exception:
                    pass

        return

    def print_sticker(self, test_status):
        program = get_program_number()

        code = {}
        code['S001'] = 435545
        code['S002'] = 552943
        qc_id = strips_tester.data['worker_id']

        date = datetime.datetime.utcnow().strftime("%d.%m.%Y")

        if test_status == True:  # Test OK
            inverse = '^L\r'
            darkness = '^H15\r'
        elif test_status == False:  # Test FAIL
            inverse = '^LI\r'
            darkness = '^H4\r'
        else:
            return

        if qc_id != -1:
            qc = "QC {}".format(qc_id)
        else:
            qc = ""

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
                 'E\n').format(darkness, inverse, code[program], " ", program, date, qc)

        self.godex.send_to_printer(label)
        time.sleep(1)

    def tear_down(self):
        try:
            self.godex.close()
        except Exception:
            pass


# Utils part due to import problems
#########################################################################################
def lid_closed():
    # if lid is opened
    state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
    if state_GPIO_SWITCH:
        # module_logger.error("Lid opened /")
        # strips_tester.current_product.task_results.append(False)
        # strips_tester.emergency_break_tasks = True
        return True
    else:
        # module_logger.debug("Lid closed")
        return False
