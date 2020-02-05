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

        # Product detection
        # Must be held high, otherwise E2 error
        #GPIO.output(gpios['DUT_{}_TMP_SW' . format(i)], GPIO.HIGH)

        if strips_tester.data['exist'][0]:
            gui_web.send({"command": "info", "nest": 0, "value": "Zaznan kos."})
            gui_web.send({"command": "progress", "value": "10", "nest": 0})
        else:
            gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Clear indicator light where DUT is not found

        return

    def tear_down(self):
        pass

# Working
class RelayBoard:
    # This is custom class for GAHF.
    def __init__(self, order, invert):
        self.size = len(order)
        self.order = order  # List of ordered relays
        self.invert = invert
        self.delay = 0.0000001

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

        # Product power off
        self.relay.clear(0xFFFFFFFF)

    def run(self):
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

# Working 11.12.2019
class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B5AF.voltage1", 0.16)
        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)

    def run(self):
        # Power on if any product exists
        if not self.is_product_ready(0):
            return

        # Power boards with L and N (!DANGER!)
        self.relay.set(int(custom_data['RELAY_BOARDS_LN'], 16))

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
        self.relay.clear(int(custom_data['RELAY_BOARDS_LN'], 16))
        self.voltmeter.close()

# Working 11.12.2019
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

        # Power boards with L and N (!DANGER!)
        self.relay.set(int(custom_data['RELAY_BOARDS_LN'], 16))

        time.sleep(1)

        gui_web.send({"command": "status", "value": "Programiranje {sw}..." . format(sw=strips_tester.data['program'])})
        gui_web.send({"command": "progress", "value": "25"})

        # Power DUT and enable programming pins
        self.relay.set(int(custom_data['RELAY_STLINK'], 16))

        num_of_tries = 5

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
        # Detach power pins
        self.relay.clear(int(custom_data['RELAY_BOARDS_LN'], 16))

