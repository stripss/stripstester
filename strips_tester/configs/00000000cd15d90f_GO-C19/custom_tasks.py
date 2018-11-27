
import importlib
import logging
import sys
import time
import multiprocessing
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import settings, server
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
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # Initialize NanoBoards
        self.nanoboard = self.use_device('NanoBoard')
        self.nanoboard_small = self.use_device('NanoBoardSmall')

        # Initialize Voltmeter
        self.voltmeter = self.use_device('voltmeter')


        # Initialize LightBoard
        self.lightboard = self.use_device('LightBoard')

        # How much distance from one pogoplate to the other
        self.shift = 17

        time.sleep(self.get_definition("start_time"))

        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        if not self.is_lid_closed():
            server.send_broadcast({"text": {"text": "Za začetek testa zapri pokrov.\n", "tag": "black"}})

        while not self.is_lid_closed():
            time.sleep(0.1)

        # Lock test device
        #GPIO.output(gpios['LOCK'], False)

        # Hide all indicator lights
        self.lightboard.clear_bit(0xFFFF)

        for i in range(3):
            time.sleep(0.1)
            self.lightboard.set_bit(self.lightboard.BUZZER)
            time.sleep(0.1)
            self.lightboard.clear_bit(self.lightboard.BUZZER)

        # Working lights on
        self.lightboard.set_bit(self.lightboard.LEFT_YELLOW)
        self.lightboard.set_bit(self.lightboard.RIGHT_YELLOW)

        self.nanoboard.calibrate()
        self.nanoboard_small.calibrate()

    def run(self) -> (bool, str):
        stop = False
        flip_left = False
        flip_right = False

        # Skleni L in N
        GPIO.output(gpios['FAZA'], False)
        GPIO.output(gpios['NULA'], False)

        # BOARD DETECTION
        for current in range(2):
            max_voltage = self.probeVolt(7 + self.shift * current) # Measure 5V

            if max_voltage > 1.5: # Product exist
                strips_tester.product[current].exist = True
                strips_tester.product[current].serial = self.configure_serial(current)

                if current:
                    server.send_broadcast({"text": {"text": "Zaznan desni kos.\n", "tag": "black"}})
                else:
                    server.send_broadcast({"text": {"text": "Zaznan levi kos.\n", "tag": "black"}})

            else:
                if max_voltage > 0.2:
                    if current:
                        server.send_broadcast({"text": {"text": "Kritična napaka desnega kosa!\n", "tag": "red"}})
                    else:
                        server.send_broadcast({"text": {"text": "Kritična napaka levega kosa!\n", "tag": "red"}})

                    raise Exception("Voltage below 1.5V (diode may be faulty)")
                else:
                    if current:
                        server.send_broadcast({"text": {"text": "Ni zaznanega desnega kosa.\n", "tag": "grey"}})
                    else:
                        server.send_broadcast({"text": {"text": "Ni zaznanega levega kosa.\n", "tag": "grey"}})

            if strips_tester.product[current].exist:
                voltage = abs(self.probeVolt(12 + self.shift * current))

                # Izracunaj razliko med napetostjo na potenciometru in napajalno napetostjo
                potentiometer = max_voltage - voltage

                # Ce napetost odstopa za vec kot 0.4, potem je potenciometer obrnjen
                if potentiometer < 0.4:  # Is potentiometer on zero value?
                    strips_tester.product[current].add_measurement(type(self).__name__, "PotentiometerInitialValue", Task.TASK_OK, potentiometer)
                else:
                    if voltage < 0.3:
                        if current:
                            flip_right = True
                            server.send_broadcast({"text": {"text": "Potenciometer na desnem kosu je v končnem položaju.\n", "tag": "yellow"}})

                        else:
                            flip_left = True
                            server.send_broadcast({"text": {"text": "Potenciometer na levem kosu je v končnem položaju.\n", "tag": "yellow"}})
                    else:
                        strips_tester.product[current].add_measurement(type(self).__name__, "PotentiometerInitialValue", Task.TASK_FAIL, potentiometer)

                        if current:
                            server.send_broadcast({"text": {"text": "Potenciometer na desnem kosu ni na začetnem položaju!\n", "tag": "red"}})
                        else:
                            server.send_broadcast({"text": {"text": "Potenciometer na levem kosu ni na začetnem položaju!\n", "tag": "red"}})

                        stop = True

        # Razkleni L in N
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        exist = []
        for current in range(2):
            if strips_tester.product[current].exist:
                exist.append(True)
            else:
                exist.append(False)

        if not any(exist):
            server.send_broadcast({"text": {"text": "Ni zaznanih kosov v nobenem izmed ležišč.\n", "tag": "black"}})
            raise Exception("No products found in nests.")

        if stop:
            server.send_broadcast({"text": {"text": "Ročno nastavite potenciometer v skrajni levi položaj in poskusite ponovno.\n", "tag": "black"}})

            # Eliminate good measurements for false report as it is working
            for current in range(2):
                if strips_tester.product[current].exist and strips_tester.product[current].ok == Task.TASK_OK:
                    strips_tester.product[current].exist = False
        else:
            if flip_left or flip_right:
                # Write warning
                #server.send_broadcast({"text": {"text": "Kosi morajo pred testiranjem imeti potenciometer v skrajnem desnem položaju.\n", "tag": "yellow"}})

                if flip_left and flip_right:
                    # Flip both servos
                    self.nanoboard_small.send_command(108,100)
                else:
                    if flip_left:
                        # Flip left
                        self.nanoboard_small.servo(1,100)

                    if flip_right:
                        # Flip right
                        self.nanoboard_small.servo(2,100)

                # Rise the platform, in the mean time camera is initialized
                self.nanoboard_small.moveStepper(20)

                # Move both servos to zero
                self.nanoboard_small.send_command(108,0)

                # Rise the platform, in the mean time camera is initialized
                self.nanoboard_small.moveStepper(0)
        return type(self).__name__


    def tear_down(self):
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        #GPIO.output(gpios['LOCK'], True)

        time.sleep(self.get_definition("end_time"))

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def probeVolt(self,index):
        self.nanoboard.relay(0)
        self.nanoboard.moveStepper(index)
        self.nanoboard.connect()

        self.voltmeter.read()
        time.sleep(1)
        for i in range(3):
            voltage = self.voltmeter.read()
            print(voltage)
            time.sleep(0.1)

        self.nanoboard.disconnect()

        return voltage

    def in_range(self, value, definition, tolerance):
        expected = self.get_definition(definition)
        if self.is_unit_percent(self.get_definition_unit(tolerance)):
            #print("in_range: {} is in percent" . format(tolerance))
            tolerance_min = expected - expected * (self.get_definition(tolerance) / 100.0)
            tolerance_max = expected + expected * (self.get_definition(tolerance) / 100.0)
        else:
            #print("in_range: {} is not percent" . format(tolerance))
            tolerance_min = expected - self.get_definition(tolerance)
            tolerance_max = expected + self.get_definition(tolerance)

        if value > tolerance_min and value < tolerance_max:
            return True
        else:
            return False

    def configure_serial(self,product):
        # Get last ID from DB
        last_test_id = strips_tester.TestDevice_Product.objects.last().test_id

        serial = str(last_test_id) + str(product)
        # Serial should look like 20150 and 20151

        return serial

