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

# You may set global test level and logging level in config_loader.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)


'''
PROCEDURE:

START
- izklop vseh relejev

DETEKCIJA KOSOV V TN
- Segger napajanje 5V
- Preverba 5V na obeh kosih 
- Preverba vPot na obeh kosih

ROTACIJA TRIMERJEV
- rotacija servo motorjev (platforma ostane gor!)
- hkrati poteka ICT test za napetosti

ICT TESTI
- sklenitev 220V
- preverba napetosti diod D1, Z1, D1, Z1

- izklop 220V (sedaj mora biti Å¾e v zaÄetni legi trimer

- sklenitev TP5, TP10 da se spraznejo kondenzatorji
- meritev upornosti pri ICT testu (skupno merjenje veÄih)

PROGRAMIRANJE MCU
- S001 ali S002

VIZUALNI PREGLED LED
- sklenitev 220V
- vrtenje trimerjev v konÄno lego
- spustitev platforme

PRINT STICKER
- good or bad

END PROCEDURE TASK
- spustitev platforme
- izklop vseh relejev


'''


# checks if lid is opened
# prevents cyclic import, because gpios aren't available on import time
class LidOpenCheck:
    def __init__(self):
        # if lid is opened
        state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
        if not state_GPIO_SWITCH:
            module_logger.error("Lid opened /")
            # strips_tester.current_product.task_results.append(False)
            # strips_tester.emergency_break_tasks = True
        else:
            module_logger.debug("Lid closed")

def get_program_number():  # Flash program selector

    try:
        program = sys.argv[1]

    except Exception:
        program = "S001"

    return program

