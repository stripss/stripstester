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


gpios = strips_tester.settings.gpios
custom_data = strips_tester.settings.custom_data
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

class StartProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)
        self.relay.clear(0xFFFFFFFF)

    def run(self) -> (bool, str):
        # Wait for selection of program
        while True:
            try:
                strips_tester.data['program']

                try:
                    strips_tester.data['first_program_set']
                except KeyError:  # First program was set
                    gui_web.send({"command": "semafor", "value": (0, 0, 0), "blink": (0, 0, 0)})  # Disable blink

                    strips_tester.data['first_program_set'] = True
                    module_logger.info("First program was set")
                break
            except KeyError:
                # Set on blinking lights

                GPIO.output(gpios['1PH_red_led'], GPIO.HIGH)
                GPIO.output(gpios['1PH_green_led'], GPIO.HIGH)
                GPIO.output(gpios['3PH_red_led'], GPIO.HIGH)
                GPIO.output(gpios['3PH_green_led'], GPIO.HIGH)
                GPIO.output(gpios['DF_red_led'], GPIO.HIGH)
                GPIO.output(gpios['DF_green_led'], GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(gpios['1PH_red_led'], GPIO.LOW)
                GPIO.output(gpios['1PH_green_led'], GPIO.LOW)
                GPIO.output(gpios['3PH_red_led'], GPIO.LOW)
                GPIO.output(gpios['3PH_green_led'], GPIO.LOW)
                GPIO.output(gpios['DF_red_led'], GPIO.LOW)
                GPIO.output(gpios['DF_green_led'], GPIO.LOW)
                time.sleep(0.5)

        gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})
        module_logger.info("Waiting for detection switch")

        # Wait for lid to close
        while not self.lid_closed():
            time.sleep(0.01)

        module_logger.info("Lid is closed - begin test")

        detect_1ph = not GPIO.input(strips_tester.settings.gpios.get("DUT_1PH_DETECT"))
        detect_3ph = not GPIO.input(strips_tester.settings.gpios.get("DUT_3PH_DETECT"))
        detect_df = not GPIO.input(strips_tester.settings.gpios.get("DUT_DF_DETECT"))

        # Check if multiple boards were inserted
        if detect_1ph + detect_3ph + detect_df > 1:
            module_logger.error("Multiple board detected! Abort test.")
            self.end_test()
            return
        elif detect_1ph + detect_3ph + detect_df == 1:
            strips_tester.data['exist'][0] = True

        if detect_1ph:
            # Set on working lights
            module_logger.info("GAHF 1P detected.")
            GPIO.output(gpios["1PH_red_led"], True)
            GPIO.output(gpios["1PH_green_led"], True)

        if detect_3ph:
            module_logger.info("GAHF 3P detected.")
            GPIO.output(gpios["3PH_red_led"], True)
            GPIO.output(gpios["3PH_green_led"], True)

        if detect_df:
            module_logger.info("GADF detected.")
            GPIO.output(gpios["DF_red_led"], True)
            GPIO.output(gpios["DF_green_led"], True)

        self.start_test(0)

        '''
        self.ftdi = devices.ArduinoSerial('/dev/ftdi', baudrate=57600, mode="hex")

        if self.ftdi.write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.3, wait=0.3, retry=10):
            module_logger.info("UART OK: Successfully enter production mode")

            self.set_digit(0, "{}".format(hex(0b1111111)[2:].zfill(2)), "{}".format(hex(0b1111111)[2:].zfill(2)))
            self.set_display(0, "{}".format(hex(0b11111111)[2:].zfill(2)), "{}".format(hex(0b1111)[2:].zfill(2)))

            time.sleep(1)
            self.ftdi.write(self.with_crc("AA 55 02 01 00 55 AA"), append="", response=self.with_crc("AA 55 02 01 00 55 AA"), timeout=0.1, wait=0.5, retry=5)  # Exit production mode

        else:
            module_logger.error("UART FAIL: Cannot enter production mode")
        self.ftdi.close()
        '''

        # Product detection
        # Must be held high, otherwise E2 error
        #GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.HIGH)

        if strips_tester.data['exist'][0]:
            gui_web.send({"command": "info", "nest": 0, "value": "Zaznan kos."})
            gui_web.send({"command": "progress", "value": "10", "nest": 0})
        else:
            gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Clear indicator light where DUT is not found


        return

    def set_digit(self, nest, digit1, digit2):
        self.ftdi.ser.write(unhexlify(self.with_crc("AA 55 08 {} {} 55 AA" . format(digit1,digit2))))  # Write data to UART

        return

    def set_display(self, nest, display1, display2):
        print(display1, display2)
        self.ftdi.ser.write(unhexlify(self.with_crc("AA 55 09 {} {} 55 AA" . format(display1,display2))))  # Write data to UART

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
        pass