class LoadTest(Task):
    def set_up(self):  # Prepare FTDI USB-to-serial devices
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B5AF.voltage2", 0.5)
        self.relay = RelayBoard([9,11,13,15,16,14,12,10,1,3,5,7,8,6,4,2,24,22,20,18,17,19,21,23,32,30,28,26,25,27,29,31], False)
        self.ftdi = devices.ArduinoSerial('/dev/ftdi', baudrate=57600, mode="hex")

        self.ftdi.ser.flushInput()
        self.ftdi.ser.flushOutput()

    def run(self):
        # Check if product exists
        if not self.is_product_ready(0):
            pass

        # Attach User Interface to the DUT
        self.relay.set(int(custom_data['RELAY_UI'], 16))

        time.sleep(1)

        # Attach Power Board power
        self.relay.set(int(custom_data['RELAY_BOARDS_LN'], 16))

        # Try to set UI in production mode 10 times
        if not self.enter_production_mode():
            module_logger.warning("UART Error: cannot enter production mode")
            gui_web.send({"command": "error", "nest": 0, "value": "Napaka pri vstopu v TEST način."})
            self.add_measurement(0, False, "UART", "Cannot enter test mode", "")

            return

        module_logger.info("UART OK: Successfully enter production mode")

        # Check for errors
        num_of_tries = 3

        error = self.get_error_state()  # Get Error from UI

        while error:
            time.sleep(1)
            num_of_tries = num_of_tries - 1

            error = self.get_error_state()  # Get Error from UI

            if not num_of_tries:
                break

        if error:  # Get Error from UI
            module_logger.warning("Error detected: E%s", error)
            gui_web.send({"command": "error", "nest": 0, "value": "Zaznana napaka - E{}" . format(error)})
            self.add_measurement(0, False, "ErrorDetect", error)
        else:
            module_logger.info("No error has been detected.")
            gui_web.send({"command": "info", "nest": 0, "value": "Ni zaznanih napak"})
            self.add_measurement(0, True, "ErrorDetect", error)




        # Connect UI to PB (Voltage levels OK, measured with VoltageTest function)

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

        # Test procedure:
        # skleni UI pine
        # read errors
        # control PB (heater on / off...)

        # check motor voltage (must be 0)
        # turn motor on
        # check motor voltage (must be 230)
        # turn motor off


        # Disable motor with Power Board
        self.set_motor_control(False)

        # Connect voltmeter to motor output pin (Relay 13, 14 on HV board)
        self.relay.set(int(custom_data['RELAY_GAHF_1P_MOTOR'], 16))

        time.sleep(0.2)

        # Enable soft-start on motor - reduce EMI
        self.relay.set(int(custom_data['RELAY_GAHF_1P_MOTOR_SOFTSTART'], 16))


        # Measure motor voltage
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 0, 10, False):
            #self.set_motor_control(False)
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("MotorOFF output shorted! Measured: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Izhod motorja ima kratek stik: {}V" . format(voltage)})
            self.add_measurement(0, False, "MotorOFF", voltage, "V")
        else:
            module_logger.info("MotorOFF output OK: Measured %sV" , voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Izhod izklopljenega motorja OK - {}V" . format(voltage)})
            self.add_measurement(0, True, "MotorOFF", voltage, "V")

        # Engage motor with Power Board
        self.set_motor_control(True)

        # Measure motor voltage
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 230, 10, False):
            #self.set_motor_control(True)
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("MotorON output FAIL. Measured: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Izhod motorja ne deluje: {}V" . format(voltage)})
            self.add_measurement(0, False, "MotorON", voltage, "V")
        else:
            module_logger.info("MotorON output OK: Measured %sV" , voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Izhod motorja OK: {}V" . format(voltage)})
            self.add_measurement(0, True, "MotorON", voltage, "V")

        time.sleep(2)
        # Turn motor off
        self.set_motor_control(False)

        # Enable soft-start on motor - reduce EMI
        self.relay.clear(int(custom_data['RELAY_GAHF_1P_MOTOR_SOFTSTART'], 16))

        time.sleep(0.2)

        self.relay.clear(int(custom_data['RELAY_GAHF_1P_MOTOR'], 16))

        #self.set_heater_control(False)

        # Connect voltmeter to heater output pin (Relay 13, 14 on HV board)
        self.relay.set(int(custom_data['RELAY_GAHF_1P_HEATER'], 16))

        time.sleep(0.2)

        # Enable soft-start on heater - reduce EMI
        self.relay.set(int(custom_data['RELAY_GAHF_1P_HEATER_SOFTSTART'], 16))

        # Measure heater voltage
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 0, 10, False):
            #self.set_heater_control(False)
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("HeaterOFF output shorted! Measured: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Izhod grelca ima kratek stik: {}V" . format(voltage)})
            self.add_measurement(0, False, "HeaterOFF", voltage, "V")
        else:
            module_logger.info("HeaterOFF output OK: Measured %sV" , voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Izhod izklopljenega grelca OK - {}V" . format(voltage)})
            self.add_measurement(0, True, "HeaterOFF", voltage, "V")

        # Engage heater from Power Board
        self.set_heater_control(True)

        # Measure heater voltage
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 230, 10, False):
            self.set_heater_control(True)
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("HeaterON output FAIL. Measured: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Izhod grelca ne deluje: {}V" . format(voltage)})
            self.add_measurement(0, False, "HeaterON", voltage, "V")
        else:
            module_logger.info("HeaterON output OK: Measured %sV" , voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Izhod grelca OK: {}V" . format(voltage)})
            self.add_measurement(0, True, "HeaterON", voltage, "V")

        # Enable soft-start on heater - reduce EMI
        self.relay.clear(int(custom_data['RELAY_GAHF_1P_HEATER_SOFTSTART'], 16))

        time.sleep(0.2)

        # Detach heater from voltmeter
        self.relay.clear(int(custom_data['RELAY_GAHF_1P_HEATER'], 16))

        '''
        # Check for errors
        num_of_tries = 5

        error = self.get_error_state()  # Get Error from UI

        while error != 1:
            time.sleep(1)
            num_of_tries = num_of_tries - 1

            error = self.get_error_state()  # Get Error from UI
            print(error)
            if not num_of_tries:
                break

        if not num_of_tries:  # Get Error from UI
            module_logger.warning("Error detected: E%s", error)
            gui_web.send({"command": "error", "nest": 0, "value": "Zaznana napaka - E{}".format(error)})
            #self.add_measurement(0, False, "ErrorDetect", error)
        else:
            module_logger.info("No error has been detected.")
            gui_web.send({"command": "info", "nest": 0, "value": "Ni zaznanih napak"})
            #self.add_measurement(0, True, "ErrorDetect", error)


        # Disable heater
        # Make short on heater
        self.set_heater_control(False)

        self.relay.set(int(custom_data['RELAY_GAHF_1P_HEATER_SHORT'], 16))
        time.sleep(0.2)

        # Enable soft-start on heater - reduce EMI
        self.relay.set(int(custom_data['RELAY_GAHF_1P_HEATER_SOFTSTART'], 16))

        # Check for errors
        num_of_tries = 5

        error = self.get_error_state()  # Get Error from UI

        while error != 2:
            time.sleep(1)
            num_of_tries = num_of_tries - 1

            error = self.get_error_state()  # Get Error from UI
            print(error)
            if not num_of_tries:
                break

        if not num_of_tries:  # Get Error from UI
            module_logger.warning("Error detected: E%s", error)
            gui_web.send({"command": "error", "nest": 0, "value": "Zaznana napaka - E{}".format(error)})
            #self.add_measurement(0, False, "ErrorDetect", error)
        else:
            module_logger.info("No error has been detected.")
            gui_web.send({"command": "info", "nest": 0, "value": "Ni zaznanih napak"})
            #self.add_measurement(0, True, "ErrorDetect", error)


        # Enable soft-start on heater - reduce EMI
        self.relay.clear(int(custom_data['RELAY_GAHF_1P_HEATER_SOFTSTART'], 16))

        time.sleep(0.2)

        # Turn heater off
        self.relay.clear(int(custom_data['RELAY_GAHF_1P_HEATER_SHORT'], 16))

        # short heater
        # check error
        '''
        self.exit_production_mode()

        self.relay.clear(int(custom_data['RELAY_UI'], 16))

        return

    def enter_production_mode(self):
        for retry in range(10):
            self.send_to_ui([0xAA, 0x55, 0x01, 0x01, 0x00, 0x55, 0xAA])
            response = self.receive_from_ui()

            if response is not None:
                return True

        return False

    def exit_production_mode(self):
        self.send_to_ui([0xAA, 0x55, 0x02, 0x01, 0x00, 0x55, 0xAA])
        response = self.receive_from_ui()

        if response is not None:
            return True

        return False

    def get_pb_temperature(self):
        self.send_to_ui([0xAA, 0x55, 0x05, 0x01, 0x00, 0x55, 0xAA])
        response = self.receive_from_ui()

        if response is not None:
            return response[4]

        return None

    def set_heater_control(self, state):
        self.send_to_ui([0xAA, 0x55, 0x03, state, 0x00, 0x55, 0xAA])
        response = self.receive_from_ui()

        if response is not None:
            return True

        return False

    def set_motor_control(self, state):
        self.send_to_ui([0xAA, 0x55, 0x04, state, 0x00, 0x55, 0xAA])
        response = self.receive_from_ui()

        if response is not None:
            return True

        return False

    def get_error_state(self):
        self.send_to_ui([0xAA, 0x55, 0x0A, 0x01, 0x00, 0x55, 0xAA])
        response = self.receive_from_ui()

        if response is not None:
            return response[3]

        return None

    # Calculate checksum value of message
    def checksum(self, message):
        return ((255 - sum(message) % 256) + 1) % 256

    # Wrapper for sending message to User Interface
    def send_to_ui(self, message):
        message = bytes(message) + bytes([self.checksum(message)])

        #self.ftdi.ser.flushOutput()
        #self.ftdi.ser.flushInput()

        # Write data to UART
        self.ftdi.ser.write(message)
        #time.sleep(2)

        return

    # Wrapper for receiving messages from User Interface
    def receive_from_ui(self):
        # read 8 bytes or timeout (set in serial.Serial)
        response = self.ftdi.ser.read(8)

        if not response:
            return None

        if self.checksum(response[:-1]) != response[-1]:  # Checksum is not the same
            module_logger.error("Checksum does not match - {} != {}" . format(self.checksum(response[:-1]), response[-1]))
            return None

        return response

    def tear_down(self):
        self.relay.clear(int(custom_data['RELAY_BOARDS_LN'], 16))

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
        inverse = False

        if strips_tester.data['status'][current_nest] == False:  # Test FAIL
            inverse = True

        datamatrix = '{}{:07d}' . format(date_full,self.get_new_serial())
        self.add_measurement(current_nest, True, "serial", datamatrix, "")

        params = [s for s in strips_tester.data['program'].split("_")]

        firmware = params[0]  # GADF or GAHF

        if firmware == "GADF":
            garo = "109561"
        else:
            garo = "41948"

        label = self.godex.load_label(strips_tester.settings.test_dir + "label/label20x9.txt")
        label.format(firmware = firmware, saop=params[3], version = params[2],qc=strips_tester.data['worker_id'], datamatrix=datamatrix,garo=garo)

        self.godex.send_to_printer(label, inverse)

        return

    def tear_down(self):
        self.godex.close()

