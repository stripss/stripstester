import RPi.GPIO as GPIO
import devices
from config_loader import *
from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task, timeout
import datetime
import pigpio

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays
custom_data = strips_tester.settings.custom_data

class DeviceManager:
    def __init__(self):
        try:
            strips_tester.data['devices']
        except KeyError:
            strips_tester.data['devices'] = []

    def open(self, device):
        if device.found:
            print("Device loaded successfully")
            strips_tester.data['devices'].append(device)

    def close(self, device):
        device.close()
        return

# Working
class RelayBoard:
    # This is custom class for IMI EMO.
    def __init__(self, order, invert):
        self.size = len(order)
        self.order = order  # List of ordered relays
        self.invert = invert

        try:
            strips_tester.data['shifter']
        except Exception:  # If shifter state instance does not exist, create it
            strips_tester.data['shifter'] = 0x0000
            self.shiftOut()

        return


    def set(self, mask):
        mask = self.format_mask(mask)

        strips_tester.data['shifter'] = strips_tester.data['shifter'] | mask  # Assign shifter global memory
        self.shiftOut()

    def clear(self, mask):
        mask = self.format_mask(mask)

        strips_tester.data['shifter'] = strips_tester.data['shifter'] & ~mask  # Assign shifter global memory
        self.shiftOut()

    def format_mask(self, mask):
        if type(mask) == str:  # If mask is string (imported from JSON), convert to hex
            mask = int(mask, 16)

        return mask

    def shiftOut(self):
        # Translate binary data to int array
        self.state = [int(d) for d in bin(strips_tester.data['shifter'])[2:].zfill(self.size)]
        self.state.reverse()  # LSB to MSB conversion

        for x in range(self.size):
            if not self.invert:
                GPIO.output(gpios['SHIFTER_DATA'], self.state[self.order[x] - 1])
            else:
                GPIO.output(gpios['SHIFTER_DATA'], not self.state[self.order[x] - 1])

            GPIO.output(gpios['SHIFTER_CLOCK'], 1)
            GPIO.output(gpios['SHIFTER_CLOCK'], 0)

        # Latch data into output
        GPIO.output(gpios['SHIFTER_LATCH'], 0)
        GPIO.output(gpios['SHIFTER_LATCH'], 1)

        # Enable outputs
        GPIO.output(gpios['SHIFTER_OE'], 0)

        return

class StartProcedureTask(Task):
    def set_up(self):
        self.relay = RelayBoard([7,5,3,1,9,11,13,15,10,12,14,16,8,6,4,2], False)

    def run(self) -> (bool, str):
        self.relay.clear(0xFFFF)
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        # Wait for selection of program
        while True:
            try:
                strips_tester.data['program_flash']
                strips_tester.data['program_eeprom']

                try:
                    strips_tester.data['first_program_set']
                except KeyError:  # First program was set
                    gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 0), "blink": (0, 0, 0)})  # Disable blink
                    strips_tester.data['first_program_set'] = True
                    module_logger.info("First program was set")
                break
            except KeyError:
                # Set on blinking lights
                GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(gpios['LIGHT_RED'], GPIO.LOW)
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.LOW)
                time.sleep(0.5)

        module_logger.info("Waiting for detection switch")
        gui_web.send({"command": "status", "nest": 0, "value": "Za začetek testa vstavi kos"})

        # Wait for DUT detect and lid to close
        while not self.lid_closed() or GPIO.input(gpios['DUT_DETECT']):
            time.sleep(0.001)

        # Check if DUT exists
        strips_tester.data['exist'][0] = True

        # Set on working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)

        # Start counting, clear GUI
        self.start_test(0)

        return

    def tear_down(self):
        pass