# Working
class RelayBoard:
    # This is custom class for GAHF.
    def __init__(self, order, invert):
        self.size = len(order)
        self.order = order  # List of ordered relays
        self.invert = invert
        self.delay = 0.0001

        try:
            strips_tester.data['shifter']
        except Exception:
            strips_tester.data['shifter'] = 0x0

    def set(self, mask):
        strips_tester.data['shifter'] = strips_tester.data['shifter'] | mask  # Assign shifter global memory
        self.shiftOut()

    def clear(self, mask):
        strips_tester.data['shifter'] = strips_tester.data['shifter'] & ~mask  # Assign shifter global memory
        self.shiftOut()

    def shiftOut(self):
        GPIO.output(gpios['OE'], 0)
        GPIO.output(gpios['LATCH'], 1)
        time.sleep(self.delay)

        # Translate binary data to int array
        self.state = [int(d) for d in bin(strips_tester.data['shifter'])[2:].zfill(self.size)]
        self.state.reverse()  # LSB to MSB conversion

        print(self.state)

        for x in range(self.size):
            if not self.invert:
                GPIO.output(gpios['DATA'], self.state[self.order[x] - 1])
            else:
                GPIO.output(gpios['DATA'], not self.state[self.order[x] - 1])

            time.sleep(self.delay)
            self.shiftClock()

        GPIO.output(gpios['LATCH'], 0)

    def shiftClock(self):
        GPIO.output(gpios['CLOCK'], 0)
        time.sleep(self.delay)
        GPIO.output(gpios['CLOCK'], 1)
        time.sleep(self.delay)
        return

# Working
class FinishProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)

    def run(self):
        # Product power off
        self.relay.clear(0xFFFFFFFF)

        for current_nest in range(strips_tester.settings.test_device_nests):
            if strips_tester.data['exist'][current_nest]:
                if strips_tester.data['status'][current_nest] == -1:
                    strips_tester.data['status'][current_nest] = True

        gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})
        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        # Disable all lights
        GPIO.output(gpios["1PH_red_led"], False)
        GPIO.output(gpios["1PH_green_led"], False)
        GPIO.output(gpios["3PH_red_led"], False)
        GPIO.output(gpios["3PH_green_led"], False)
        GPIO.output(gpios["DF_red_led"], False)
        GPIO.output(gpios["DF_green_led"], False)

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == True:
                GPIO.output(gpios["1PH_green_led"], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            elif strips_tester.data['status'][0] == False:
                GPIO.output(gpios["1PH_red_led"], True)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        gui_web.send({"command": "status", "value": "Za konec testa odpri pokrov"})
        module_logger.info("Za konec testa odpri pokrov")

        while self.lid_closed():
            time.sleep(0.01)

        return

    def tear_down(self):
        pass

# Working
class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B5AF.voltage1", 0.16)  # Rectified DC Voltage
        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)

    def run(self):
        # Power on if any product exists
        if not self.is_product_ready(0):
            return

        gui_web.send({"command": "status", "value": "Meritev napetosti"})

        # Preklop 5v, 3v3
        # If OK, connect MCU else FAIL
        self.relay.set(int(custom_data['RELAY_5V'], 16))

        # Measure 5V
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 5, 0.5, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()
            print(voltage)

            if not num_of_tries:
                break

        self.relay.clear(int(custom_data['RELAY_5V'], 16))

        gui_web.send({"command": "progress", "value": "20", "nest": 0})

        if not num_of_tries:
            module_logger.warning("5V is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti 5V je izven območja: {}V" . format(voltage)})
            self.add_measurement(0, False, "5V", voltage, "V")
        else:
            module_logger.info("5V in bounds: meas: %sV" , voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti 5V: {}V" . format(voltage)})
            self.add_measurement(0, True, "5V", voltage, "V")

        self.relay.set(int(custom_data['RELAY_3V3'], 16))
        # Measure 3V3
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 3.3, 0.15, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        self.relay.clear(int(custom_data['RELAY_3V3'], 16))

        gui_web.send({"command": "progress", "value": "20", "nest": 0})

        if not num_of_tries:
            module_logger.warning("3V3 is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti 3V3 je izven območja: {}V" . format(voltage)})
            self.add_measurement(0, False, "3V3", voltage, "V")
        else:
            module_logger.info("3V3 in bounds: meas: %sV" , voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti 3V3: {}V" . format(voltage)})
            self.add_measurement(0, True, "3V3", voltage, "V")
        return

    def tear_down(self):
        self.voltmeter.close()

class FlashMCU(Task):
    def set_up(self):
        self.flasher = devices.STLink()
        self.flasher.set_binary(strips_tester.settings.test_dir + "/bin/" + strips_tester.data['program'] + ".hex")
        self.flasher.set_mcu("stm8s001j3")

        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)

    def run(self):
        # Check if product exists
        if not self.is_product_ready(0):
            return

        gui_web.send({"command": "status", "value": "Programiranje {sw}..." . format(sw=strips_tester.data['program'])})
        gui_web.send({"command": "progress", "value": "25"})

        # Power DUT and enable programming pins
        self.relay.set(int(custom_data['RELAY_STLINK'], 16))

        num_of_tries = 9999

        flash = self.flasher.flash_stm8()

        while not flash:
            # Reset USB device (take away power and give it back)
            num_of_tries = num_of_tries - 1

            flash = self.flasher.flash_stm8()

            if not num_of_tries:
                break

        gui_web.send({"command": "progress", "value": "35"})

        if not num_of_tries:
            gui_web.send({"command": "error", "value": "Programiranje ni uspelo!"})
            self.add_measurement(0, False, "Programming", strips_tester.data['program'], "")
        else:
            gui_web.send({"command": "info", "value": "Programiranje uspelo."})
            self.add_measurement(0, True, "Programming", strips_tester.data['program'], "")

        # Detach programming pins
        self.relay.clear(int(custom_data['RELAY_STLINK'], 16))

        return

    def tear_down(self):
        pass

