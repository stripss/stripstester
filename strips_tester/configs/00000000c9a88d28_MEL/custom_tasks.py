## -*- coding: utf-8 -*-
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import *
from tester import Task
import datetime
import io
from binascii import unhexlify
import base64
import cv2
import numpy as np
import glob
import os
import stm32loader
import usb.core
import struct
import serial

gpios = strips_tester.settings.gpios
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

class StartProcedureTask(Task):
    def set_up(self):
        self.relays = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-DEE80.voltage1", 0.16)

    def run(self) -> (bool, str):
        self.relays.open_all_relays()

        # Wait for selection of program
        while True:
            try:
                strips_tester.data['program']

                try:
                    strips_tester.data['first_program_set']
                except KeyError:  # First program was set
                    gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Disable blink

                    strips_tester.data['first_program_set'] = True
                    module_logger.info("First program was set")
                break
            except KeyError:
                # Set on blinking lights
                GPIO.output(gpios['red_led'], GPIO.HIGH)
                GPIO.output(gpios['green_led'], GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(gpios['red_led'], GPIO.LOW)
                GPIO.output(gpios['green_led'], GPIO.LOW)
                time.sleep(0.5)

        gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        module_logger.info("Waiting for detection switch")
        # Wait for lid to close
        while self.lid_closed():
            time.sleep(0.01)

        module_logger.info("Lid is closed - begin test")

        # Set on working lights
        GPIO.output(gpios["red_led"], True)
        GPIO.output(gpios["green_led"], True)
        GPIO.output(gpios["red_led"], True)
        GPIO.output(gpios["green_led"], True)

        # Product found
        strips_tester.data['exist'][0] = True

        self.start_test(0)

        # Product detection
        # for i in range(2):
        #     self.start_test(i)
        #
        #     # Must be held high, otherwise E2 error
        #     GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.HIGH)
        #
        #     strips_tester.data['exist'][i] = not GPIO.input(strips_tester.settings.gpios.get("DUT_{}_DETECT" . format(i)))
        #
        #     if strips_tester.data['exist'][i]:
        #         gui_web.send({"command": "info", "nest": i, "value": "Zaznan kos."})
        #         gui_web.send({"command": "progress", "value": "10", "nest": i})
        #     else:
        #         gui_web.send({"command": "semafor", "nest": i, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Clear indicator light where DUT is not found


        return

    def tear_down(self):
        self.relays.close()
        self.voltmeter.close()

# Working
class FinishProcedureTask(Task):
    def set_up(self):
        pass

    def run(self):
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == -1:
                strips_tester.data['status'][0] = True

        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})
        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        # Disable all lights
        GPIO.output(gpios["red_led"], False)
        GPIO.output(gpios["green_led"], False)

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == True:
                GPIO.output(gpios["green_led"], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            elif strips_tester.data['status'][0] == False:
                GPIO.output(gpios["red_led"], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
        module_logger.info("Za konec testa odpri pokrov")

        while not self.lid_closed():
            time.sleep(0.01)

        #time.sleep(1)
        return

    def tear_down(self):
        pass

# Working
class VoltageTest(Task):
    def set_up(self):
        self.relays = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-DEE80.voltage1", 0.16)

    def run(self):
        gui_web.send({"command": "status", "nest": 0, "value": "Meritev napetosti"})

        # Measure Vc
        self.relays.close_relay(1)
        self.measure_voltage("Vc", 15, 0.2)
        self.relays.open_relay(1)
        time.sleep(0.1)
        self.relays.close_relay(2)
        self.measure_voltage("12V", 12, 0.2)
        self.relays.open_relay(2)
        time.sleep(0.1)
        self.relays.close_relay(3)
        self.measure_voltage("5V", 5, 0.2)
        self.relays.open_relay(3)
        time.sleep(0.1)
        self.relays.close_relay(4)
        self.measure_voltage("3V3", 3.3, 0.2)
        self.relays.open_relay(4)
        gui_web.send({"command": "progress", "value": "20", "nest": 0})

        return

    def measure_voltage(self, name, expected, tolerance):
        # Measure 3V3
        num_of_tries = 10

        voltage = self.voltmeter.read()

        while not self.in_range(voltage, expected, tolerance, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("{name} is out of bounds: meas: {volt}V" . format(name=name, volt=voltage))
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti {} je izven območja: {}V" . format(name, voltage)})
            self.add_measurement(0, False, name, voltage, "V")
        else:
            module_logger.info("{name} in bounds: meas: {volt}V" . format(name=name, volt=voltage))
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti {}: {}V" . format(name, voltage)})
            self.add_measurement(0, True, name, voltage, "V")

        return

    def tear_down(self):
        self.relays.open_all_relays()
        self.relays.close()
        self.voltmeter.close()

# Working, but signal lines must be shorter and soldered!
class FlashMCU(Task):
    def set_up(self):
        self.relays = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-DEE80.voltage1", 0.16)

        self.flasher = devices.STLink()
        self.flasher.set_binary(strips_tester.settings.test_dir + "/bin/" + strips_tester.data['program'] + ".bin")

    def run(self):
        # Check if product exists
        if not self.is_product_ready(0):
            return

        # If WiFI module -> flash WiFi
        # If non WiFi module -> flash MCU

        gui_web.send({"command": "info", "nest": 0, "value": "Programiranje {sw}..." . format(sw=strips_tester.data['program'])})
        gui_web.send({"command": "progress", "value": "25", "nest": 0})

        num_of_tries = 3

        flash = self.flasher.flash()

        while not flash:
            num_of_tries = num_of_tries - 1

            flash = self.flasher.flash()

            if not num_of_tries:
                break

        gui_web.send({"command": "progress", "value": "35", "nest": 0})

        if not num_of_tries:
            gui_web.send({"command": "error", "nest": 0, "value": "Programiranje ni uspelo!"})
            self.add_measurement(0, False, "Programming", strips_tester.data['program'], "")
        else:
            gui_web.send({"command": "info", "nest": 0, "value": "Programiranje uspelo."})
            self.add_measurement(0, True, "Programming", strips_tester.data['program'], "")

        return

    def tear_down(self):
        self.relays.open_all_relays()
        self.relays.close()
        self.voltmeter.close()


class InternalTest(Task):
    def set_up(self):
        self.relays = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-DEE80.voltage1", 0.16)

        self.serial = serial.Serial(
            port="/dev/serial0",
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=0,
            rtscts=0,
            timeout=0.5,
            dsrdtr=0
        )

        self.temp_sensor = devices.IRTemperatureSensor(0)  # meas delay = 0

    def run(self):
        # Set test mode
        # Measure relays
        # VisualTest
        # Measure temp sensor

        self.relays.close_relay(7)
        self.relays.close_relay(8)
        self.relays.close_relay(11)

        time.sleep(1)

        data = bytes([0x05, 0x06, 0x01])

        sent = bytes([0x00]) + data + struct.pack("H", self.crc(data))
        print(sent)
        self.serial.write(sent) # int().from_bytes(op_code, "big")

        data = bytes([0x05, 0x06, 0x02])

        sent = bytes([0x00]) + data + struct.pack("H", self.crc(data))
        print(sent)
        self.serial.write(sent) # int().from_bytes(op_code, "big")

        while True:
            print(self.serial.read(1))
            time.sleep(0.1)



        time.sleep(2)


        self.relays.open_relay(7)
        self.relays.open_relay(8)
        self.relays.open_relay(11)
        return

    @staticmethod
    def crc(data):
        def _update_crc( crc, byte_):
            crc = (crc >> 8) | ((crc & 0xFF) << 8)
            crc ^= byte_ & 0xFF
            crc ^= (crc & 0xFF) >> 4
            crc ^= ((crc & 0x0F) << 8) << 4
            crc ^= ((crc & 0xFF) << 4) << 1
            return crc
        data = data[1: 2 + data[0] - 0x04]
        crc = 0
        for c in data:
            crc = _update_crc(crc, c)
        return crc

    def tear_down(self):
        self.relays.open_all_relays()
        self.relays.close()
        self.voltmeter.close()
        self.serial.close()

class VisualTest(Task):
    # Predpostavljamo, da je modul v UART production načinu!

    def set_up(self):
        self.ftdi = []
        self.visual = []
        self.success = []

        for i in range(2):
            self.ftdi.append(devices.ArduinoSerial('/dev/ftdi{}'.format(i + 1), baudrate=57600, mode="hex"))
            self.visual.append(devices.Visual())
            self.visual[i].load_mask(strips_tester.settings.test_dir + "/mask/mask{}.json" . format(i))
            self.success.append([])  # Handles success data

        self.camera = devices.RPICamera()

    def run(self):
        gui_web.send({"command": "status", "value": "Testiranje displaya"})

        for i in range(2):
            if not self.is_product_ready(i):
                continue

            self.ftdi[i].write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.1, wait=0.5, retry=10)

            gui_web.send({"command": "progress", "value": "85", "nest": i})

        for j in range(7):
            val = bin(0b000001 << j)  # Shift through display

            for k in range(2):
                if not self.is_product_ready(k):
                    continue

                self.set_digit(k, "{}".format(hex(int(val, 2))[2:].zfill(2)), "{}".format(hex(int(val, 2))[2:].zfill(2)))

            self.camera.get_image()
            self.camera.crop_image(90, 174, 465, 66)

            for k in range(2):
                if not self.is_product_ready(k):
                    continue

                self.success[k].append(self.check_mask(k, j))

        for k in range(2):
            if not self.is_product_ready(k):
                continue

            self.set_digit(k, "00", "00")
            gui_web.send({"command": "progress", "value": "90", "nest": k})

        for j in range(8):
            val = bin(0b0000001 << j)  # Shift through display

            for k in range(2):
                if not self.is_product_ready(k):
                    continue

                self.set_display(k, "{}".format(hex(int(val, 2))[2:].zfill(2)), "00")

            self.camera.get_image()
            self.camera.crop_image(90, 174, 465, 66)

            for k in range(2):
                if not self.is_product_ready(k):
                    continue
                self.success[k].append(self.check_mask(k, 7 + j))

        for j in range(3):
            val = bin(0b001 << j)  # Shift through display

            for k in range(2):
                if not self.is_product_ready(k):
                    continue

                self.set_display(k, "00", "{}".format(hex(int(val, 2))[2:].zfill(2)))

            self.camera.get_image()
            self.camera.crop_image(90, 174, 465, 66)

            for k in range(2):
                if not self.is_product_ready(k):
                    continue

                self.success[k].append(self.check_mask(k, 15 + j))

        # Visual detection over, process error, if any

        for nest in range(2):
            if not self.is_product_ready(nest):
                continue

            gui_web.send({"command": "progress", "value": "95", "nest": nest})

            if not all(self.success[nest]):  # Inspect why it failed
                error_image = cv2.imread(strips_tester.settings.test_dir + "/image/screen.jpg")

                # foreach error draw circle
                for current_error in self.visual[nest].error:
                    cv2.circle(error_image, current_error[:], 8, (0, 0, 255), -1)

                # Rotate image for 180 degrees
                image_center = tuple(np.array(error_image.shape[1::-1]) / 2)
                rot_mat = cv2.getRotationMatrix2D(image_center, 180, 1.0)
                error_image = cv2.warpAffine(error_image, rot_mat, error_image.shape[1::-1], flags=cv2.INTER_LINEAR)

                retval, buffer = cv2.imencode('.jpg', error_image)
                jpg_as_text = base64.b64encode(buffer)

                gui_web.send({"command": "error", "nest": nest, "value": "Napaka na displayu"})
                gui_web.send({"command": "error", "nest": nest, "value": jpg_as_text.decode(), "type": "image"})

                self.add_measurement(nest, False, "Display", "FAIL", "")
            else:
                module_logger.info("VisualTest OK")
                self.add_measurement(nest, True, "Display", "OK", "")
                gui_web.send({"command": "info", "nest": nest, "value": "Display OK."})


        # Exit procution mode
        #self.ftdi[i].write(self.with_crc("AA 55 02 01 00 55 AA"), append="", response=self.with_crc("AA 55 02 01 00 55 AA"), timeout=0.1, wait=0.5, retry=5)  # Exit production mode

        #return

    # Check mask for both nests
    def check_mask(self, nest, mask):
        self.visual[nest].set_image(self.camera.last_image)
        height, width, _ = self.visual[nest].image.shape

        # Apply mask cover so it does not detect other product pixels
        cv2.rectangle(self.visual[nest].image, (int(nest * width / 2), 0), (int((1 + nest) * width / 2), height), (0, 0, 0), -1)

        success = self.visual[nest].compare_mask(mask)  # Handles if all vertices on mask work

        show_points = 1

        if show_points:
            for a in range(len(self.visual[nest].mask)):
                for b in self.visual[nest].mask[a]:
                    cv2.circle(self.visual[nest].image, (b['x'] + self.visual[nest].mask_offset_x, b['y'] + self.visual[nest].mask_offset_y), 1, (255, 255, 0), -1)

            retval, buffer = cv2.imencode('.jpg', self.visual[nest].image)
            jpg_as_text = base64.b64encode(buffer)

            gui_web.send({"command": "info", "nest": nest, "value": jpg_as_text.decode(), "type": "image"})

        return success


    def set_digit(self, nest, digit1, digit2):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 08 {} {} 55 AA" . format(digit1,digit2))))  # Write data to UART

        return

    def set_display(self, nest, display1, display2):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 09 {} {} 55 AA" . format(display1,display2))))  # Write data to UART

        return

    def with_crc(self, a):
        a = a.replace(" ", "").upper()  # Remove spaces

        b = [a[i:i + 2] for i in range(0, len(a), 2)]
        c = [int(i, 16) for i in b]
        d = (255 - sum(c) % 256) + 1

        e = hex(d)[2:].zfill(2)

        result = "{}{}".format(a, e)
        return result.upper()

    def tear_down(self):
        self.camera.close()

        # Close FTDI adapters
        for i in range(2):
            self.ftdi[i].close()