class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)
        self.lightboard = devices.MCP23017(0x25)

    def run(self) -> (bool, str):
        strips_tester.data['exist_left'] = False  # Untested
        strips_tester.data['exist_right'] = False  # Untested

        strips_tester.data['status_left'] = -1  # Untested
        strips_tester.data['status_right'] = -1  # Untested

        gui_web.send({"command": "title", "value": "GO-C19 ({})" . format(get_program_number())})

        if "START_SWITCH" in settings.gpios:
            module_logger.info("Za nadaljevanje zapri pokrov")

            gui_web.send({"command": "status", "value": "Za testiranje zapri pokrov."})
            gui_web.send({"command": "progress", "value": "0"})

            # self.lightboard.clear_bit(self.lightboard.LEFT_YELLOW)
            # self.lightboard.clear_bit(self.lightboard.RIGHT_YELLOW)

            while True:
                # GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
                if state_GPIO_SWITCH:
                    # module_logger.info("START_SWITCH pressed(lid closed)")
                    break

                time.sleep(0.01)

            gui_web.send({"command": "error", "value": -1})  # Clear all error messages
            gui_web.send({"command": "info", "value": -1})  # Clear all error messages
            gui_web.send({"command": "nests", "value": 2})

            self.lightboard.set_bit(self.lightboard.LEFT_YELLOW)
            self.lightboard.set_bit(self.lightboard.RIGHT_YELLOW)

            for i in range(2):
                gui_web.send({"command": "blink", "which": i + 1, "value": (0, 0, 0)})
                gui_web.send({"command": "semafor", "which": i + 1, "value": (0, 1, 0)})

            for i in range(3):
                self.lightboard.set_bit(self.lightboard.BUZZER)
                time.sleep(0.1)
                self.lightboard.clear_bit(self.lightboard.BUZZER)
                time.sleep(0.1)

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
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-B5E9C.voltage1", 0.16)
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)

        self.segger_found = False
        for i in range(1):
            try:
                self.segger = devices.Segger("/dev/segger")
                self.segger_found = True
                break
            except Exception:
                time.sleep(0.1)

        self.measurement_results = {}

    def run(self) -> (bool, str):

        #if not self.segger_found:
        #    gui_web.send({"command": "error", "value": "Programatorja ni mogoče najti!"})
        #   return {"signal": [0, "fail", 5, "NA"]}

        #self.segger.select_file(get_program_number())  # Select S001 binary file

        self.shifter.reset()

        #if not lid_closed():
        #    gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!"})
        #
        #    return {"signal": [0, "fail", 5, "NA"]}

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

        self.power_on()  # Power on board (external 5V)

        self.flash_process = multiprocessing.Process(target=self.flashMCU)

        self.shifter.set("K11", True)  # Segger RESET enable

        self.shifter.set("K10", False)  # Segger SWIM Left
        self.shifter.set("K12", False)  # Segger RESET Left
        self.shifter.set("K13", False)  # Segger VCC Left
        self.shifter.set("K14", False)  # Segger GND Left
        self.shifter.invertShiftOut()

        voltage_left = self.measure_voltage("M7", "M3")
        if self.in_range(voltage_left, 4.8, 10):
            strips_tester.data['exist_left'] = True

            module_logger.info("left product detected with %sV of power supply", voltage_left)
            gui_web.send({"command": "info", "value": "Levi kos zaznan na napetosti {}V" . format(voltage_left)})
        else:
            gui_web.send({"command": "info", "value": "Ni zaznanega levega kosa: {}V" . format(voltage_left)})

        if strips_tester.data['exist_left']:
            trimmer_left = self.measure_voltage("M7", "L4")
            angle = (trimmer_left / voltage_left) * 100.0
            # print("Trimmer: {}%, {}V" . format(int(angle),trimmer_left))

            if angle < 5 or angle > 95:
                if angle > 95:
                    flip_left = True

                #self.flash_process.start()

                capacitor_left = self.measure_voltage("M7", "M1")
                if self.in_range(capacitor_left, 1.8, 10):
                    module_logger.info("capacitor voltage in bounds: meas:%sV", capacitor_left)
                    gui_web.send({"command": "info", "value": "Meritev napetosti vCap na levem kosu: {}V" . format(capacitor_left)})
                    self.measurement_results["cap_left"] = [capacitor_left, "ok", 0, "V"]
                else:
                    strips_tester.data['status_left'] = 0
                    module_logger.warning("capacitor voltage out of bounds: meas:%sV", capacitor_left)
                    gui_web.send({"command": "error", "value": "Meritev napetosti vCap na levem kosu je izven območja: {}V" . format(capacitor_left)})
                    self.measurement_results["cap_left"] = [capacitor_left, "fail", 0, "V"]

                vr1_left = self.measure_voltage("L3", "M5")
                if self.in_range(vr1_left, -1.9, 0.2, False):
                    module_logger.info("R1 voltage in bounds: meas:%sV", vr1_left)
                    gui_web.send({"command": "info", "value": "Meritev napetosti R1 na levem kosu: {}V" . format(vr1_left)})
                    self.measurement_results["vR1_left"] = [vr1_left, "ok", 0, "V"]
                else:
                    strips_tester.data['status_left'] = 0
                    module_logger.warning("R1 voltage out of bounds: meas:%sV", vr1_left)
                    gui_web.send({"command": "error", "value": "Meritev napetosti R1 na levem kosu je izven območja: {}V" . format(vr1_left)})
                    self.measurement_results["vR1_left"] = [vr1_left, "fail", 0, "V"]

                resistor_left = self.measure_voltage("L4", "M5")
                expected_voltage = - voltage_left + trimmer_left

                if self.in_range(resistor_left, expected_voltage, 1, False):  # Should be in absolute (not in percent)
                    module_logger.info("R2 voltage in bounds: meas:%sV", resistor_left)
                    gui_web.send({"command": "info", "value": "Meritev napetosti R2 na levem kosu: {}V" . format(resistor_left)})
                    self.measurement_results["vR2_left"] = [resistor_left, "ok", 0, "V"]
                else:
                    strips_tester.data['status_left'] = 0
                    module_logger.warning("R2 voltage out of bounds: meas:%sV", resistor_left)
                    gui_web.send({"command": "error", "value": "Meritev napetosti R2 na levem kosu je izven območja: {}V" . format(resistor_left)})
                    self.measurement_results["vR2_left"] = [resistor_left, "fail", 5, "V"]
                    stop = True  # Can't determine trimmer position

                # Wait flashing to be done.
                #self.flash_process.join()
            else:
                strips_tester.data['status_left'] = 0
                module_logger.error("left trimmer not in end position! ({}%)".format(angle))
                gui_web.send({"command": "error", "value": "Potenciometer na levem kosu ni na končnem položaju ({}%)." . format(angle)})
                self.measurement_results["trimmer_left"] = [angle, "fail", 5, "deg"]
                stop = True
        else:
            gui_web.send({"command": "semafor", "which": 1, "value": (0, 0, 0)})

        # Make process for right side programming
        #self.flash_process = multiprocessing.Process(target=self.flashMCU)

        # 5V right
        self.shifter.set("K10", True)  # Segger SWIM Right
        self.shifter.set("K12", True)  # Segger RESET Right
        self.shifter.set("K13", True)  # Segger VCC Right
        self.shifter.set("K14", True)  # Segger GND Right
        self.shifter.invertShiftOut()

        gui_web.send({"command": "status", "value": "Detekcija desnega kosa..."})
        voltage_right = self.measure_voltage("L11", "L7")
        if self.in_range(voltage_right, 4.8, 10):
            strips_tester.data['exist_right'] = True
            module_logger.info("right product detected with %sV of power supply", voltage_right)
            gui_web.send({"command": "info", "value": "Desni kos zaznan na napetosti {}V" . format(voltage_right)})
        else:
            gui_web.send({"command": "info", "value": "Ni zaznanega desnega kosa: {}V" . format(voltage_right)})

        if strips_tester.data['exist_right']:
            trimmer_right = self.measure_voltage("K8", "L11")
            angle = (trimmer_right / voltage_right) * 100.0
            print("Trimmer: {}%, {}V".format(int(angle), trimmer_right))

            if angle < 5 or angle > 95:
                if angle > 95:
                    flip_right = True

                #self.flash_process.start()

                capacitor_right = self.measure_voltage("L5", "L11")
                if self.in_range(capacitor_right, 1.8, 10):
                    module_logger.info("capacitor voltage in bounds: meas:%sV", capacitor_right)
                    gui_web.send({"command": "info", "value": "Meritev napetosti vCap na desnem kosu: {}V" . format(capacitor_right)})
                    self.measurement_results["cap_right"] = [capacitor_right, "ok", 0, "V"]
                else:
                    strips_tester.data['status_right'] = 0
                    module_logger.warning("capacitor voltage out of bounds: meas:%sV", capacitor_right)
                    gui_web.send({"command": "error", "value": "Meritev napetosti vCap na desnem kosu je izven območja: {}V" . format(capacitor_right)})
                    self.measurement_results["cap_right"] = [capacitor_right, "fail", 0, "V"]

                vr1_right = self.measure_voltage("K7", "L9")
                if self.in_range(vr1_right, -1.9, 0.2, False):
                    module_logger.info("R1 voltage in bounds: meas:%sV", vr1_right)
                    gui_web.send({"command": "info", "value": "Meritev napetosti R1 na desnem kosu: {}V" . format(vr1_right)})
                    self.measurement_results["vR1_right"] = [vr1_right, "ok", 0, "V"]
                else:
                    strips_tester.data['status_right'] = 0
                    module_logger.warning("R1 voltage out of bounds: meas:%sV", vr1_right)
                    gui_web.send({"command": "error", "value": "Meritev napetosti R1 na desnem kosu je izven območja: {}V" . format(vr1_right)})
                    self.measurement_results["vR1_right"] = [vr1_right, "fail", 0, "V"]

                resistor_right = self.measure_voltage("K8", "L9")
                expected_voltage = - voltage_right + trimmer_right
                print("EXPECTED_RIGHT: {}".format(expected_voltage))

                if self.in_range(resistor_right, expected_voltage, 1, False):  # Should be in absolute (not in percent)
                    module_logger.info("R2 voltage in bounds: meas:%sV", resistor_right)
                    gui_web.send({"command": "info", "value": "Meritev napetosti R2 na desnem kosu: {}V" . format(resistor_right)})
                    self.measurement_results["vR2_right"] = [resistor_right, "ok", 0, "V"]
                else:
                    strips_tester.data['status_right'] = 0
                    module_logger.warning("R2 voltage out of bounds: meas:%sV", resistor_right)
                    gui_web.send({"command": "error", "value": "Meritev napetosti R1 na desnem kosu je izven območja: {}V" . format(resistor_right)})
                    self.measurement_results["vR2_right"] = [resistor_right, "fail", 5, "V"]
                    stop = True  # Can't determine trimmer position

                # Wait flashing to be done.
                #self.flash_process.join()
            else:
                strips_tester.data['status_right'] = 0
                module_logger.error("right trimmer not in end position! ({}%)".format(angle))
                gui_web.send({"command": "error", "value": "Potenciometer na desnem kosu ni na končnem položaju ({}%)." . format(angle)})
                self.measurement_results["trimmer_right"] = [angle, "fail", 5, "deg"]
                stop = True
        else:
            gui_web.send({"command": "semafor", "which": 2, "value": (0, 0, 0)})

        gui_web.send({"command": "status", "value": "Kalibracija..."})

        self.shifter.set("K10", False)  # Segger SWIM Left
        self.shifter.set("K12", False)  # Segger RESET Left
        self.shifter.set("K13", False)  # Segger VCC Left
        self.shifter.set("K14", False)  # Segger GND Left
        self.shifter.set("K11", False)  # Segger RESET disable
        self.shifter.invertShiftOut()

        self.power_off()
        self.calibration_thread.join()  # Wait for servo to calibrate

        if not stop:
            if flip_left and flip_right:
                # Flip both servos
                self.nanoboard_small.write("servo 3 100")
            else:
                if flip_left:
                    # Flip left
                    self.nanoboard_small.write("servo 1 100")

                if flip_right:
                    # Flip right
                    self.nanoboard_small.write("servo 2 100")

        '''
        if strips_tester.data['exist_left']:
            angle = (trimmer_left / voltage_left) * 100.0

            print("rotate left to {}" . format(int(angle)))
            self.nanoboard_small.servo(1, int(angle))

        if strips_tester.data['exist_right']:
            angle = (trimmer_right / voltage_right) * 100.0
            print("rotate right to {}" . format(int(angle)))
            self.nanoboard_small.servo(2, int(angle))
        '''

        # Upoštevaj flip! (zato se servo ne obrne desni!) (ce je angle  vecji 50)
        # Platforma naj ostane gor

        return self.measurement_results

    def power_on(self):
        GPIO.output(gpios['POWER'], GPIO.HIGH)

    def power_off(self):
        GPIO.output(gpios['POWER'], GPIO.LOW)

    def calibration(self):
        self.nanoboard_small.write("calibrate")

    def measure_voltage(self, testpad1, testpad2):
        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        voltage = self.voltmeter.read()
        # print("Voltage: {}V" . format(voltage))
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

    def flashMCU(self):  # functional
        status = self.segger.download()
        gui_web.send({"command": "status", "value": "Programiranje..."})

        if status:
            module_logger.info("flashing ok ({})".format(get_program_number()))
            gui_web.send({"command": "info", "value": "Programiranje uspelo {}." . format(get_program_number())})
        else:
            module_logger.warning("error flashing ({})".format(get_program_number()))
            gui_web.send({"command": "error", "value": "Programiranje ni uspelo {}." . format(get_program_number())})

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
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)

        for i in range(10):
            try:
                self.ohmmeter = devices.DigitalMultiMeter("/dev/ohmmeter")
                break
            except Exception:
                time.sleep(0.2)

        self.measurement_results = {}

    def run(self) -> (bool, str):
        if not lid_closed():
            gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!"})
            return {"signal": [0, "fail", 5, "NA"]}

        if not strips_tester.data['exist_right'] and not strips_tester.data['exist_left']:
            return {"signal": [0, "fail", 5, "no products exist"]}

        gui_web.send({"command": "status", "value": "ICT Meritev upornosti..."})

        # Lock test device
        self.shifter.set("K9", True)
        self.shifter.invertShiftOut()

        # Initiate servo calibration
        self.servo_thread = threading.Thread(target=self.zero_trimmers)
        self.servo_thread.start()

        gui_web.send({"command": "progress", "value": "10"})

        self.power_off()  # Just to make sure
        self.make_short("M5", "M7")  # We make sure capacitors are discharged
        self.make_short("L9", "L7")  # We make sure capacitors are discharged

        if strips_tester.data['exist_left'] and strips_tester.data['status_left'] != 0:
            self.shifter.set("K13", True)  # Segger VCC Right
            self.shifter.set("K14", True)  # Segger GND Right
            self.shifter.set("K12", True)  # Segger RESET Left
            self.shifter.invertShiftOut()

            r3_left = self.measure_resistance("R3_left", "L2", "M13", 47, 30)
            r9_left = self.measure_resistance("R9_left", "M16", "M9", 180)
            r8_left = self.measure_resistance("R8_left", "M10", "M8", 220)

        gui_web.send({"command": "progress", "value": "15"})

        if strips_tester.data['exist_right'] and strips_tester.data['status_right'] != 0:
            self.shifter.set("K13", False)  # Segger VCC Right
            self.shifter.set("K14", False)  # Segger GND Right
            self.shifter.set("K12", False)  # Segger RESET Left
            self.shifter.invertShiftOut()

            r3_right = self.measure_resistance("R3_right", "K6", "L16", 47, 30)
            r9_right = self.measure_resistance("R9_right", "L13", "K4", 180)
            r8_right = self.measure_resistance("R8_right", "K3", "L12", 220)

            r4_right = self.measure_resistance("R4_right", "L15", "K6", 220000)
            r5_right = self.measure_resistance("R5_right", "L14", "K5", 220000)

            if r3_right == -1 or r9_right == -1 or r8_right == -1 or r4_right == -1 or r5_right == -1:
                strips_tester.data['status_right'] = 0

        gui_web.send({"command": "progress", "value": "20"})

        if strips_tester.data['exist_left'] and strips_tester.data['status_left'] != 0:
            self.shifter.set("K13", True)  # Segger VCC Right
            self.shifter.set("K14", True)  # Segger GND Right
            self.shifter.set("K12", True)  # Segger RESET Left
            self.shifter.invertShiftOut()

            r4_left = self.measure_resistance("R4_left", "L2", "M14", 220000)
            r5_left = self.measure_resistance("R5_left", "L1", "M15", 220000)

            if r3_left == -1 or r9_left == -1 or r8_left == -1 or r4_left == -1 or r5_left == -1:
                strips_tester.data['status_left'] = 0

        gui_web.send({"command": "progress", "value": "25"})
        self.servo_thread.join()  # Wait until trimmers are zeroed

        return self.measurement_results

    def zero_trimmers(self):
        # Assuming servos are already in position as the trimmers
        self.nanoboard_small.write("move 20")

        # BUG -> if servo is over the 50, it wont turn
        self.nanoboard_small.write("servo 3 0")  # Zero both servos

        # Upoštevaj flip! (zato se servo ne obrne desni!) (ce je angle  vecji 50)
        # Platforma naj ostane gor

        return

    def measure_resistance(self, name, testpad1, testpad2, expected, tolerance=20):
        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        num_of_tries = 20

        resistance = self.ohmmeter.read().numeric_val
        if resistance is None:
            resistance = -1

        while not self.in_range(resistance, expected, tolerance):
            num_of_tries = num_of_tries - 1

            resistance = self.ohmmeter.read().numeric_val

            if resistance is None:
                resistance = -1

            module_logger.debug("   Retrying... {}ohm".format(resistance))

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("%s out of bounds: meas:%sohm", name, resistance)
            gui_web.send({"command": "error", "value": "Meritev upornosti {} je izven območja: {}ohm".format(name,resistance)})
            self.measurement_results[name] = [resistance, "fail", 0, "ohm"]
            resistance = -1
        else:
            module_logger.info("%s in bounds: meas:%sohm", name, resistance)
            gui_web.send({"command": "info", "value": "Meritev upornosti {}: {}ohm".format(name,resistance)})
            self.measurement_results[name] = [resistance, "ok", 0, "ohm"]

        self.shifter.set(testpad1, False)
        self.shifter.set(testpad2, False)
        self.shifter.invertShiftOut()

        time.sleep(0.01)

        return resistance

    def power_off(self):
        GPIO.output(gpios['POWER'], GPIO.LOW)

    def make_short(self, vccpad, gndpad):
        time.sleep(0.01)
        self.shifter.set(vccpad, True)
        self.shifter.set(gndpad, True)
        self.shifter.invertShiftOut()
        time.sleep(0.5)
        self.shifter.set(vccpad, False)
        self.shifter.set(gndpad, False)
        self.shifter.invertShiftOut()
        time.sleep(0.01)

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
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-B5E9C.voltage1", 0.16)  # Rectified DC Voltage
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.nanoboard_small = devices.ArduinoSerial('/dev/arduino', baudrate=115200)

        self.measurement_results = {}

        self.led_gpio = [40, 37, 38, 35, 36, 33]

        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        # Prepare GPIO list for visual test (left leds, right leds)
        for current in self.led_gpio:
            GPIO.setup(current, GPIO.IN)

    def run(self) -> (bool, str):
        if not lid_closed():
            gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!"})
            return {"signal": [0, "fail", 5, "NA"]}

        if not strips_tester.data['exist_right'] and not strips_tester.data['exist_left']:
            return {"signal": [0, "fail", 5, "no products exist"]}

        gui_web.send({"command": "status", "value": "Vizualni pregled LED diod"})

        # Lock test device
        self.shifter.set("K9", True)
        self.shifter.invertShiftOut()

        self.power_off()  # We make sure that test device is galvanic isolated from product
        self.shifter.set("K11", False)  # Segger RESET disable (so both MCU are running)
        self.shifter.invertShiftOut()

        # skleni L, N
        self.shifter.set("K16", True)  # L
        self.shifter.set("K15", True)  # N
        self.shifter.invertShiftOut()

        module_logger.info("VISUAL TEST STARTING...")
        # Initiate ICT voltage test
        self.ict_thread = threading.Thread(target=self.ICTVoltageACTest)
        self.ict_thread.start()

        gui_web.send({"command": "progress", "value": "30"})
        visual_start = self.check_mask([0, 0, 1], 7)

        if strips_tester.data['exist_left']:
            if not visual_start[0]:
                module_logger.error("VisualStart LEFT")
                self.measurement_results['visualStart_left'] = [0, "fail", 0, "N/A"]
                gui_web.send({"command": "error", "value": "Napaka LED diod na levem kosu (VisualStart)"})
                strips_tester.data['status_left'] = 0
            else:
                module_logger.info("VisualStart LEFT")
                gui_web.send({"command": "info", "value": "Test LED diod na levem kosu (VisualStart) ustrezen"})
                self.measurement_results['visualStart_left'] = [1, "ok", 0, "N/A"]

        if strips_tester.data['exist_right']:
            if not visual_start[1]:
                module_logger.error("VisualStart RIGHT")
                self.measurement_results['visualStart_right'] = [0, "fail", 0, "N/A"]
                gui_web.send({"command": "error", "value": "Napaka LED diod na desnem kosu (VisualStart)"})
                strips_tester.data['status_right'] = 0
            else:
                module_logger.info("VisualStart RIGHT")
                gui_web.send({"command": "info", "value": "Test LED diod na desnem kosu (VisualStart) ustrezen"})
                self.measurement_results['visualStart_right'] = [1, "ok", 0, "N/A"]
        
        # Wait until leds are off
        visual_off = self.check_mask([1, 1, 1], 4)
        gui_web.send({"command": "progress", "value": "40"})

        if strips_tester.data['exist_left']:
            if not visual_off[0]:
                module_logger.error("VisualOff LEFT")
                strips_tester.data['status_left'] = 0
                gui_web.send({"command": "error", "value": "Napaka LED diod na levem kosu (VisualOff)"})
            else:
                module_logger.info("VisualOff LEFT")
                gui_web.send({"command": "info", "value": "Test LED diod na levem kosu (VisualOff) ustrezen"})

        if strips_tester.data['exist_right']:
            if not visual_off[1]:
                module_logger.error("VisualOff RIGHT")
                strips_tester.data['status_right'] = 0
                gui_web.send({"command": "error", "value": "Napaka LED diod na desnem kosu (VisualOff)"})
            else:
                module_logger.info("VisualOff RIGHT")
                gui_web.send({"command": "info", "value": "Test LED diod na desnem kosu (VisualOff) ustrezen"})

        # Check for errors
        visual_err = self.check_mask([0, 1, 1], 1)
        gui_web.send({"command": "progress", "value": "50"})

        if strips_tester.data['exist_left']:
            if visual_err[0]:
                module_logger.info("VisualError LEFT")
                self.measurement_results['visualOff_left'] = [0, "fail", 0, "N/A"]
                gui_web.send({"command": "error", "value": "Napaka LED diod na level kosu (VisualError)"})
                strips_tester.data['status_left'] = 0
            else:
                self.measurement_results['visualOff_left'] = [1, "ok", 0, "N/A"]
                gui_web.send({"command": "info", "value": "Test LED diod na levem kosu (VisualError) ustrezen"})

        if strips_tester.data['exist_right']:
            if visual_err[1]:
                module_logger.info("VisualError RIGHT")
                self.measurement_results['visualOff_right'] = [0, "fail", 0, "N/A"]
                strips_tester.data['status_right'] = 0
                gui_web.send({"command": "error", "value": "Napaka LED diod na desnem kosu (VisualError)"})
            else:
                self.measurement_results['visualOff_right'] = [1, "ok", 0, "N/A"]
                gui_web.send({"command": "info", "value": "Test LED diod na desnem kosu (VisualError) ustrezen"})

        self.nanoboard_small.write("servo 3 100")
        self.nanoboard_small.write("move 0")

        visual_on = self.check_mask([0, 0, 0], 5)
        gui_web.send({"command": "progress", "value": "60"})

        if strips_tester.data['exist_left']:
            if not visual_on[0]:
                module_logger.error("VisualOn LEFT")
                self.measurement_results['visualOn_left'] = [0, "fail", 0, "N/A"]
                gui_web.send({"command": "error", "value": "Napaka LED diod na levem kosu (VisualOn)"})
                strips_tester.data['status_left'] = 0
            else:
                module_logger.info("VisualOn LEFT")
                self.measurement_results['visualOn_left'] = [1, "ok", 0, "N/A"]
                gui_web.send({"command": "info", "value": "Test LED diod na levem kosu (VisualOn) ustrezen"})

        if strips_tester.data['exist_right']:
            if not visual_on[1]:
                module_logger.error("VisualOn RIGHT")
                self.measurement_results['visualOn_right'] = [0, "fail", 0, "N/A"]
                gui_web.send({"command": "error", "value": "Napaka LED diod na desnem kosu (VisualOn)"})
                strips_tester.data['status_right'] = 0
            else:
                module_logger.info("VisualOn RIGHT")
                self.measurement_results['visualOn_right'] = [1, "ok", 0, "N/A"]
                gui_web.send({"command": "info", "value": "Test LED diod na desnem kosu (VisualOn) ustrezen"})

        self.ict_thread.join()  # Wait until ICT voltage test is finished
        gui_web.send({"command": "progress", "value": "70"})

        # razkleni L, N
        self.shifter.set("K16", False)  # L
        self.shifter.set("K15", False)  # N
        self.shifter.invertShiftOut()

        return self.measurement_results

    def ICTVoltageACTest(self):
        if strips_tester.data['exist_left']:
            voltage_5v = self.measure_voltage("5V_left", "M3", "M7", 4.7, 0.3)
            voltage_d1 = self.measure_voltage("D1_left", "M4", "M7", 2.3, 0.3)
            voltage_z1 = self.measure_voltage("Z1_left", "M4", "M5", -2.3, 0.3)

            if voltage_5v == -1 or voltage_d1 == -1 or voltage_z1 == -1:
                strips_tester.data['status_left'] = 0

        if strips_tester.data['exist_right']:
            voltage_5v = self.measure_voltage("5V_right", "L7", "L11", 4.7, 0.3)
            voltage_d1 = self.measure_voltage("D1_right", "L8", "L11", 2.3, 0.3)
            voltage_z1 = self.measure_voltage("Z1_right", "L8", "L9", -2.3, 0.3)

            if voltage_5v == -1 or voltage_d1 == -1 or voltage_z1 == -1:
                strips_tester.data['status_right'] = 0

    def check_mask(self, mask=[], duration=0):
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)

        while datetime.datetime.now() < end_time:
            state_list = []

            for current in range(len(self.led_gpio)):
                state_list.append(GPIO.input(self.led_gpio[current]))

                #print("{} -> [{}] {}".format(current, mask[current], state_list[-1]))


            #print(state_list, end='')
            #print(" should be ", end='')
            #print(mask)

            time.sleep(0.05)

            result = [not strips_tester.data['exist_left'], not strips_tester.data['exist_right']]

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

    def measure_voltage(self, name, testpad1, testpad2, expected, tolerance=15):
        self.shifter.set(testpad1, True)
        self.shifter.set(testpad2, True)
        self.shifter.invertShiftOut()

        num_of_tries = 20
        time.sleep(0.2)

        voltage = self.voltmeter.read()

        while not self.in_range(voltage, expected, tolerance, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            # print("   Retrying... {}V" . format(voltage))

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("%s out of bounds: meas:%sV", name, voltage)
            gui_web.send({"command": "error", "value": "Meritev napetosti {} je izven območja: {}V" . format(name,voltage)})
            self.measurement_results[name] = [voltage, "fail", 0, "V"]
            voltage = -1
        else:
            module_logger.info("%s in bounds: meas:%sV", name, voltage)
            gui_web.send({"command": "info", "value": "Meritev napetosti {}: {}V" . format(name,voltage)})
            self.measurement_results[name] = [voltage, "ok", 0, "V"]

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
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("ProductConfigTask init")

    def run(self):
        if strips_tester.data['exist_left']:
            if strips_tester.data['status_left'] == -1:  # untested prodcut became tested
                strips_tester.data['status_left'] = 1

        if strips_tester.data['exist_right']:
            if strips_tester.data['status_right'] == -1:
                strips_tester.data['status_right'] = 1

        gui_web.send({"command": "progress", "value": "80"})
        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        pass

class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

        self.shifter = devices.HEF4094BT(24, 31, 26, 29)
        self.lightboard = devices.MCP23017(0x25)

    def run(self):
        strips_tester.data['result_ok'] = 0
        strips_tester.data['result_fail'] = 0

        gui_web.send({"command": "progress", "value": "90"})

        for i in range(2):
            gui_web.send({"command": "semafor", "which": i + 1, "value": (0, 0, 0)})
            gui_web.send({"command": "blink", "which": i + 1, "value": (0, 0, 0)})

        self.lightboard.clear_bit(self.lightboard.LEFT_YELLOW)
        self.lightboard.clear_bit(self.lightboard.RIGHT_YELLOW)

        if strips_tester.data['exist_left']:
            if strips_tester.data['status_left'] == 1:  # test ok
                strips_tester.data['result_ok'] += 1

                # Turn left green on
                self.lightboard.set_bit(self.lightboard.LEFT_GREEN)
                gui_web.send({"command": "semafor", "which": 1, "value": (0, 0, 1)})
            elif strips_tester.data['status_left'] == 0:  # test fail
                strips_tester.data['result_fail'] += 1

                self.lightboard.set_bit(self.lightboard.LEFT_RED)
                self.lightboard.set_bit(self.lightboard.BUZZER)
                gui_web.send({"command": "semafor", "which": 1, "value": (1, 0, 0)})

        if strips_tester.data['exist_right']:
            if strips_tester.data['status_right'] == 1:  # test ok
                strips_tester.data['result_ok'] += 1

                # Turn left green on
                self.lightboard.set_bit(self.lightboard.RIGHT_GREEN)
                gui_web.send({"command": "semafor", "which": 2, "value": (0, 0, 1)})
            elif strips_tester.data['status_right'] == 0:  # test fail
                strips_tester.data['result_fail'] += 1

                self.lightboard.set_bit(self.lightboard.RIGHT_RED)
                self.lightboard.set_bit(self.lightboard.BUZZER)
                gui_web.send({"command": "semafor", "which": 2, "value": (1, 0, 0)})
        time.sleep(1)

        # Turn buzzer off
        self.lightboard.clear_bit(self.lightboard.BUZZER)

        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        self.shifter.reset()

class PrintSticker(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.godex = devices.Godex(port='/dev/usb/lp0', timeout=3.0)
        self.shifter = devices.HEF4094BT(24, 31, 26, 29)

    def run(self):
        # Unlock test device
        self.shifter.set("K9", False)
        self.shifter.invertShiftOut()

        gui_web.send({"command": "progress", "value": "95"})

        # wait for open lid
        if not strips_tester.data['exist_right'] and not strips_tester.data['exist_left']:
            gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
            module_logger.info("Za konec testa odpri pokrov")
        else:
            module_logger.info("Za tiskanje nalepke odpri pokrov")
            gui_web.send({"command": "status", "value": "Za tiskanje nalepke odpri pokrov"})

        while lid_closed():
            time.sleep(0.01)

        # Lid is now opened.
        if strips_tester.data['exist_left']:
            if strips_tester.data['status_left'] != -1:  # if product was tested

                if strips_tester.data['exist_right'] and strips_tester.data['status_right'] != -1:
                    module_logger.info("Prilepi prvo natiskano nalepko na LEVI kos.")

                try:
                    self.print_sticker(strips_tester.data['status_left'])
                except Exception:
                    pass

        if strips_tester.data['exist_right']:
            if strips_tester.data['status_right'] != -1:  # if product was tested
                if strips_tester.data['exist_left'] and strips_tester.data['status_left'] != -1:
                    module_logger.info("Prilepi drugo natiskano nalepko na DESNI kos.")

                try:
                    self.print_sticker(strips_tester.data['status_right'])
                except Exception:
                    pass

        gui_web.send({"command": "progress", "value": "100"})
        return {"signal": [1, 'ok', 0, 'NA']}

    def print_sticker(self, test_status):
        program = get_program_number()

        code = {}
        code['S001'] = 435545
        code['S002'] = 552943
        qc_id = -1

        date = datetime.datetime.now().strftime("%d.%m.%Y")

        if test_status == 1:  # Test OK
            inverse = '^L\r'
            darkness = '^H15\r'
        else:  # Test FAIL
            inverse = '^LI\r'
            darkness = '^H4\r'

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