# ALMOST DONE
# - needs right indicators to light up
class EndProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # Initialize LightBoard
        self.lightboard = self.use_device('LightBoard')

    def run(self) -> (bool, str):
        server.send_broadcast({"text": {"text": "Odprite pokrov in odstranite testirane kose.\n", "tag": "black"}})
        GPIO.output(gpios['LOCK'],True)

        while self.is_lid_closed():
            time.sleep(0.1)

        self.lightboard.clear_bit(0xFFFF) # Clear all lights

        beep = False
        if strips_tester.product[0].exist:
            if strips_tester.product[0].ok: # Product is bad
                beep = True
                self.lightboard.set_bit(self.lightboard.LEFT_RED) # Red left light
            else:
                self.lightboard.set_bit(self.lightboard.LEFT_GREEN) # Green left light
        else:
            self.lightboard.clear_bit(self.lightboard.LEFT_YELLOW) # No left light

        if strips_tester.product[1].exist:
            if strips_tester.product[1].ok:  # Product is bad
                beep = True
                self.lightboard.set_bit(self.lightboard.RIGHT_RED)  # Red right light
            else:
                self.lightboard.set_bit(self.lightboard.RIGHT_GREEN)  # Green right light
        else:
            self.lightboard.clear_bit(self.lightboard.RIGHT_YELLOW)  # No right light

        if not strips_tester.product[0].exist and not strips_tester.product[1].exist:
            beep = True

        if beep:
            self.lightboard.set_bit(self.lightboard.BUZZER)
            time.sleep(1)
            self.lightboard.clear_bit(self.lightboard.BUZZER)

        return type(self).__name__

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def tear_down(self):
        GPIO.output(gpios['LOCK'],True)


class VisualTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.camera = cv2.VideoCapture(0)  # video capture source camera
        self.threshold = 150

        self.roi_x = 80
        self.roi_y = 80
        self.roi_width = 490
        self.roi_height = 280

        self.led = []
        for i in range(6):
            self.led.append({}) # Append dictionary
            self.led[-1]['x'] = self.get_definition("led{}_posx" . format(i + 1))
            self.led[-1]['y'] = self.get_definition("led{}_posy" . format(i + 1))

        self.nanoboard_small = self.use_device('NanoBoardSmall')
        #self.nanoboard_small.calibrate()

        #GPIO.output(gpios['LOCK'],False)

    # Why seperated process?
    # Segger causing LED to stop working (we must switch to other nest for testing)


    def run(self) -> (bool, str):
        # Razkleni stik pri reset pinu
        GPIO.output(gpios['RESET_ENABLE'], False)

        # Rotate both servos on zero
        self.nanoboard_small.send_command(108,0)

        # Rise the platform, in the mean time camera is initialized
        self.nanoboard_small.moveStepper(20)

        # Check if both products are ok and if they exist
        if strips_tester.product[0].exist and strips_tester.product[0].ok != Task.TASK_OK and strips_tester.product[1].exist and strips_tester.product[1].ok != Task.TASK_OK:
            # Rotate both servos to 270 degrees
            self.nanoboard_small.send_command(108, 100)
        else:
            # Sklenitev 230VAC
            GPIO.output(gpios['FAZA'], False)
            GPIO.output(gpios['NULA'], False)

            self.get_light_states()

            if strips_tester.product[1].exist and strips_tester.product[1].ok == Task.TASK_OK:
                if self.check_mask([1, 1, -1, -1, -1, -1]):  # Does LED turn on?
                    strips_tester.product[1].add_measurement(type(self).__name__, "VisualStart", Task.TASK_OK, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled desnega kosa (VisualStart)\n", "tag": "green"}})
                else:
                    strips_tester.product[1].add_measurement(type(self).__name__, "VisualStart", Task.TASK_WARNING, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled desnega kosa (VisualStart)\n", "tag": "red"}})

            if strips_tester.product[0].exist and strips_tester.product[0].ok == Task.TASK_OK:
                if self.check_mask([-1, -1, -1, 1, 1, -1]):  # Does LED turn on?
                    strips_tester.product[0].add_measurement(type(self).__name__, "VisualStart", Task.TASK_OK, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled levega kosa (VisualStart)\n", "tag": "green"}})
                else:
                    strips_tester.product[0].add_measurement(type(self).__name__, "VisualStart", Task.TASK_WARNING, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled levega kosa (VisualStart)\n", "tag": "red"}})

            # VisualOff - all LED must be off
            time.sleep(2)
            self.get_light_states()

            if strips_tester.product[1].exist and strips_tester.product[1].ok == Task.TASK_OK:
                if self.check_mask([0, 0, -1, -1, -1, -1]):  # Does LED turn off?
                    strips_tester.product[1].add_measurement(type(self).__name__, "VisualOff", Task.TASK_OK, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled desnega kosa (VisualOff)\n", "tag": "green"}})
                else:
                    strips_tester.product[1].add_measurement(type(self).__name__, "VisualOff", Task.TASK_WARNING, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled desnega kosa (VisualOff)\n", "tag": "red"}})

            if strips_tester.product[0].exist and strips_tester.product[0].ok == Task.TASK_OK:
                if self.check_mask([-1, -1, -1, 0, 0, -1]):  # Does LED turn off?
                    strips_tester.product[0].add_measurement(type(self).__name__, "VisualOff", Task.TASK_OK, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled levega kosa (VisualOff)\n", "tag": "green"}})
                else:
                    strips_tester.product[0].add_measurement(type(self).__name__, "VisualOff", Task.TASK_WARNING, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled levega kosa (VisualOff)\n", "tag": "red"}})

            # Rotate both servos to 270 degrees
            self.nanoboard_small.send_command(108, 100)

            time.sleep(3)
            self.get_light_states()

            if strips_tester.product[1].exist and strips_tester.product[1].ok == Task.TASK_OK:
                if self.check_mask([1, 1, 1, -1, -1, -1]):  # Does all LED turn on?
                    strips_tester.product[1].add_measurement(type(self).__name__, "VisualOn", Task.TASK_OK, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled desnega kosa (VisualOn)\n", "tag": "green"}})
                else:
                    strips_tester.product[1].add_measurement(type(self).__name__, "VisualOn", Task.TASK_WARNING, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled desnega kosa (VisualOn)\n", "tag": "red"}})

            if strips_tester.product[0].exist and strips_tester.product[0].ok == Task.TASK_OK:
                if self.check_mask([-1, -1, -1, 1, 1, 1]):  # Does all LED turn on?
                    strips_tester.product[0].add_measurement(type(self).__name__, "VisualOn", Task.TASK_OK, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled levega kosa (VisualOn)\n", "tag": "green"}})
                else:
                    strips_tester.product[0].add_measurement(type(self).__name__, "VisualOn", Task.TASK_WARNING, "n/a")
                    server.send_broadcast({"text": {"text": "Vizualni pregled levega kosa (VisualOn)\n", "tag": "red"}})

        # Razklenitev 230VAC
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        return type(self).__name__

    def get_threshold_image(self):
        # Update few frames to get accurate image
        for refresh in range(5):
            ret, frame = self.camera.read()  # return a single frame in variable `frame`

        roi = frame[self.roi_y:self.roi_y + self.roi_height,self.roi_x:self.roi_width + self.roi_x] # Make region of interest
        grayscale = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) # Grayscale ROI

        # Make binary image from grayscale ROI
        th, dst = cv2.threshold(grayscale, self.threshold, 255, cv2.THRESH_BINARY)

        return dst

    def check_mask(self,mask):
        # If mask[i] == -1, ignore
        result = True
        for i in range(len(self.led)):
            if self.led[i]['state'] != mask[i] and mask[i] != -1:
                result = False
                break

        return result


    # Get all the lights in test device
    def get_light_states(self):
        img = self.get_threshold_image()

        for i in range(len(self.led)):
            self.led[i]['state'] = self.detect_led_state(img, int(self.led[i]['x']), int(self.led[i]['y']), 5)

            print(self.led[i]['state'])

        print(" ")

    def detect_led_state(self, th, x, y, rng):
        x = x - self.roi_x
        y = y - self.roi_y

        state = False

        black = 0
        white = 0

        for yy in range(-rng, rng):
            for xx in range(-rng, rng):
                pixel = th[y + yy][x + xx] % 254

                if pixel:
                    white += 1
                else:
                    black += 1

        # Return True if there is more white than black
        if white > black:
            state = True

        return state

    def tear_down(self):
        self.nanoboard_small.moveStepper(0)

        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)
        #GPIO.output(gpios['LOCK'],True)

        self.camera.release()



class PrintSticker(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        try:
            self.godex = devices.GoDEXG300("/dev/godex")
        except Exception as err:
            server.send_broadcast({"text": {"text": "Tiskalnika Godex ni mogoče najti! ({})\n" . format(err), "tag": "red"}})


    def run(self):
        server.send_broadcast({"text": {"text": "Označite kose s pripadajočimi natisnjenimi nalepkami:\n", "tag": "black"}})

        for current in range(2):
            if strips_tester.product[current].exist:
                program = self.get_external_definition("FlashMCU", "file")
                code = self.get_external_definition("FlashMCU", "sticker_" + program)

                qc_id = server.test_user_id
                date = datetime.datetime.now().strftime("%d.%m.%Y")

                if not strips_tester.product[current].ok:
                    inverse = '^L\r'
                    darkness = '^H15\r'
                else:
                    inverse = '^LI\r'
                    darkness = '^H0\r'

                label = ('^Q9,3\r'
                         '^W21\r'
                         '{}'
                         '^P1\r'
                         '^S2\r'
                         '^AD\r'
                         '^C1\r'
                         '^R12\r'
                         '~Q+0\r'
                         '^O0\r'
                         '^D0\r'
                         '^E12\r'
                         '~R200\r'
                         '^XSET,ROTATION,0\r'
                         '{}'
                         'Dy2-me-dd\r'
                         'Th:m:s\r'
                         'AA,8,10,1,1,0,0E,ID:{}     {}\r'
                         'AA,8,29,1,1,0,0E,C-19_PL_UF_{}\r'
                         'AA,8,48,1,1,0,0E,{}  QC {}\r'
                         'E\r').format(darkness, inverse, code, strips_tester.product[current].serial, program, date, qc_id)

                time.sleep(1)
                self.godex.send_to_printer(label)

                if current:
                    server.send_broadcast({"text": {"text": "   Serijska {} - desni kos\n" . format(strips_tester.product[current].serial), "tag": "black"}})
                else:
                    server.send_broadcast({"text": {"text": "   Serijska {} - levi kos\n".format(strips_tester.product[current].serial), "tag": "black"}})

        return type(self).__name__

    def tear_down(self):
        self.godex.close()


class FlashMCU(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.measurement_results = {}

        self.file = self.get_definition("file")

        self.segger = devices.Segger("/dev/segger")

        # Allow only these two files to be downloaded
        if self.file == "S001" or self.file == "S002":
            self.segger.select_file(self.file)
        else:
            server.send_broadcast({"text": {"text": "Nepravilno ime programa za programiranje!\n" . format(self.file), "tag": "red"}})

            raise Exception("File format invalid!")

    def run(self) -> (bool, str):
        # Check if product exists
        # Nalozi glede na to

        # check if product exists
        # preklopi releje

        # razkleni 220VAC
        # sprogramiraj

        # Preglej ce drugi obstaja
        # preklopi releje
        # sprogramiraj

        # Naredi stik pri reset pinu
        GPIO.output(gpios['RESET_ENABLE'], True)

        # Razklenitev L in N
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        if strips_tester.product[0].exist:
            server.send_broadcast({"text": {"text": "Nalaganje programa '{}' na levi kos.\n" . format(self.file), "tag": "black"}})

            GPIO.output(gpios['C19_GND'], False)
            GPIO.output(gpios['C19_SWIM'], False)
            GPIO.output(gpios['C19_VCC'], False)
            GPIO.output(gpios['C19_RESET'], False)

            # Flash the device using self.file file
            result = self.segger.download()

            if result:
                strips_tester.product[0].add_measurement(type(self).__name__, "FlashMCU", Task.TASK_OK, "N/A")
                server.send_broadcast({"text": {"text": "Levi modul uspešno sprogramiran!\n", "tag": "green"}})
            else:
                strips_tester.product[0].add_measurement(type(self).__name__, "FlashMCU", Task.TASK_WARNING, "N/A")
                server.send_broadcast({"text": {"text": "Napaka pri programiranju levega modula!\n", "tag": "red"}})

        if strips_tester.product[1].exist:
            server.send_broadcast({"text": {"text": "Nalaganje programa '{}' na desni kos.\n" . format(self.file), "tag": "black"}})

            GPIO.output(gpios['C19_GND'], True)
            GPIO.output(gpios['C19_SWIM'], True)
            GPIO.output(gpios['C19_VCC'], True)
            GPIO.output(gpios['C19_RESET'], True)

            # Flash the device using self.file file
            result = self.segger.download()

            if result:
                strips_tester.product[1].add_measurement(type(self).__name__, "FlashMCU", Task.TASK_OK, "N/A")
                server.send_broadcast({"text": {"text": "Desni modul uspešno sprogramiran!\n", "tag": "green"}})
            else:
                strips_tester.product[1].add_measurement(type(self).__name__, "FlashMCU", Task.TASK_WARNING, "N/A")
                server.send_broadcast({"text": {"text": "Napaka pri programiranju desnega modula!\n", "tag": "red"}})

        return type(self).__name__

    def tear_down(self):
        # Close serial connection with Segger
        self.segger.close()


class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # Initialize Voltmeter
        self.voltmeter = self.use_device('voltmeter')

        try:
            self.ohmmeter = devices.DigitalMultiMeter("/dev/ohmmeter")
        except Exception as err:
            server.send_broadcast({"text": {"text": "Ohmmetra DT-4000ZC ni mogoče najti! Preverite baterije. ({})\n" . format(err), "tag": "red"}})
            raise

        # Initialize NanoBoards
        self.nanoboard = self.use_device('NanoBoard')

        # Measure order
        # Expected values imported from definitions
        # Position, Mode (0 - VOLT, 1 - OHM, EXPECTED,TOLERANCE)
        self.measure_order = [
            (0, 1, "R3", "R3_tolerance",0.0), # R3
            (1, 1, "R4", "R4_tolerance",0.0), # R4
            (2, 1, "R5", "R5_tolerance",0.0), # R5
            #(5, 1, "P1", "P1_tolerance",0.0), # P1
            (9, 1, "R9", "R9_tolerance",0.0), # R9
            (11,1, "R8", "R8_tolerance",0.0), # R8

            (6, 0, "vR2", "vR2_tolerance", 0.0),  # R2
            (8, 0, "vR1", "vR1_tolerance", 0.0),  # R1
            (3, 0, "Z1", "Z1_tolerance",0.0), # Z1
            (4, 0, "D1", "D1_tolerance",0.0), # D1
            (7, 0, "5V", "5V_tolerance",0.0), # 5V
            (10,0, "Uvcap", "Uvcap_tolerance",0.0) # Uvcap
        ]

        self.shift = 17  # How many free places on PogoBoard between two nests
        #GPIO.output(gpios['LOCK'],False)

    def run(self) -> (bool, str):

        # Razklenitev L in N
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        # POTREBNO DISCHARGATI VEZJE


        # iterate two products if exists and shift i for next product
        for current in range(2):
            if strips_tester.product[current].exist:
                if strips_tester.product[current].ok == Task.TASK_OK:
                    if current:
                        server.send_broadcast({"text": {"text": "Meritev upornosti desnega kosa:\n", "tag": "black"}})
                    else:
                        server.send_broadcast({"text": {"text": "Meritev upornosti levega kosa:\n", "tag": "black"}})

                for i in range(len(self.measure_order)):
                    if self.measure_order[i][1]:  # if we measure resistance
                        # Proceed measurement if product is ok
                        if strips_tester.product[current].ok == Task.TASK_OK:
                            #print("Probing {}" . format(self.measure_order[i][0] + self.shift * current))

                            self.nanoboard.relay(1)  # Ohmmeter mode
                            self.nanoboard.send_command(100, self.measure_order[i][0] + self.shift * current)

                            self.nanoboard.connect()

                            for j in range(10):
                                resistance = self.ohmmeter.read().numeric_val

                                # Avoid NoneType
                                if resistance is None:
                                    resistance = 0

                                resistance = round(resistance,1) # Round resistance to one decimal point

                                if self.in_range(resistance, self.measure_order[i][2], self.measure_order[i][3]):
                                    strips_tester.product[current].add_measurement(type(self).__name__, self.measure_order[i][2], Task.TASK_OK, resistance)
                                    server.send_broadcast({"text": {"text": "Meritev upornosti {}: {}ohm\n".format(self.measure_order[i][2], resistance), "tag": "green"}})

                                    break
                                else:
                                    time.sleep(0.5)
                                    print("Resistance {} not in range ({})... retrying..." . format(self.get_definition(self.measure_order[i][2]), resistance))

                            # If resistance failed
                            if not self.in_range(resistance, self.measure_order[i][2], self.measure_order[i][3]):
                                strips_tester.product[current].add_measurement(type(self).__name__, self.measure_order[i][2], Task.TASK_WARNING, resistance)
                                server.send_broadcast({"text": {"text": "Meritev upornosti {}: {}ohm\n".format(self.measure_order[i][2], resistance), "tag": "red"}})

                            self.nanoboard.disconnect()

        # Sklenitev L in N
        GPIO.output(gpios['FAZA'], False)
        GPIO.output(gpios['NULA'], False)

        #time.sleep(2)

        # Measure voltages
        for current in range(2):
            if strips_tester.product[current].exist:
                if strips_tester.product[current].ok == Task.TASK_OK:
                    if current:
                        server.send_broadcast({"text": {"text": "Meritev napetosti desnega kosa:\n", "tag": "black"}})
                    else:
                        server.send_broadcast({"text": {"text": "Meritev napetosti levega kosa:\n", "tag": "black"}})

                for i in range(len(self.measure_order)):
                    if not self.measure_order[i][1]:  # if we measure voltages
                        # Proceed measurement if product is ok
                        if strips_tester.product[current].ok == Task.TASK_OK:
                            time.sleep(self.measure_order[i][4])

                            self.nanoboard.relay(0)  # Voltmeter mode
                            self.nanoboard.moveStepper(self.measure_order[i][0] + self.shift * current)

                            self.nanoboard.connect()

                            for j in range(10):
                                voltage = self.voltmeter.read()

                                if self.in_range(voltage, self.measure_order[i][2], self.measure_order[i][3]):
                                    strips_tester.product[current].add_measurement(type(self).__name__, self.measure_order[i][2], Task.TASK_OK, voltage)
                                    server.send_broadcast({"text": {"text": "Meritev napetosti {}: {}V\n".format(self.measure_order[i][2], voltage), "tag": "green"}})

                                    break
                                else:
                                    time.sleep(0.2)
                                    print("Voltage {} not in range ({})... retrying..." . format(self.get_definition(self.measure_order[i][2]), voltage))

                            if not self.in_range(voltage, self.measure_order[i][2], self.measure_order[i][3]):
                                strips_tester.product[current].add_measurement(type(self).__name__, self.measure_order[i][2], Task.TASK_WARNING, voltage)
                                server.send_broadcast({"text": {"text": "Meritev napetosti {}: {}V\n".format(self.measure_order[i][2], voltage), "tag": "red"}})

                            self.nanoboard.disconnect()

        # Razklenitev L in N
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)

        return type(self).__name__

    def in_range(self, value, definition, tolerance):
        expected = self.get_definition(definition)
        if self.is_unit_percent(self.get_definition_unit(tolerance)):
            #print("in_range: {} is in percent" . format(tolerance))
            tolerance_min = expected - expected * (self.get_definition(tolerance) / 100.0)
            tolerance_max = expected + expected * (self.get_definition(tolerance) / 100.0)
        else:
            #print("in_range: {} is not percent" . format(tolerance))
            tolerance_min = expected - self.get_definition(tolerance)
            tolerance_max = expected + self.get_definition(tolerance)

        if value > tolerance_min and value < tolerance_max:
            return True
        else:
            return False

    '''
    def probeVolt(self,index):
        self.nanoboard.relay(0)
        self.nanoboard.moveStepper(index)
        self.nanoboard.connect()

        voltage = self.voltmeter.read()
        time.sleep(1)

        for i in range(3):
            voltage = self.voltmeter.read()
            print(voltage)
            time.sleep(0.1)

        self.nanoboard.disconnect()
        return voltage
    
    def probeOhm(self, index, expected, tolerance):
        resistance = -1

        self.nanoboard.relay(1)  # Ohmmeter mode
        self.nanoboard.send_command(100, index)

        self.nanoboard.connect()

        for i in range(10):
            resistance = self.ohmmeter.read().numeric_val
            
            if resistance
            
            print("Resistance: {}" . format(resistance))
            print("NewResistance: {}" . format(new_resistance))

        diff = 1 # dummy diff
        while diff < 0.80:
            resistance = self.ohmmeter.read().numeric_val
            new_resistance = self.ohmmeter.read().numeric_val
            print("Resistance: {}" . format(resistance))
            print("NewResistance: {}" . format(new_resistance))

            # Is difference bigger than 5%?
            if new_resistance and resistance:
                diff = new_resistance / resistance

                if diff > 1:
                    diff = resistance / new_resistance
            else:
                break

        # Apply newest measurement
        resistance = new_resistance

        self.nanoboard.disconnect()

        return resistance
    '''
    def tear_down(self):
        self.nanoboard.disconnect()
        self.ohmmeter.close()

        #GPIO.output(gpios['LOCK'],True)
        GPIO.output(gpios['FAZA'], True)
        GPIO.output(gpios['NULA'], True)