class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B5BE.voltage1", 0.1)  # DC Voltage
        self.voltmeterAC = devices.YoctoVoltageMeter("VOLTAGE1-10B5BE.voltage2", 0.1)  # AC Voltage
        self.relay = RelayBoard([7,5,3,1,9,11,13,15,10,12,14,16,8,6,4,2], False)

        #self.servo = GPIO.PWM(gpios['SERVO'], 50)
        #self.servo.start(4)

        self.pi = pigpio.pi()

    def run(self):
        # Connect 12V to DUT and connect VCC-D to voltmeter
        self.relay.set(custom_data['RELAY_DUT_POWER'])

        self.relay.set(custom_data['RELAY_VCC-D'])

        # Measure 3V3
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 5.0, 0.15, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        gui_web.send({"command": "progress", "value": "20"})

        if not num_of_tries:
            module_logger.warning("VCC-D is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "value": "Meritev napetosti VCC-D je izven območja: {}V".format(voltage)})
            self.add_measurement(0, False, "VCC-D", voltage, "V")
        else:
            module_logger.info("VCC-D in bounds: meas: %sV", voltage)
            gui_web.send({"command": "info", "value": "Meritev napetosti VCC-D: {}V".format(voltage)})
            self.add_measurement(0, True, "VCC-D", voltage, "V")

        gui_web.send({"command": "progress", "value": "10"})

        # Product fail at voltage reading
        if not self.is_product_ready(0):
            return

        # Disconnect voltmeter from VCC-D but keep power
        self.relay.clear(custom_data['RELAY_VCC-D'])

        # Set MCU in RESET mode (so all pins are input)
        self.relay.set(custom_data['RELAY_MCU_RESET'])

        time.sleep(0.1)

        # Apply 5V to HALL-P
        self.relay.set(custom_data['RELAY_HALL-P'])

        # Read Hall analog value
        self.relay.set(custom_data['RELAY_HALL-A'])

        self.servo_hall(True)

        # Measure Hall sensor
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 0.0, 0.1, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Hall voltage (magnet) is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "value": "Napetost hall senzorja z magnetom je izven območja: {}V".format(voltage)})
            self.add_measurement(0, False, "hall-magnet", voltage, "V")
        else:
            module_logger.info("Hall voltage (magnet) in bounds: meas: %sV", voltage)
            gui_web.send({"command": "info", "value": "Test hall senzorja z magnetom: {}V".format(voltage)})
            self.add_measurement(0, True, "hall-magnet", voltage, "V")

        gui_web.send({"command": "progress", "value": "20"})

        self.servo_hall(False)

        # Measure Hall sensor
        num_of_tries = 10

        voltage = self.voltmeter.read()
        while not self.in_range(voltage, 2.4, 0.1, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Hall voltage (without magnet) is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "value": "Napetost hall senzorja brez magneta je izven območja: {}V".format(voltage)})
            self.add_measurement(0, False, "hall-no-magnet", voltage, "V")
        else:
            module_logger.info("Hall voltage (no magnet) in bounds: meas: %sV", voltage)
            gui_web.send({"command": "info", "value": "Test hall senzorja brez magneta: {}V".format(voltage)})
            self.add_measurement(0, True, "hall-no-magnet", voltage, "V")

        self.relay.clear(custom_data['RELAY_HALL-A'])

        # Detach 5V from HALL-P
        self.relay.clear(custom_data['RELAY_HALL-P'])

        gui_web.send({"command": "progress", "value": "30"})

        # Product fail at Hall reading
        if not self.is_product_ready(0):
            return

        # UY voltage test
        self.relay.set(custom_data['RELAY_UY1-A'])

        # Apply 5V to UY1-P
        self.relay.set(custom_data['RELAY_UY1-P'])
        self.relay.set(custom_data['RELAY_UY1'])

        uy1_outputs = []
        uy2_outputs = []

        uy1_outputs.append(self.measure_voltage("UY1-test1", 4.65))

        self.relay.clear(custom_data['RELAY_UY1'])
        # Read voltage with UY1 disabled
        uy1_outputs.append(self.measure_voltage("UY1-test2", 2.12))

        self.relay.clear(custom_data['RELAY_UY1-P'])
        self.relay.set(custom_data['RELAY_UY1'])

        uy1_outputs.append(self.measure_voltage("UY1-test3", 4.65))

        self.relay.clear(custom_data['RELAY_UY1'])

        # Read voltage with UY1 disabled
        #for i in range(10):
        #    print("Voltage UY1-A (UY1-P off, UY1 0V): {}" . format(self.voltmeter.read()))

        self.relay.clear(custom_data['RELAY_UY1-A'])

        if not all(uy1_outputs):
            module_logger.warning("Output UY1 functionality fail.")
            gui_web.send({"command": "error", "value": "Delovanje izhoda UY1 nepravilno."})
            self.add_measurement(0, False, "UY1_output", uy1_outputs, "")
        else:
            module_logger.info("Output UY1 OK.")
            gui_web.send({"command": "info", "value": "Delovanje izhoda UY1 OK."})
            self.add_measurement(0, True, "UY1_output", uy1_outputs, "")

        gui_web.send({"command": "progress", "value": "40"})

        # Product fail at UY1 reading
        if not self.is_product_ready(0):
            return

        # UY voltage test
        self.relay.set(custom_data['RELAY_UY2-A'])

        # Apply 5V to UY1-P
        self.relay.set(custom_data['RELAY_UY2-P'])
        self.relay.set(custom_data['RELAY_UY2'])

        # Read voltage
        uy2_outputs.append(self.measure_voltage("UY2-test1", 3.19))

        self.relay.clear(custom_data['RELAY_UY2'])
        # Read voltage with UY1 disabled
        uy2_outputs.append(self.measure_voltage("UY2-test2", 2.37))

        self.relay.clear(custom_data['RELAY_UY2-P'])
        self.relay.set(custom_data['RELAY_UY2'])

        # Read voltage
        uy2_outputs.append(self.measure_voltage("UY2-test3", 2.37))

        self.relay.clear(custom_data['RELAY_UY2'])
        # Read voltage with UY1 disabled
        #for i in range(10):
        #   print("Voltage UY2-A (UY2-P off, UY2 0V): {}".format(self.voltmeter.read()))

        self.relay.clear(custom_data['RELAY_UY2-A'])

        if not all(uy2_outputs):
            module_logger.warning("Output UY2 functionality fail.")
            gui_web.send({"command": "error", "value": "Delovanje izhoda UY2 nepravilno."})
            self.add_measurement(0, False, "UY2_output", uy2_outputs, "")
        else:
            module_logger.info("Output UY2 OK.")
            gui_web.send({"command": "info", "value": "Delovanje izhoda UY2 OK."})
            self.add_measurement(0, True, "UY2_output", uy2_outputs, "")

        gui_web.send({"command": "progress", "value": "50"})

        # Product fail at UY1 reading
        if not self.is_product_ready(0):
            return

        self.relay.set(custom_data['RELAY_TRIAC-PULLUP'])
        time.sleep(0.1)
        self.relay.set(custom_data['RELAY_TRIAC-P'])
        time.sleep(0.1)


        # Measure active Triac
        num_of_tries = 10

        voltage = self.voltmeterAC.read()
        while not self.in_range(voltage, 24, 4, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeterAC.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Triac (inactive) FAIL: meas: %sV", voltage)
            gui_web.send({"command": "error", "value": "Triak se ne izklopi. Izmerjeno {}V".format(voltage)})
            self.add_measurement(0, False, "TriacOFF", voltage, "V")
        else:
            module_logger.info("Triac (inactive) OK: meas: %sV", voltage)
            gui_web.send({"command": "info", "value": "Triak izklop OK. Izmerjeno {}V".format(voltage)})
            self.add_measurement(0, True, "TriacOFF", voltage, "V")

        gui_web.send({"command": "progress", "value": "60"})

        self.relay.set(custom_data['RELAY_TRIAC-D'])
        time.sleep(0.5)


        # Measure active Triac
        num_of_tries = 10

        voltage = self.voltmeterAC.read()
        while not self.in_range(voltage, 0, 2, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeterAC.read()

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Triac (active) FAIL: meas: %sV", voltage)
            gui_web.send({"command": "error", "value": "Triak se ne vklopi. Izmerjeno {}V".format(voltage)})
            self.add_measurement(0, False, "TriacON", voltage, "V")
        else:
            module_logger.info("Triac (active) OK: meas: %sV", voltage)
            gui_web.send({"command": "info", "value": "Triak vklop OK. Izmerjeno {}V".format(voltage)})
            self.add_measurement(0, True, "TriacON", voltage, "V")

        self.relay.clear(custom_data['RELAY_TRIAC-P'])
        self.relay.clear(custom_data['RELAY_TRIAC-D'])
        self.relay.clear(custom_data['RELAY_TRIAC-PULLUP'])

        self.relay.clear(custom_data['RELAY_MCU_RESET'])

        gui_web.send({"command": "progress", "value": "70"})

        return


    def measure_voltage(self, name, expected):
        #for a in range(30):
        #    print(self.voltmeter.read())

        num_of_tries = 10

        voltage = self.voltmeter.read()

        while not self.in_range(voltage, expected, 0.1, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()

            print("   Retrying {}... {}V".format(name,voltage))

            if not num_of_tries:
                return False

        print(" ")
        return True

    def servo_hall(self, enable):
        if enable:
            self.pi.set_servo_pulsewidth(19, 1200)
            #self.servo.ChangeDutyCycle(3.25)
        else:
            #self.servo.ChangeDutyCycle(4)
            self.pi.set_servo_pulsewidth(19, 1350)

        return

    def tear_down(self):
        self.pi.stop()  # At the end of the program, stop the PWM
        self.voltmeter.close()
        self.voltmeterAC.close()


class FlashMCU(Task):
    def set_up(self):
        self.relay = RelayBoard([7, 5, 3, 1, 9, 11, 13, 15, 10, 12, 14, 16, 8, 6, 4, 2], False)
        self.atmel = devices.ATMEL_ICE()

        # Set ATTINY88 Microprocessor
        self.atmel.set_mcu('t88')

        if strips_tester.data['program_flash'] != -1:
            self.atmel.set_binary(strips_tester.settings.test_dir + "/bin/" + strips_tester.data['program_flash'] + ".hex")
        else:
            self.atmel.set_binary(None)

        if strips_tester.data['program_eeprom'] != -1:
            self.atmel.set_eeprom(strips_tester.settings.test_dir + "/bin/" + strips_tester.data['program_eeprom'] + ".eep")
        else:
            self.atmel.set_eeprom(None)


    def run(self):
        # Product fail - skip programming
        if not self.is_product_ready(0):
            return

        self.relay.set(custom_data['RELAY_PROGARMMER_COMMON_GND'])

        num_of_tries = 5

        gui_web.send({"command": "progress", "value": "80"})
        success = self.atmel.upload()

        # Flashing not succeded
        while not success:
            num_of_tries = num_of_tries - 1

            # Reset the programmer (SW reset)
            self.atmel.reset_programmer()

            success = self.atmel.upload()

            if not num_of_tries:
                break


        flash_nice = "brez" if strips_tester.data['program_flash'] == -1 else strips_tester.data['program_flash']
        eeprom_nice = "brez" if strips_tester.data['program_eeprom'] == -1 else strips_tester.data['program_eeprom']

        if not num_of_tries:
            gui_web.send({"command": "error", "value": "Programiranje ni uspelo!"})
            self.add_measurement(0, False, "Programming", [flash_nice, eeprom_nice], "")
        else:
            gui_web.send({"command": "info", "value": "Programiranje uspelo."})
            self.add_measurement(0, True, "Programming", [flash_nice, eeprom_nice], "")

        self.relay.clear(custom_data['RELAY_PROGARMMER_COMMON_GND'])
        return

    def tear_down(self):
        # Close the programmer
        self.atmel.close()

class ProductConfigTask(Task):
    def set_up(self):
        pass

    def run(self):
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == -1:  # If product is marked as untested
                strips_tester.data['status'][0] = True

        return

    def tear_down(self):
        pass


class FinishProcedureTask(Task):
    def set_up(self):
        return

    def run(self):
        # gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 1, 0)})
        gui_web.send({"command": "status", "nest": 0, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        # Set off working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.LOW)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.LOW)
        GPIO.output(gpios['BUZZER'], GPIO.HIGH)

        mode = 0
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0]:
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
                mode = 1
            else:
                GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        self.start_buzzer_thread = threading.Thread(target=self.start_buzzer, args=(mode,))
        self.start_buzzer_thread.start()

        # Wait for lid to open
        while self.lid_closed():
            time.sleep(0.01)

        return

    def start_buzzer(self, mode):
        if not mode:  # Mode for bad test (4 short buzz)
            for i in range(4):
                GPIO.output(gpios['BUZZER'], True)
                time.sleep(0.1)
                GPIO.output(gpios['BUZZER'], False)
                time.sleep(0.1)
        else:
            for i in range(2):  # Mode for good test  (2 long buzz)
                GPIO.output(gpios['BUZZER'], True)
                time.sleep(0.25)
                GPIO.output(gpios['BUZZER'], False)
                time.sleep(0.25)

    def tear_down(self):
        return
