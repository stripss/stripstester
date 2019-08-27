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

gpios = strips_tester.settings.gpios
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

class StartProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)
        self.arduino = devices.ArduinoSerial('/dev/nano', baudrate=9600)

    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "value": "Za začetek testiranja zapri pokrov."})
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

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

        for i in range(2):
            gui_web.send({"command": "error", "nest": i, "value": -1})  # Clear all error messages
            gui_web.send({"command": "info", "nest": i, "value": -1})  # Clear all error messages
            gui_web.send({"command": "semafor", "nest": i, "value": (0, 1, 0), "blink": (0, 0, 0)})

            strips_tester.data['start_time'][i] = datetime.datetime.utcnow()  # Get start test date
            gui_web.send({"command": "time", "mode": "start", "nest": i})  # Start count for test

        for i in range(2):
            gui_web.send({"command": "progress", "value": "20", "nest": i})

        self.arduino.write("servo 0 0")
        self.arduino.write("servo 1 0")
        self.arduino.write("servo 2 0")
        self.arduino.write("servo 3 180")
        self.arduino.write("servo 4 180")
        self.arduino.write("servo 5 180")

        # Product power on
        self.relay.set(0x1)

        # Product detection
        for i in range(2):
            # Must be held high, otherwise E2 error
            GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.HIGH)

            strips_tester.data['exist'][i] = not GPIO.input(strips_tester.settings.gpios.get("DUT_{}_DETECT" . format(i)))

            if strips_tester.data['exist'][i]:
                gui_web.send({"command": "info", "nest": i, "value": "Zaznan kos."})
            else:
                gui_web.send({"command": "semafor", "nest": i, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Clear indicator light where DUT is not found

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

        for current_nest in range(strips_tester.data['test_device_nests']):
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
        # Power on
        self.relay.set(0x1)

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
        self.flasher.set_binary(strips_tester.settings.test_dir + "/bin/GAFH.hex")

        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

    def run(self):


        for i in range(2):
            # Check if product exists
            if not self.is_product_ready(i):
                continue

            if i == 1:
                self.relay.set(0x7C)
            else:
                self.relay.set(0xEC00)

            gui_web.send({"command": "status", "nest": i, "value": "Programiranje"})

            num_of_tries = 1

            for j in range(10):
                if self.flasher.flash():  # Flashing begins
                    gui_web.send({"command": "info", "nest": i, "value": "Programiranje uspelo."})
                    self.add_measurement(i, True, "Programming", "OK", "")
                    break
                else:
                    num_of_tries -= 1

                    if not num_of_tries:
                        break

            if not num_of_tries:
                gui_web.send({"command": "error", "nest": i, "value": "Programiranje ni uspelo!"})
                self.add_measurement(i, False, "Programming", "FAIL", "")

            self.relay.clear(0xEC7C)

    def tear_down(self):
        pass


class ButtonAndNTCTest(Task):
    def set_up(self):  # Prepare FTDI USB-to-serial devices
        self.ftdi = []
        self.arduino = devices.ArduinoSerial('/dev/nano', baudrate=9600)

        for i in range(2):
            self.ftdi.append(devices.ArduinoSerial('/dev/ftdi{}'.format(i + 1), baudrate=57600, mode="hex"))

        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)
    def run(self):

        # Power on
        self.relay.set(0x1)

        for i in range(2):
            if not self.is_product_ready(i):
                continue

            # Entering production mode with 10 retries
            if self.ftdi[i].write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.1, wait=0.1, retry=10):
                module_logger.info("UART OK: Successfully enter production mode")
                gui_web.send({"command": "info", "nest": i, "value": "Vstop v TEST način"})
                self.add_measurement(i, True, "UART", "Test mode OK", "")

                gui_web.send({"command": "status", "nest": i, "value": "Meritev temperature"})

                # Measure NTC on PCB
                num_of_tries = 10

                temperature = self.get_temperature(i, 'pb') # Get PCB temperature

                while not self.in_range(temperature, 61, 5):
                    num_of_tries = num_of_tries - 1

                    temperature = self.get_temperature(i, 'pb') # Get PCB temperature

                    if not num_of_tries:
                        break

                if not num_of_tries:
                    module_logger.warning("NTC_PCB is out of bounds: meas: %s°C", temperature)
                    gui_web.send({"command": "error", "nest": i, "value": "Meritev temperature na tiskanini je izven območja: {}°C".format(temperature)})
                    self.add_measurement(i, False, "NTC_PCB", temperature, "°C")
                else:
                    module_logger.info("NTC_PCB in bounds: meas: %s°C", temperature)
                    gui_web.send({"command": "info", "nest": i, "value": "Meritev temperature na tiskanini: {}°C".format(temperature)})
                    self.add_measurement(i, True, "NTC_PCB", temperature, "°C")

                # Measure NTC on cable
                num_of_tries = 10

                temperature = self.get_temperature(i, "ui")
                while not self.in_range(temperature, 63, 5):
                    num_of_tries = num_of_tries - 1

                    temperature = self.get_temperature(i, "ui")

                    if not num_of_tries:
                        break

                if not num_of_tries:
                    module_logger.warning("NTC_Cable is out of bounds: meas: %s°C", temperature)
                    gui_web.send({"command": "error", "nest": i, "value": "Meritev temperature na kablu je izven območja: {}°C".format(temperature)})
                    self.add_measurement(i, False, "NTC_Cable", temperature, "°C")
                else:
                    module_logger.info("NTC_Cable in bounds: meas: %s°C", temperature)
                    gui_web.send({"command": "info", "nest": i, "value": "Meritev temperature na kablu: {}°C".format(temperature)})
                    self.add_measurement(i, True, "NTC_Cable", temperature, "°C")

                gui_web.send({"command": "status", "nest": i, "value": "Branje napetosti krmilnika"})

                # Measure 5V on PCB
                num_of_tries = 15

                voltage = self.get_voltage(i, "5v")
                while not self.in_range(voltage, 5, 10):
                    num_of_tries = num_of_tries - 1

                    voltage = self.get_voltage(i, "5v")

                    if not num_of_tries:
                        break

                if not num_of_tries:
                    module_logger.warning("5V reference is out of bounds: meas: %sV", voltage)
                    gui_web.send({"command": "error", "nest": i, "value": "Meritev napetosti 5V je izven območja: {}V".format(voltage)})
                    self.add_measurement(i, False, "5V_PCB", voltage, "°C")
                else:
                    module_logger.info("5V reference in bounds: meas: %sV", voltage)
                    gui_web.send({"command": "info", "nest": i, "value": "Meritev napetosti 5V: {}V".format(voltage)})
                    self.add_measurement(i, True, "5V_PCB", voltage, "V")

                # Measure 3V3 on PCB
                num_of_tries = 15

                voltage = self.get_voltage(i, "3v3")
                while not self.in_range(voltage, 3.3, 0.2, False):
                    num_of_tries = num_of_tries - 1

                    voltage = self.get_voltage(i, "3v3")

                    if not num_of_tries:
                        break

                if not num_of_tries:
                    module_logger.warning("3V3 reference is out of bounds: meas: %sV", voltage)
                    gui_web.send({"command": "error", "nest": i, "value": "Meritev napetosti 3.3V je izven območja: {}V".format(voltage)})
                    self.add_measurement(i, False, "3V3_PCB", voltage, "°C")
                else:
                    module_logger.info("3V3 reference in bounds: meas: %sV", voltage)
                    gui_web.send({"command": "info", "nest": i, "value": "Meritev napetosti 3.3V: {}V".format(voltage)})
                    self.add_measurement(i, True, "3V3_PCB", voltage, "V")

                gui_web.send({"command": "status", "nest": i, "value": "Test delovanja gumbov"})

                # Press all buttons at once and check button states via UART
                self.press_button(i, "111")

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

                # Press all buttons at once and check button states via UART
                self.press_button(i, "000")

                gui_web.send({"command": "status", "nest": i, "value": "Testiranje grelca"})

                self.set_heater_control(i, False)  # Turn Heater OFF
                state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_P_CTRL".format(i)))

                if state:
                    module_logger.warning("Heater control FAIL")
                    gui_web.send({"command": "error", "nest": i, "value": "Napaka pri izklopu grelca!"})
                    self.add_measurement(i, False, "HeaterControl", "Fail on turn off", "")
                else:
                    module_logger.info("Heater Control OK")
                    gui_web.send({"command": "info", "nest": i, "value": "Izklop grelca OK"})
                    self.add_measurement(i, True, "HeaterControl", "OK", "")



                #
                # self.set_heater_control(i, True)  # Turn Heater ON
                #
                # for m in range(20):
                #     state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_P_CTRL".format(i)))
                #     print(state)
                #     state1 = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_P_CTRL".format(1-i)))
                #     print(state1)
                #     time.sleep(0.1)
                #
                #
                # if not state:
                #     module_logger.warning("Heater control FAIL")
                #     gui_web.send({"command": "error", "nest": i, "value": "Napaka pri vklopu grelca!"})
                #     self.add_measurement(i, False, "HeaterControl", "Fail on turn on", "")
                # else:
                #     module_logger.info("Heater Control OK")
                #     gui_web.send({"command": "info", "nest": i, "value": "Vklop grelca OK"})
                #     self.add_measurement(i, True, "HeaterControl", "OK", "")


                self.set_motor_control(i, False)  # Turn Motor OFF
                state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_M_CTRL".format(i)))

                gui_web.send({"command": "status", "nest": i, "value": "Testiranje motorja"})

                if state:
                    module_logger.warning("Motor control FAIL")
                    gui_web.send({"command": "error", "nest": i, "value": "Napaka pri izklopu motorja!"})
                    self.add_measurement(i, False, "MotorControl", "Fail on turn off", "")
                else:
                    module_logger.info("Motor Control OK")
                    gui_web.send({"command": "info", "nest": i, "value": "Izklop motorja OK"})
                    self.add_measurement(i, True, "MotorControl", "OK", "")

                self.set_motor_control(i, True)  # Turn Motor ON
                state = GPIO.input(strips_tester.settings.gpios.get("DUT_{}_M_CTRL".format(i)))

                if not state:
                    module_logger.warning("Motor control FAIL")
                    gui_web.send({"command": "error", "nest": i, "value": "Napaka pri vklopu motorja!"})
                    self.add_measurement(i, False, "MotorControl", "Fail on turn on", "")
                else:
                    module_logger.info("Motor Control OK")
                    gui_web.send({"command": "info", "nest": i, "value": "Vklop motorja OK"})
                    self.add_measurement(i, True, "MotorControl", "OK", "")

                # Error detection signal -> get UART state of GPIO pin TMP_SW_DET

                #self.ftdi[i].write(self.with_crc("AA 55 02 01 00 55 AA"), append="", response=self.with_crc("AA 55 02 00 00 55 AA"), timeout=0.1, wait=0.5, retry=5) # Exit production mode
            else:
                module_logger.warning("UART Error: cannot enter production mode")
                gui_web.send({"command": "error", "nest": i, "value": "Napaka pri vstopu v TEST način."})
                self.add_measurement(i, False, "UART", "Cannot enter test mode", "")

        # Restore servo initial positions
        self.arduino.write("servo 0 0")
        self.arduino.write("servo 1 0")
        self.arduino.write("servo 2 0")
        self.arduino.write("servo 3 180")
        self.arduino.write("servo 4 180")
        self.arduino.write("servo 5 180")

        return

    def get_temperature(self, nest, command):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 05 01 00 55 AA" . format(command))))  # Write data to UART
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

        return temperature

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

    def set_heater_control(self, nest, state=1):
        if state:
            command = "01"
        else:
            command = "00"

        # Send heater control command
        #self.ftdi[nest].write(self.with_crc("AA 55 07 {} 00 55 AA" . format(command)), append="", response=self.with_crc("AA 55 03 01 01 55 AA" . format(command)), timeout=0.1, wait=0.5, retry=5)
        self.ftdi[nest].write(self.with_crc("AA 55 03 01 00 55 AA"), append="", response=self.with_crc("AA 55 03 01 00 55 AA"), timeout=0.2, wait=0.5)
        time.sleep(0.2)

    def set_motor_control(self, nest, state=1):
        if state:
            command = "01"
        else:
            command = "00"

        # Send motor control command
        self.ftdi[nest].write(self.with_crc("AA 55 04 {} 00 55 AA" . format(command)), append="", response=self.with_crc("AA 55 04 {} 00 55 AA" . format(command)), timeout=0.1, wait=0.5)

    def press_button(self,nest,button_states):
        self.servos_init = [85,105,115,80,70,65]
        self.servos_current = [85,105,115,80,70,65]
        self.servos_limit = [95,115,125,70,60,50]

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

        time.sleep(0.6)

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

        for i in range(2):
            self.ftdi.append(devices.ArduinoSerial('/dev/ftdi{}'.format(i + 1), baudrate=57600, mode="hex"))
            self.visual.append(Visual())
            self.visual[i].load_mask(strips_tester.settings.test_dir + "/mask/mask{}.json" . format(1-i))
            self.visual[i].mask_offset_x = -2
            self.visual[i].mask_offset_y = -1

        self.camera = devices.RPICamera()

    def run(self):
        #for i in range(2):
        #    self.ftdi[i].write(self.with_crc("AA 55 01 00 00 55 AA"), append="", response=self.with_crc("AA 55 01 00 00 55 AA"), timeout=0.1, wait=0.5, retry=10)


        for k in range(2):
            module_logger.warning("manual VisualTest")
            gui_web.send({"command": "status", "nest": k, "value": "Očesno pregledovanje zaslona..."})
            self.add_measurement(k, True, "Display", "Manual testing", "")


        # retrieve 16 images from camera
        for j in range(7):
            val = bin(0b000001 << j)  # Shift through display

            for k in range(2):
                if not self.is_product_ready(k):
                    continue
                self.set_digit(k, "{}".format(hex(int(val, 2))[2:].zfill(2)), "{}".format(hex(int(val, 2))[2:].zfill(2)))

        for k in range(2):
            if not self.is_product_ready(k):
                continue
            self.set_digit(k, "00", "00")

        for j in range(8):
            val = bin(0b0000001 << j)  # Shift through display

            for k in range(2):
                if not self.is_product_ready(k):
                    continue
                self.set_display(k, "{}".format(hex(int(val, 2))[2:].zfill(2)), "00")

        for j in range(3):
            val = bin(0b001 << j)  # Shift through display

            for k in range(2):
                if not self.is_product_ready(k):
                    continue
                self.set_display(k, "00", "{}".format(hex(int(val, 2))[2:].zfill(2)))




        #
        #
        # for j in range(7):
        #     val = bin(0b000001 << j)  # Shift through display
        #
        #     for k in range(2):
        #         self.set_digit(k, "{}".format(hex(int(val, 2))[2:].zfill(2)), "{}".format(hex(int(val, 2))[2:].zfill(2)))
        #
        #     self.camera.get_image()
        #     self.camera.crop_image(90,174,465,66)
        #
        #     for k in range(2):
        #         #if not self.is_product_ready(k):
        #         #    continue
        #         self.visual[k].set_image(self.camera.last_image)
        #         height, width, _ = self.visual[k].image.shape
        #
        #         # Draw rectangle on image where mask is not supposed to be checked
        #         cv2.rectangle(self.visual[k].image, (int(k * width / 2), 0), (int((1 + k) * width / 2), height), (0, 0, 0), -1)
        #
        #         for a in range(len(self.visual[k].mask)):
        #             for b in self.visual[k].mask[a]:
        #                 cv2.circle(self.visual[k].image, (b['x'] + self.visual[k].mask_offset_x, b['y'] + self.visual[k].mask_offset_y), 2, (255,255,0), -1)
        #
        #         retval, buffer = cv2.imencode('.jpg', self.visual[k].image)
        #         jpg_as_text = base64.b64encode(buffer)
        #
        #         success = self.visual[k].compare_mask(j)
        #
        #         if not success:
        #             module_logger.warning("VisualTest error on nest {} with mask index {}" . format(k,j))
        #             gui_web.send({"command": "error", "nest": k, "value": "Napaka na segmentu pod indeksom {}!" . format(j)})
        #             self.add_measurement(k, False, "Display", "Fail at index {}" . format(j), "")
        #         else:
        #             module_logger.info("VisualTest on nest {} with mask index {} OK" . format(k,j))
        #             self.add_measurement(k, True, "Display", "OK Index {}" . format(j), "")
        #
        #         gui_web.send({"command": "info", "nest": k, "value": jpg_as_text.decode(), "type": "image"})
        #
        # for k in range(2):
        #     self.set_digit(k, "00", "00")
        #
        # for j in range(8):
        #     val = bin(0b0000001 << j)  # Shift through display
        #
        #     for k in range(2):
        #         self.set_display(k, "{}".format(hex(int(val, 2))[2:].zfill(2)), "00")
        #
        #     self.camera.get_image()
        #     self.camera.crop_image(90,174,465,66)
        #
        #     for k in range(2):
        #         #if not self.is_product_ready(k):
        #         #    continue
        #
        #         self.visual[k].set_image(self.camera.last_image)
        #         height, width, _ = self.visual[k].image.shape
        #
        #         cv2.rectangle(self.visual[k].image, (int(k * width / 2), 0), (int((1 + k) * width / 2), height), (0,0,0), -1)
        #
        #         for a in range(len(self.visual[k].mask)):
        #             for b in self.visual[k].mask[a]:
        #                 idx = self.visual[k].mask[a].index(b)
        #
        #                 if idx == j:
        #                     color = (255,0,0)
        #                 else:
        #                     color = (255,255,0)
        #
        #                 cv2.circle(self.visual[k].image, (b['x'] + self.visual[k].mask_offset_x, b['y'] + self.visual[k].mask_offset_y), 2, color, -1)
        #
        #         retval, buffer = cv2.imencode('.jpg', self.visual[k].image)
        #         jpg_as_text = base64.b64encode(buffer)
        #
        #         success = self.visual[k].compare_mask(7 + j)
        #
        #         if not success:
        #             module_logger.warning("VisualTest error on nest {} with mask index {}".format(k,7 + j))
        #             gui_web.send({"command": "error", "nest": k, "value": "Napaka na segmentu pod indeksom {}!".format(7 + j)})
        #             self.add_measurement(k, False, "Display", "Fail at index {}".format(7 + j), "")
        #         else:
        #             module_logger.info("VisualTest on nest {} with mask index {} OK".format(k, 7 + j))
        #             self.add_measurement(k, True, "Display", "OK Index {}".format(7 + j), "")
        #
        #         gui_web.send({"command": "info", "nest": k, "value": jpg_as_text.decode(), "type": "image"})
        #
        #
        # for j in range(3):
        #     val = bin(0b001 << j)  # Shift through display
        #
        #     for k in range(2):
        #         self.set_display(k, "00", "{}".format(hex(int(val, 2))[2:].zfill(2)))
        #
        #     self.camera.get_image()
        #     self.camera.crop_image(90,174,465,66)
        #
        #     for k in range(2):
        #         #if not self.is_product_ready(k):
        #         #    continue
        #
        #         self.visual[k].set_image(self.camera.last_image)
        #         height, width, _ = self.visual[k].image.shape
        #
        #         cv2.rectangle(self.visual[k].image, (int(k * width / 2), 0), (int((1 + k) * width / 2), height), (0,0,0), -1)
        #
        #         for a in range(len(self.visual[k].mask)):
        #             for b in self.visual[k].mask[a]:
        #                 cv2.circle(self.visual[k].image, (b['x'] + self.visual[k].mask_offset_x, b['y'] + self.visual[k].mask_offset_y), 2, (255, 255, 0), -1)
        #
        #
        #         retval, buffer = cv2.imencode('.jpg', self.visual[k].image)
        #         jpg_as_text = base64.b64encode(buffer)
        #
        #         success = self.visual[k].compare_mask(15 + j)
        #
        #         if not success:
        #             module_logger.warning("VisualTest error on nest {} with mask index {}".format(k, 15 + j))
        #             gui_web.send({"command": "error", "nest": k, "value": "Napaka na segmentu pod indeksom {}!".format(15 + j)})
        #             self.add_measurement(k, False, "Display", "Fail at index {}".format(15 + j), "")
        #         else:
        #             module_logger.info("VisualTest on nest {} with mask index {} OK".format(k, 15 + j))
        #             self.add_measurement(k, True, "Display", "OK Index {}".format(15 + j), "")
        #
        #         gui_web.send({"command": "info", "nest": k, "value": jpg_as_text.decode(), "type": "image"})

        # Initialize camera
        # Send UART code, wait for response
        # If response good, take pictures
        # Given picture, compare with mask provided


    def set_digit(self, nest, digit1, digit2):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 08 {} {} 55 AA" . format(digit1,digit2))))  # Write data to UART
        time.sleep(0.2)

        return

    def set_display(self, nest, display1, display2):
        self.ftdi[nest].ser.write(unhexlify(self.with_crc("AA 55 09 {} {} 55 AA" . format(display1,display2))))  # Write data to UART
        time.sleep(0.2)

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

        for i in range(2):
            self.ftdi[i].close()