class LoadTest(Task):
    def set_up(self):  # Prepare FTDI USB-to-serial devices
        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)
        self.ftdi = devices.ArduinoSerial('/dev/ftdi', baudrate=57600, mode="hex")

    def run(self):

        self.relay.set(int(custom_data['RELAY_UI'], 16))

        # Enter production mode
        if self.ftdi.write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.3, wait=0.3, retry=10):
            module_logger.info("UART OK: Successfully enter production mode")

            # Connect UI to PB (Voltage levels OK, measured with VoltageTest function)

            # skleni UI pine
            # read errors
            # control PB (heater on / off...)




            self.set_heater_control(True)
            self.set_motor_control(True)
            time.sleep(3)
            self.set_heater_control(False)
            self.set_motor_control(False)
            time.sleep(3)
            self.set_heater_control(True)
            self.set_motor_control(True)
            time.sleep(3)

            # Measure NTC on PCB
            num_of_tries = 3

            temperature = self.get_pb_temperature()  # Get PCB temperature

            while not self.in_range(temperature, 25, 5, False):
                time.sleep(1)
                num_of_tries = num_of_tries - 1

                temperature = self.get_pb_temperature()  # Get PCB temperature

                if not num_of_tries:
                    break

            if not num_of_tries:
                module_logger.warning("NTC_PCB is out of bounds: meas: %s°C", temperature)
                gui_web.send({"command": "error", "nest": 0, "value": "Meritev temperature na tiskanini je izven območja: {}°C" . format(temperature)})
                self.add_measurement(0, False, "NTC_PCB", temperature, "°C")
            else:
                module_logger.info("NTC_PCB in bounds: meas: %s°C", temperature)
                gui_web.send({"command": "info", "nest": 0, "value": "Meritev temperature na tiskanini: {}°C".format(temperature)})
                self.add_measurement(0, True, "NTC_PCB", temperature, "°C")

            # Measure NTC on PCB
            for i in range(10):
                error = self.get_error_state()  # Get PCB temperature
                print(error)
                time.sleep(1)


        else:
            module_logger.error("UART FAIL: Cannot enter production mode")

        self.ftdi.write(self.with_crc("AA 55 02 01 00 55 AA"), append="", response=self.with_crc("AA 55 02 01 00 55 AA"), timeout=0.1, wait=0.5, retry=5)  # Exit production mode

        self.relay.clear(int(custom_data['RELAY_UI'], 16))
        gui_web.send({"command": "status", "value": "Testiranje funkcij modula"})

        return

    def test(self):
        if not self.is_product_ready(0):
            return

        # Check https://stackoverflow.com/questions/22605164/pyserial-how-to-understand-that-the-timeout-occured-while-reading-from-serial-p
        # You must send datacode with crc and you want to get the same answer, if not or timeout (set in serial obj) -> repeat 10x
        # Entering production mode with 10 retries

        if self.ftdi[0].write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.3, wait=0.3, retry=10):
            module_logger.info("UART OK: Successfully enter production mode")
            gui_web.send({"command": "info", "nest": 0, "value": "Vstop v TEST način"})

            gui_web.send({"command": "progress", "value": "40", "nest": 0})

            # Measure NTC on PCB
            num_of_tries = 50

            temperature = self.get_pb_temperature()  # Get PCB temperature

            while not self.in_range(temperature, 61, 5):
                time.sleep(0.2)
                num_of_tries = num_of_tries - 1

                temperature = self.get_pb_temperature()  # Get PCB temperature

                if not num_of_tries:
                    break
            '''
            #gui_web.send({"command": "progress", "value": "45", "nest": 0})

            if not num_of_tries:
                module_logger.warning("NTC_PCB is out of bounds: meas: %s°C", temperature)
                gui_web.send({"command": "error", "nest": 0, "value": "Meritev temperature na tiskanini je izven območja: {}°C".format(temperature)})
                self.add_measurement(0, False, "NTC_PCB", temperature, "°C")
            else:
                module_logger.info("NTC_PCB in bounds: meas: %s°C", temperature)
                gui_web.send({"command": "info", "nest": 0, "value": "Meritev temperature na tiskanini: {}°C".format(temperature)})
                self.add_measurement(0, True, "NTC_PCB", temperature, "°C")


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
                
            '''

            # Do not exit procution mode because camera needs to be tested.
            #self.ftdi[i].write(self.with_crc("AA 55 02 01 00 55 AA"), append="", response=self.with_crc("AA 55 02 00 00 55 AA"), timeout=0.1, wait=0.5, retry=5) # Exit production mode
        else:
            module_logger.warning("UART Error: cannot enter production mode")
            gui_web.send({"command": "error", "nest": 0, "value": "Napaka pri vstopu v TEST način."})
            self.add_measurement(0, False, "UART", "Cannot enter test mode", "")

    def get_pb_temperature(self):
        self.send_to_ui([0xAA, 0x55, 0x05, 0x01, 0x00, 0x55, 0xAA])

        # read 8 bytes or timeout (set in serial.Serial)
        response = self.ftdi.ser.read(8)
        checksum = self.checksum(response[:-1])

        if checksum != response[-1]:  # Checksum is the same
            print("Checksum not match")
            return False

        return response[4]

    def set_heater_control(self, command):
        self.send_to_ui([0xAA, 0x55, 0x03, command, 0x00, 0x55, 0xAA])
        # read 8 bytes or timeout (set in serial.Serial)
        response = self.ftdi.ser.read(8)

        if response != message:
            print("Checksum heater does not match")
            return False

        return True

    def set_motor_control(self, command):
        self.send_to_ui([0xAA, 0x55, 0x04, command, 0x00, 0x55, 0xAA])

        # read 8 bytes or timeout (set in serial.Serial)
        response = self.ftdi.ser.read(8)

        if response != message:
            print("Checksum motor does not match")
            return False

        return True

    def get_error_state(self):
        self.send_to_ui([0xAA, 0x55, 0x0A, 0x01, 0x00, 0x55, 0xAA])

        # read 8 bytes or timeout (set in serial.Serial)
        response = self.ftdi.ser.read(8)
        checksum = self.checksum(response[:-1])

        if checksum != response[-1]:  # Checksum is the same
            print("Checksum not match")
            return False

        return response[3]

    def with_crc(self, a):
        a = a.replace(" ", "").upper()  # Remove spaces

        b = [a[i:i + 2] for i in range(0, len(a), 2)]
        c = [int(i, 16) for i in b]
        d = (255 - sum(c) % 256) + 1

        e = hex(d)[2:].zfill(2)

        result = "{}{}".format(a, e)
        return result.upper()

    def checksum(self, message):
        return 255 - (sum(message) % 256) + 1

    def send_to_ui(self, message):
        message = bytes(message)
        checksum = self.checksum(message)
        message += bytes([checksum])

        self.ftdi.ser.write(message)  # Write data to UART
        return

    def tear_down(self):
        self.ftdi.close()

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

