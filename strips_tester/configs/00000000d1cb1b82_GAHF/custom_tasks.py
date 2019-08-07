## -*- coding: utf-8 -*-
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import *
from tester import Task
import datetime

gpios = strips_tester.settings.gpios

class StartProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

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

        # Product power on
        self.relay.set(0x1)

        # Product detection
        for i in range(2):
            strips_tester.data['exist'][i] = not GPIO.input(strips_tester.settings.gpios.get("DUT_{}_DETECT" . format(i)))

            if strips_tester.data['exist'][i]:
                gui_web.send({"command": "info", "nest": i, "value": "Zaznan kos."})

        # Move stepper to end
        arduino = devices.ArduinoSerial('/dev/nano', baudrate=9600)

        for i in range(6):
            arduino.write("servo {} 30" . format(i), 5)
            time.sleep(0.1)
            arduino.write("servo {} 0" . format(i), 5)
            time.sleep(0.1)

        arduino.close()

        return

    def tear_down(self):
        pass


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
        #print("set {} to {}" . format(mask,strips_tester.data['shifter']))
        self.shiftOut()

    def clear(self, mask):
        strips_tester.data['shifter'] = strips_tester.data['shifter'] & ~mask  # Assign shifter global memory
        self.shiftOut()

    def byte_to_binary(self, n, size):
        return ''.join(str((n & (1 << i)) and 1) for i in reversed(range(size)))

    def shiftOut(self):
        GPIO.output(gpios['OE'], 1)
        GPIO.output(gpios['LATCH'], 0)

        #byte = self.byte_to_binary(strips_tester.data['shifter'], self.size)
        self.state = [int(d) for d in bin(strips_tester.data['shifter'])[2:].zfill(self.size)]
        self.state.reverse()

        for x in range(self.size):
            if not self.invert:

                #ordered = [7,5,3,1,9,11,13,15,10,12,14,16,8,6,4,2]
                #index = series * 16 + ordered.index(int(position[1:]))

                GPIO.output(gpios['DATA'], self.state[self.order[x + 1]])
            else:
                #print(self.state)
                #print("{} -> {}" . format(x,self.order[x]))

                GPIO.output(gpios['DATA'], not self.state[self.order[x] - 1])

            GPIO.output(gpios['CLOCK'], 1)
            GPIO.output(gpios['CLOCK'], 0)

        GPIO.output(gpios['LATCH'], 1)





# OK
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

        #time.sleep(1)
        return

    def tear_down(self):
        pass


class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-ED120.voltage1", 0.16)  # Rectified DC Voltage
        self.relay = RelayBoard([16,14,12,10,9,11,13,15,8,6,4,2,1,3,5,7], True)

    def run(self):
        # Power on
        self.relay.clear(0x1)
        time.sleep(1)
        self.relay.set(0x1)

        for i in range(2):
            # Check if product exists
            if not self.is_product_ready(i):
                continue

            gui_web.send({"command": "status", "nest": i, "value": "Meritev napetosti..."})

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
        self.flasher.set_binary(strips_tester.settings.test_dir + "/bin/gahf.hex")
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

            gui_web.send({"command": "status", "nest": i, "value": "Programiranje..."})

            if self.flasher.flash():  # Flashing begins
                gui_web.send({"command": "info", "nest": i, "value": "Programiranje uspelo."})
                self.add_measurement(i, True, "Programming", "OK", "")
            else:
                gui_web.send({"command": "error", "nest": i, "value": "Programiranje ni uspelo!"})
                self.add_measurement(i, False, "Programming", "FAIL", "")

            self.relay.clear(0xEC7C)

    def tear_down(self):
        pass

class VisualAndButtonTest(Task):
    def set_up(self):
        self.ftdi = []

        for i in range(2):
            self.ftdi.append(devices.ArduinoSerial('/dev/ftdi{}' . format(i + 1), baudrate=9600))

    def run(self):
        for i in range(2):
            # Check if product exists
            if not self.is_product_ready(i):
                continue

            for j in range(1):
                print(self.ftdi[i].write("Ping", response="ok", timeout=1, append="\13\10"))
                #print(self.ftdi[i].write("run LED_test 200", 3, append="\13\10"))


        time.sleep(3)

        # Initialize camera
        # Send UART code, wait for response
        # If response good, take pictures
        # Given picture, compare with mask provided
        print("VisualTest:)")

    def tear_down(self):
        for i in range(2):
            self.ftdi[i].close()