class Visual:
    def __init__(self):
        self.mask = []
        self.image = None
        self.selected = 0
        self.option_selected = 0
        self.option_list = ['h1','s1','v1','h2','s2','v2']
        self.option_command = 0
        self.mask_offset_x = 0
        self.mask_offset_y = 0


    def load_image(self, filename):
        if os.path.isfile(filename):
            self.image = cv2.imread(filename)
            self.camera = False
        else:
            print("File '{}' does not exist" . format(filename))

    def set_image(self, image):
        self.image = image.copy()

    def load_mask(self, filename):

        try:
            input_file = open(filename)
            json_array = json.load(input_file)

            for point in json_array:
                self.mask.append([])

                for point1 in point:
                    self.mask[-1].append(point1)

        except FileNotFoundError:
            pass

    # Use this function if you want to check every point defined in mask. This function returns bool or matching percent
    def compare_mask(self, mask_num):
        if self.image is None:
            return

        # loop through masks
        # check every index of current mask
        # ok mora biti pri mask_num in ne sme bit ok pri != mask_num

        for subindex in range(len(self.mask)):  # Loop through masks
            for index in range(len(self.mask[subindex])):
                if not self.detect_point_state(subindex, index):
                    if subindex == mask_num:
                        return False
                else:
                    if subindex != mask_num:
                        return False

        return True

    # Detect Region of Interest (or point) if the background is white
    def detect_point_state(self, mask_num, index):

        x = self.mask[mask_num][index]['x'] + self.mask_offset_x
        y = self.mask[mask_num][index]['y'] + self.mask_offset_y

        # Pick up small region of interest
        roi = self.image[y - 2:y+2, x-2:x+2]

        mask_min = np.array([self.mask[mask_num][index]['h1'], self.mask[mask_num][index]['s1'], self.mask[mask_num][index]['v1']], np.uint8)
        mask_max = np.array([self.mask[mask_num][index]['h2'], self.mask[mask_num][index]['s2'], self.mask[mask_num][index]['v2']], np.uint8)

        hsv_img = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        frame_thresh = cv2.bitwise_not(cv2.inRange(hsv_img, mask_min, mask_max))

        # Calculate povprecje barv v ROI
        # Primerjaj z masko in glej threshold
        # Obvezno primerjaj HSV barve!

        state = False

        black = 0
        white = 0

        for yy in range(-2, 2):
            for xx in range(-2, 2):
                pixel = frame_thresh[yy][xx] % 254

                if pixel:
                    white += 1
                else:
                    black += 1

        # Return True if there is more white than black
        if white > black:
            state = True

        return state

