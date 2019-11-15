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

import usb.core

gpios = strips_tester.settings.gpios
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

class StartProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)
        self.arduino = devices.ArduinoSerial('/dev/nano', baudrate=9600)

    def run(self) -> (bool, str):

        # Wait for selection of program
        while True:
            try:
                strips_tester.data['program']

                try:
                    strips_tester.data['first_program_set']
                except KeyError:  # First program was set
                    for nest in range(2):
                        gui_web.send({"command": "semafor", "nest": nest, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Disable blink
                    strips_tester.data['first_program_set'] = True
                    module_logger.info("First program was set")
                break
            except KeyError:
                # Set on blinking lights
                GPIO.output(gpios['left_red_led'], GPIO.HIGH)
                GPIO.output(gpios['left_green_led'], GPIO.HIGH)
                GPIO.output(gpios['right_red_led'], GPIO.HIGH)
                GPIO.output(gpios['right_green_led'], GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(gpios['left_red_led'], GPIO.LOW)
                GPIO.output(gpios['left_green_led'], GPIO.LOW)
                GPIO.output(gpios['right_red_led'], GPIO.LOW)
                GPIO.output(gpios['right_green_led'], GPIO.LOW)
                time.sleep(0.5)

        gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        self.arduino.write("servo 0 0")
        self.arduino.write("servo 1 0")
        self.arduino.write("servo 2 0")
        self.arduino.write("servo 3 180")
        self.arduino.write("servo 4 180")
        self.arduino.write("servo 5 180")

        module_logger.info("Waiting for detection switch")
        # Wait for lid to close
        while not self.lid_closed():
            time.sleep(0.01)

        module_logger.info("Lid is closed - begin test")

        # Set on working lights
        GPIO.output(gpios["left_red_led"], True)
        GPIO.output(gpios["left_green_led"], True)
        GPIO.output(gpios["right_red_led"], True)
        GPIO.output(gpios["right_green_led"], True)

        # Product detection
        for i in range(2):
            self.start_test(i)

            # Must be held high, otherwise E2 error
            GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.HIGH)

            strips_tester.data['exist'][i] = not GPIO.input(strips_tester.settings.gpios.get("DUT_{}_DETECT" . format(i)))

            if strips_tester.data['exist'][i]:
                gui_web.send({"command": "info", "nest": i, "value": "Zaznan kos."})
                gui_web.send({"command": "progress", "value": "10", "nest": i})
            else:
                gui_web.send({"command": "semafor", "nest": i, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Clear indicator light where DUT is not found

        #Power on if any product exists
        for i in range(2):
            if self.is_product_ready(i):
                self.relay.set(0x1)
                break

        return

    def tear_down(self):
        self.arduino.close()

# Working
class RelayBoard:
    # This is custom class for GAHF.

    def __init__(self, order, invert):
        self.size = len(order)
        self.order = order  # List of ordered relays
        self.invert = invert

        try:
            strips_tester.data['shifter']
        except Exception:
            strips_tester.data['shifter'] = 0x0000

    def set(self, mask):
        strips_tester.data['shifter'] = strips_tester.data['shifter'] | mask  # Assign shifter global memory
        self.shiftOut()

    def clear(self, mask):
        strips_tester.data['shifter'] = strips_tester.data['shifter'] & ~mask  # Assign shifter global memory
        self.shiftOut()

    def shiftOut(self):
        GPIO.output(gpios['OE'], 1)
        GPIO.output(gpios['LATCH'], 0)

        # Translate binary data to int array
        self.state = [int(d) for d in bin(strips_tester.data['shifter'])[2:].zfill(self.size)]
        self.state.reverse()  # LSB to MSB conversion

        for x in range(self.size):
            if not self.invert:
                GPIO.output(gpios['DATA'], self.state[self.order[x] - 1])
            else:
                GPIO.output(gpios['DATA'], not self.state[self.order[x] - 1])

            GPIO.output(gpios['CLOCK'], 1)
            GPIO.output(gpios['CLOCK'], 0)

        GPIO.output(gpios['LATCH'], 1)

# Working
class FinishProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

    def run(self):

        # Product power off
        self.relay.clear(0x1)

        for current_nest in range(strips_tester.settings.test_device_nests):
            if strips_tester.data['exist'][current_nest]:
                if strips_tester.data['status'][current_nest] == -1:
                    strips_tester.data['status'][current_nest] = True

        for i in range(2):
            gui_web.send({"command": "semafor", "nest": i, "value": (0, 0, 0), "blink": (0, 0, 0)})
            gui_web.send({"command": "progress", "nest": i, "value": "100"})

        # Disable all lights
        GPIO.output(gpios["left_red_led"], False)
        GPIO.output(gpios["left_green_led"], False)
        GPIO.output(gpios["right_red_led"], False)
        GPIO.output(gpios["right_green_led"], False)

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == True:
                GPIO.output(gpios["left_green_led"], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            elif strips_tester.data['status'][0] == False:
                GPIO.output(gpios["left_red_led"], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        if strips_tester.data['exist'][1]:
            if strips_tester.data['status'][1] == True:
                GPIO.output(gpios["right_green_led"], True)
                gui_web.send({"command": "semafor", "nest": 1, "value": (0, 0, 1)})
            elif strips_tester.data['status'][1] == False:
                GPIO.output(gpios["right_red_led"], True)
                gui_web.send({"command": "semafor", "nest": 1, "value": (1, 0, 0)})

        gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
        module_logger.info("Za konec testa odpri pokrov")

        while self.lid_closed():
            time.sleep(0.01)

        #time.sleep(1)
        return

    def tear_down(self):
        pass

# Working
class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-ED120.voltage1", 0.16)  # Rectified DC Voltage
        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

    def run(self):
        # Power on if any product exists
        for i in range(2):
            if self.is_product_ready(i):
                self.relay.set(0x1)
                break


        for i in range(2):
            # Check if product exists
            if not self.is_product_ready(i):
                continue

            gui_web.send({"command": "status", "nest": i, "value": "Meritev napetosti"})

            if i == 0:
                self.relay.set(0x2)
            else:
                self.relay.clear(0x2)

            # Measure 3V3
            num_of_tries = 10

            voltage = self.voltmeter.read()
            while not self.in_range(voltage, 3.3, 0.15, False):
                num_of_tries = num_of_tries - 1

                voltage = self.voltmeter.read()

                if not num_of_tries:
                    break

            gui_web.send({"command": "progress", "value": "20", "nest": i})

            if not num_of_tries:
                module_logger.warning("3V3 is out of bounds: meas: %sV", voltage)
                gui_web.send({"command": "error", "nest": i, "value": "Meritev napetosti 3.3V je izven območja: {}V" . format(voltage)})
                self.add_measurement(i, False, "3V3", voltage, "V")
            else:
                module_logger.info("3V3 in bounds: meas: %sV" , voltage)
                gui_web.send({"command": "info", "nest": i, "value": "Meritev napetosti 3.3V: {}V" . format(voltage)})
                self.add_measurement(i, True, "3V3", voltage, "V")

        return

    def tear_down(self):
        self.voltmeter.close()

# Working, but signal lines must be shorter and soldered!
class FlashMCU(Task):
    def set_up(self):
        self.flasher = devices.STLink()
        self.flasher.set_binary(strips_tester.settings.test_dir + "/bin/" + strips_tester.data['program'] + ".hex")

        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

    def run(self):
        gui_web.send({"command": "status", "value": "Programiranje {sw}..." . format(sw=strips_tester.data['program'])})

        for i in range(2):
            # Check if product exists
            if not self.is_product_ready(i):
                continue

            if i == 1:
                self.relay.set(0x7C)
            else:
                self.relay.set(0xEC00)

            time.sleep(0.2)

            gui_web.send({"command": "info", "nest": i, "value": "Programiranje {sw}..." . format(sw=strips_tester.data['program'])})
            gui_web.send({"command": "progress", "value": "25", "nest": i})

            num_of_tries = 3

            flash = self.flasher.flash()

            while not flash:
                # Reset USB device (take away power and give it back)
                self.relay.set(0x80)
                time.sleep(2)
                self.relay.clear(0x80)
                time.sleep(2)

                num_of_tries = num_of_tries - 1

                flash = self.flasher.flash()

                if not num_of_tries:
                    break

            gui_web.send({"command": "progress", "value": "35", "nest": i})

            if not num_of_tries:
                gui_web.send({"command": "error", "nest": i, "value": "Programiranje ni uspelo!"})
                self.add_measurement(i, False, "Programming", strips_tester.data['program'], "")
            else:
                gui_web.send({"command": "info", "nest": i, "value": "Programiranje uspelo."})
                self.add_measurement(i, True, "Programming", strips_tester.data['program'], "")

            self.relay.clear(0xEC7C)

        # Power off
        self.relay.clear(0x1)
        time.sleep(0.1)

        #Power on if any product exists
        for i in range(2):
            if self.is_product_ready(i):
                self.relay.set(0x1)
                break

    def tear_down(self):
        pass

class ButtonAndNTCTest(Task):
    def set_up(self):  # Prepare FTDI USB-to-serial devices
        self.ftdi = []
        self.arduino = devices.ArduinoSerial('/dev/nano', baudrate=9600)

        for i in range(2):
            self.ftdi.append(devices.ArduinoSerial('/dev/ftdi{}'.format(i + 1), baudrate=57600, mode="hex"))

        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

        self.test_thread = []
        self.threading_lock = threading.Lock()

    def run(self):

        # Power on
        self.relay.set(0x1)

        gui_web.send({"command": "status", "value": "Testiranje funkcij modula"})

        for i in range(2):
            # Get servo on init position
            self.test_thread.append(threading.Thread(target=self.test,args=(i,)))
            self.test_thread[i].daemon = True

            self.test_thread[i].start()
            # Create two threads
            # Lock on arduino

        for i in range(2):
            self.test_thread[i].join()

        # Power off
        self.relay.clear(0x1)
        time.sleep(0.1)

        # Power on
        self.relay.set(0x1)

        # Restore servo initial positions
        self.arduino.write("servo 0 0")
        self.arduino.write("servo 1 0")
        self.arduino.write("servo 2 0")
        self.arduino.write("servo 3 180")
        self.arduino.write("servo 4 180")
        self.arduino.write("servo 5 180")

        return

    '''
    # thread with reading RX
    def read(self, ser):
        read = bytes(self.ser.read(1))  # Read one byte or timeout

        if len(read) == 0:  # Return if no bytes received (timeout)
            return

        read = read[0]  # Retrieve byte

        if self.stage == 0:  # Wait for seperator
            if read == 0xAA:
                self.rx = []
                self.stage += 1
                print("1 Seperator found")
            else:
                return
        elif self.stage == 1:  # Received start of message
            if read == 0x55:  # Second separator found
                self.stage += 1
                print("2 Seperator found")
            else:
                self.stage = 0  # Start again
                return

        self.rx.append(read)

        if len(self.rx) == 8:  # Message terminated
            print("buffer full")
            print(self.rx)
            self.stage = 0  # Wait for next separator

            # check if crc is ok
            if self.with_crc(self.rx) == self.rx[-1]: # Compare checksums
                print("Checksum OK")
                command = self.rx[2]
                data1 = self.rx[3]
                data2 = self.rx[4]
                print("Command {}, Data1: {}, Data2: {}" . format(command,data1,data2))

                # Parse responses

        return
    '''
    def test(self,i):
        if not self.is_product_ready(i):
            return
        self.press_button(i, "000")

        # Check https://stackoverflow.com/questions/22605164/pyserial-how-to-understand-that-the-timeout-occured-while-reading-from-serial-p
        # You must send datacode with crc and you want to get the same answer, if not or timeout (set in serial obj) -> repeat 10x
        # Entering production mode with 10 retries

        if self.ftdi[i].write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.3, wait=0.3, retry=10):
            module_logger.info("UART OK: Successfully enter production mode")
            gui_web.send({"command": "info", "nest": i, "value": "Vstop v TEST način"})
            self.add_measurement(i, True, "UART", "Test mode OK", "")

            gui_web.send({"command": "progress", "value": "40", "nest": i})

            # Measure NTC on PCB
            num_of_tries = 50

            temperature = self.get_temperature(i, 'pb')  # Get PCB temperature

            while not self.in_range(temperature, 61, 5):
                time.sleep(0.2)
                num_of_tries = num_of_tries - 1

                temperature = self.get_temperature(i, 'pb')  # Get PCB temperature

                if not num_of_tries:
                    break

            gui_web.send({"command": "progress", "value": "45", "nest": i})

            if not num_of_tries:
                module_logger.warning("NTC_PCB is out of bounds: meas: %s°C", temperature)
                gui_web.send({"command": "error", "nest": i, "value": "Meritev temperature na tiskanini je izven območja: {}°C".format(temperature)})
                self.add_measurement(i, False, "NTC_PCB", temperature, "°C")
            else:
                module_logger.info("NTC_PCB in bounds: meas: %s°C", temperature)
                gui_web.send({"command": "info", "nest": i, "value": "Meritev temperature na tiskanini: {}°C".format(temperature)})
                self.add_measurement(i, True, "NTC_PCB", temperature, "°C")

            if not self.is_product_ready(i):
                return

            # Measure NTC on cable
            num_of_tries = 50

            temperature = self.get_temperature(i, "ui")
            while not self.in_range(temperature, 63, 5):
                time.sleep(0.2)
                num_of_tries = num_of_tries - 1

                temperature = self.get_temperature(i, "ui")

                if not num_of_tries:
                    break

            gui_web.send({"command": "progress", "value": "50", "nest": i})

            if not num_of_tries:
                module_logger.warning("NTC_Cable is out of bounds: meas: %s°C", temperature)
                gui_web.send({"command": "error", "nest": i, "value": "Meritev temperature na kablu je izven območja: {}°C".format(temperature)})
                self.add_measurement(i, False, "NTC_Cable", temperature, "°C")
            else:
                module_logger.info("NTC_Cable in bounds: meas: %s°C", temperature)
                gui_web.send({"command": "info", "nest": i, "value": "Meritev temperature na kablu: {}°C".format(temperature)})
                self.add_measurement(i, True, "NTC_Cable", temperature, "°C")

            if not self.is_product_ready(i):
                return

            # Measure 5V on PCB
            num_of_tries = 20

            voltage = self.get_voltage(i, "5v")
            while not self.in_range(voltage, 5, 10):
                time.sleep(0.1)
                num_of_tries = num_of_tries - 1

                voltage = self.get_voltage(i, "5v")

                if not num_of_tries:
                    break

            gui_web.send({"command": "progress", "value": "55", "nest": i})

            if not num_of_tries:
                module_logger.warning("5V reference is out of bounds: meas: %sV", voltage)
                gui_web.send({"command": "error", "nest": i, "value": "Meritev napetosti 5V je izven območja: {}V".format(voltage)})
                self.add_measurement(i, False, "5V_PCB", voltage, "V")
            else:
                module_logger.info("5V reference in bounds: meas: %sV", voltage)
                gui_web.send({"command": "info", "nest": i, "value": "Meritev napetosti 5V: {}V".format(voltage)})
                self.add_measurement(i, True, "5V_PCB", voltage, "V")

            # Measure 3V3 on PCB
            num_of_tries = 20

            if not self.is_product_ready(i):
                return

            voltage = self.get_voltage(i, "3v3")
            while not self.in_range(voltage, 3.3, 0.2, False):
                time.sleep(0.1)
                num_of_tries = num_of_tries - 1

                voltage = self.get_voltage(i, "3v3")

                if not num_of_tries:
                    break

            gui_web.send({"command": "progress", "value": "60", "nest": i})

            if not num_of_tries:
                module_logger.warning("3V3 reference is out of bounds: meas: %sV", voltage)
                gui_web.send({"command": "error", "nest": i, "value": "Meritev napetosti 3.3V je izven območja: {}V".format(voltage)})
                self.add_measurement(i, False, "3V3_PCB", voltage, "V")
            else:
                module_logger.info("3V3 reference in bounds: meas: %sV", voltage)
                gui_web.send({"command": "info", "nest": i, "value": "Meritev napetosti 3.3V: {}V".format(voltage)})
                self.add_measurement(i, True, "3V3_PCB", voltage, "V")

            gui_web.send({"command": "progress", "value": "65", "nest": i})

            # Press all buttons at once and check button states via UART
            self.press_button(i, "111",0.2)

            button_states = self.get_button_states(i)
            button_lang = ["Desna", "Srednja", "Leva"]

            for current_button in range(len(button_states)):
                if not button_states[current_button]:  # Current button FAIL
                    gui_web.send({"command": "error", "nest": i, "value": "{} tipka ne deluje." . format(button_lang[current_button])})

            if all(button_states):
                module_logger.info("Button test OK")
                gui_web.send({"command": "info", "nest": i, "value": "Tipke OK"})
                self.add_measurement(i, True, "Buttons", button_states, "")
            else:
                module_logger.warning("Button error: {}" . format(button_states))
                self.add_measurement(i, False, "Buttons", button_states, "")

            gui_web.send({"command": "progress", "value": "70", "nest": i})

            if not self.is_product_ready(i):
                return

            # Press all buttons at once and check button states via UART
            self.press_button(i, "000", 0.2)

            if not self.set_heater_control(i, True):
                module_logger.warning("Heater control FAIL")
                gui_web.send({"command": "error", "nest": i, "value": "Napaka pri vklopu grelca!"})
                self.add_measurement(i, False, "HeaterControl", "Fail on turn on", "")
            else:
                module_logger.info("Heater Control OK")
                gui_web.send({"command": "info", "nest": i, "value": "Vklop grelca OK"})
                self.add_measurement(i, True, "HeaterControl", "OK", "")

            if not self.set_heater_control(i, False):
                module_logger.warning("Heater control FAIL")
                gui_web.send({"command": "error", "nest": i, "value": "Napaka pri izklopu grelca!"})
                self.add_measurement(i, False, "HeaterControl", "Fail on turn off", "")
            else:
                module_logger.info("Heater Control OK")
                gui_web.send({"command": "info", "nest": i, "value": "Izklop grelca OK"})
                self.add_measurement(i, True, "HeaterControl", "OK", "")

            gui_web.send({"command": "progress", "value": "75", "nest": i})

            if not self.is_product_ready(i):
                return

            if not self.set_motor_control(i, True):
                module_logger.warning("Motor control FAIL")
                gui_web.send({"command": "error", "nest": i, "value": "Napaka pri izklopu motorja!"})
                self.add_measurement(i, False, "MotorControl", "Fail on turn off", "")
            else:
                module_logger.info("Motor Control OK")
                gui_web.send({"command": "info", "nest": i, "value": "Izklop motorja OK"})
                self.add_measurement(i, True, "MotorControl", "OK", "")

            if not self.set_motor_control(i, True):
                module_logger.warning("Motor control FAIL")
                gui_web.send({"command": "error", "nest": i, "value": "Napaka pri vklopu motorja!"})
                self.add_measurement(i, False, "MotorControl", "Fail on turn on", "")
            else:
                module_logger.info("Motor Control OK")
                gui_web.send({"command": "info", "nest": i, "value": "Vklop motorja OK"})
                self.add_measurement(i, True, "MotorControl", "OK", "")

            gui_web.send({"command": "progress", "value": "80", "nest": i})

            # Error detection signal -> get UART state of GPIO pin TMP_SW_DET

            if not self.is_product_ready(i):
                return

            # Module must have no errors:
            num_of_tries = 20

            error = self.get_error_states(i)
            while error:
                time.sleep(0.1)
                num_of_tries = num_of_tries - 1

                error = self.get_error_states(i)

                if not num_of_tries:
                    break

            if not num_of_tries:
                module_logger.warning("Error detection FAIL")
                gui_web.send({"command": "error", "nest": i, "value": "Zaznana napaka na modulu: {}!" . format(error)})
                self.add_measurement(i, False, "ErrorDetection", "Detected error {}" . format(error), "")
            else:
                module_logger.info("Error detection OK")
                gui_web.send({"command": "info", "nest": i, "value": "Zaznavanje napak na modulu OK"})
                self.add_measurement(i, True, "ErrorDetection", "OK", "")

            # Trigger E2 error
            GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.LOW)
            time.sleep(2)

            num_of_tries = 20

            error = self.get_error_states(i)
            while error != 2:
                time.sleep(0.1)
                num_of_tries = num_of_tries - 1

                error = self.get_error_states(i)

                if not num_of_tries:
                    break

            if not num_of_tries:
                module_logger.warning("Error detection FAIL")
                gui_web.send({"command": "error", "nest": i, "value": "Ni zaznane simulirane napake E2!"})
                self.add_measurement(i, False, "ErrorDetection", "Not detected E2", "")
            else:
                module_logger.info("Error detection OK")
                gui_web.send({"command": "info", "nest": i, "value": "Simulirana napaka zaznana."})
                self.add_measurement(i, True, "ErrorDetection", "OK", "")

            GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.HIGH)

            # Do not exit procution mode because camera needs to be tested.
            #self.ftdi[i].write(self.with_crc("AA 55 02 01 00 55 AA"), append="", response=self.with_crc("AA 55 02 00 00 55 AA"), timeout=0.1, wait=0.5, retry=5) # Exit production mode
        else:
            module_logger.warning("UART Error: cannot enter production mode")
            gui_web.send({"command": "error", "nest": i, "value": "Napaka pri vstopu v TEST način."})
            self.add_measurement(i, False, "UART", "Cannot enter test mode", "")

    def get_temperature(self, nest, command):
        self.ftdi[nest].ser.flushInput()
        self.ftdi[nest].ser.flushOutput()

        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 05 01 00 55 AA")))  # Write data to UART
        time.sleep(0.1)

        # read 8 bytes or timeout (set in serial.Serial)
        response = (self.ftdi[nest].ser.read(8)).hex()[6:10]

        try:
            if command == "pb":
                temperature = int(response[0:2], 16)
            elif command == "ui":
                temperature = int(response[2:4], 16)

        except ValueError:  # Response is zero
            temperature = 0.0

        print("Command: {} -> Response: {} -> Temperature: {}°C" . format(command, response, temperature))
        return temperature

    def set_heater_control(self, nest, command):
        if command:
            command1 = "01"
        else:
            command1 = "00"

        self.ftdi[nest].write(self.with_crc("AA 55 03 {} 00 55 AA" . format(command1)), append="", response=self.with_crc("AA 55 03 {} 00 55 AA" . format(command1)), timeout=0.3)

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=4)  # 3 seconds timeout

        state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_P_CTRL".format(nest)))
        while state != command: # or timeout
            if datetime.datetime.now() > end_time:
                module_logger.error("Reached timeout for heater!")
                return False

            state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_P_CTRL".format(nest)))

        return True

    def get_voltage(self, nest, command):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 06 01 00 55 AA" . format(command))))  # Write data to UART
        time.sleep(0.1)
        # read 8 bytes or timeout (set in serial.Serial)
        response = (self.ftdi[nest].ser.read(8)).hex()[6:10]

        try:
            if command == "3v3":
                voltage = int(response[0:2], 16) / 10.0
            elif command == "5v":
                voltage = int(response[2:4], 16) / 10.0

        except ValueError:  # Response is zero
            voltage = 0.0

        return voltage

    def get_button_states(self, nest):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 07 01 00 55 AA")))  # Write data to UART
        time.sleep(0.1)
        # read 8 bytes or timeout (set in serial.Serial)
        response = (self.ftdi[nest].ser.read(8)).hex()[6:10]

        try:
            states = "{}".format(bin(int(response[0:2],16))[2:].zfill(2))
        except ValueError:  # Response is zero
            states = "000"

        states_list = []
        for i in states:
            states_list.append(int(i))

        return states_list

    def set_motor_control(self, nest, command):
        if command:
            command1 = "01"
        else:
            command1 = "00"

        self.ftdi[nest].write(self.with_crc("AA 55 04 {} 00 55 AA" . format(command1)), append="", response=self.with_crc("AA 55 04 {} 00 55 AA" . format(command1)), timeout=0.3)

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=4)  # 3 seconds timeout

        state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_M_CTRL".format(nest)))
        while state != command: # or timeout
            if datetime.datetime.now() > end_time:
                module_logger.error("Reached timeout for heater!")
                return False

            state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_M_CTRL".format(nest)))

        return True

    def get_error_states(self, nest):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 0A 01 00 55 AA")))  # Write data to UART
        time.sleep(0.1)
        # read 8 bytes or timeout (set in serial.Serial)
        response = (self.ftdi[nest].ser.read(8)).hex()

        print("Response: {}".format(response))

        try:
            response = int(response[6:8])
        except Exception:
            response = 0

        return response

    def press_button(self,nest,button_states, wait=0.6):
        self.threading_lock.acquire()

        self.servos_init = [90,105,115,80,70,65]
        self.servos_current = [90,105,115,80,70,65]
        self.servos_limit = [100,115,125,70,60,50]

        # Pritisni tisti servo kjer mora biti 1
        for j in range(3):
            if nest:
                servo_current = 5 - j
            else:
                servo_current = j

            if int(button_states[2-j]):  # if button must be 1
                # Touch servo
                self.servos_current[servo_current] = self.servos_limit[servo_current]
            else:
                self.servos_current[servo_current] = self.servos_init[servo_current]

        for index in range(6):
            self.arduino.write("servo {} {}" . format(index, self.servos_current[index]))

        time.sleep(wait)
        self.threading_lock.release()

    def check_for_button(self, nest, button_states):
        self.press_button(nest, button_states)

        for i in range(3):
            # Get button states
            if self.ftdi[nest].write(self.with_crc("AA 55 07 01 00 55 AA"), append="", response=self.with_crc("AA 55 07 {} 00 55 AA" . format(hex(int(button_states,2))[2:].zfill(2))), timeout=0.1, wait=0.2, retry=3):
                return True
            else:
                return False

    def with_crc(self, a):
        a = a.replace(" ", "").upper()  # Remove spaces

        b = [a[i:i + 2] for i in range(0, len(a), 2)]
        c = [int(i, 16) for i in b]
        d = (255 - sum(c) % 256) + 1

        e = hex(d)[2:].zfill(2)

        result = "{}{}".format(a, e)
        return result.upper()

    def tear_down(self):
        self.arduino.close()

        for i in range(2):
            self.ftdi[i].close()

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


class PrintSticker(Task):
    def set_up(self):
        self.godex = devices.Godex(interface=2)

    def run(self):
        if not self.godex.found:
            for current_nest in range(2):
                if strips_tester.data['exist'][current_nest]:
                    gui_web.send({"command": "error", "nest": current_nest, "value": "Tiskalnika ni mogoče najti!"})
            return

        for current_nest in range(2):
            # Lid is now opened.
            if strips_tester.data['exist'][current_nest]:
                if strips_tester.data['status'][current_nest] != -1:  # if product was tested
                    self.print_sticker(current_nest)

        return

    def print_sticker(self, current_nest):
        date = datetime.datetime.now()
        date_full = date.strftime("%y%m%d")  # Generate full date

        if strips_tester.data['status'][current_nest] == True:  # Test OK
            inverse = '^L\n'
            darkness = '^H15\n'
        elif strips_tester.data['status'][current_nest] == False:  # Test FAIL
            inverse = '^LI\n'
            darkness = '^H4\n'
        else:
            return

        datamatrix = '{}{:07d}' . format(date_full,self.get_new_serial())
        self.add_measurement(current_nest, True, "serial", datamatrix, "")

        params = [s for s in strips_tester.data['program'].split("_")]

        firmware = params[0]  # GADF or GAHF
        saop = params[3]  # Saop number
        fw_version = params[2]  # Firmware version
        size = 2

        if firmware == "GADF":
            garo = "109561"
        else:
            garo = "41948"

        if size == 1:  # 25x10mm
            label = ('^Q10,3\n'
                    '^W21\n'
                    '{darkness}'
                    '^P1\n'
                    '^S2\n'
                    '^AD\n'
                    '^C1\n'
                    '^R0\n'
                    '~Q+0\n'
                    '^O0\n'
                    '^D0\n'
                    '^E12\n'
                    '~R255\n'
                    '{inverse}'
                    'Dy2-me-dd\n'
                    'Th:m:s\n'
                    'AA,10,12,1,1,0,0E,{firmware} int {saop}\n'
                    'AA,10,31,1,1,0,0E,f.w.: {version}\n'
                    'AA,10,50,1,1,0,0E,{garo}, QC: {qc}\n'
                    'XRB115,35,2,0,13\n'
                    '{datamatrix}\n'
                    'E\n').format(darkness = darkness,inverse = inverse,firmware = firmware, saop=saop, version = fw_version,qc=strips_tester.data['worker_id'], datamatrix=datamatrix,garo=garo)
        else:  # 25x7mm
            label = ('^Q7,3\n'
                     '^W25\n'
                     '{darkness}'
                     '^P1\n'
                     '^S3\n'
                     '^AD\n'
                     '^C1\n'
                     '^R0\n'
                     '~Q+0\n'
                     '^O0\n'
                     '^D0\n'
                     '^E12\n'
                     '~R255\n'
                     '{inverse}'
                     'Dy2-me-dd\n'
                     'Th:m:s\n'
                     'AA,9,2,1,1,0,0E,{firmware} int {saop}\n'
                     'AA,9,21,1,1,0,0E,f.w.: {version}\n'
                     'AA,9,40,1,1,0,0E,{garo}, QC: {qc}\n'
                     'XRB152,10,2,0,13\n'
                     '{datamatrix}\n'
                     'E\n').format(darkness=darkness, inverse=inverse, firmware=firmware, saop=saop, version=fw_version, qc=strips_tester.data['worker_id'], datamatrix=datamatrix,garo=garo)

        self.godex.send_to_printer(label)
        time.sleep(1)

    def tear_down(self):
        self.godex.close()

