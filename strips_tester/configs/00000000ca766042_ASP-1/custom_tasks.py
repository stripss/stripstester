import RPi.GPIO as GPIO
import devices
from config_loader import *

from strips_tester import *
import strips_tester
from tester import Task, timeout

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays
custom_data = strips_tester.settings.custom_data

class StartProcedureTask(Task):
    def set_up(self):
        self.scanner = devices.Honeywell_1900HID(vid=0x05f9, pid=0x2216)

    def run(self) -> (bool, str):
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

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
                GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(gpios['LIGHT_RED'], GPIO.LOW)
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.LOW)
                time.sleep(0.5)

        self.add_measurement(0, True, "SAOP", strips_tester.data['program'][0], "")

        if not self.scanner.found:
            # Send warning but keep testing
            gui_web.send({"command": "error", "value": "Skenerja ni mogoče najti!"})
        else:
            gui_web.send({"command": "status", "nest": 0, "value": "Skeniraj QR kodo"})

            qr_code = self.scanner.read()

            self.add_measurement(0, True, "Serial", qr_code, "")
            gui_web.send({"command": "info", "nest": 0, "value": "Modul skeniran: {}".format(qr_code)})

        module_logger.info("Waiting for detection switch")
        gui_web.send({"command": "status", "nest": 0, "value": "Za začetek testa priklopi modul"})

        # Wait for lid to close
        while self.lid_closed():
            time.sleep(0.001)

        # Assume that product exists, because the start switch is made this way
        strips_tester.data['exist'][0] = True

        # Set on working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)

        # Start counting, clear GUI
        self.start_test(0)

        return

    def tear_down(self):
        self.scanner.close()

class ReadSerial(Task):
    def set_up(self):
        self.scanner = devices.Honeywell_1900HID(vid=0x0c2e, pid=0x0901)

    def run(self):
        self.add_measurement(0, True, "SAOP", strips_tester.data['program'][0], "")

        if not self.scanner.found:
            # Send warning but keep testing
            gui_web.send({"command": "error", "value": "Skenerja ni mogoče najti!"})
            return

        gui_web.send({"command": "status", "nest": 0, "value": "Skeniraj QR kodo"})

        qr_code = self.scanner.read()

        self.add_measurement(0, True, "Serial", qr_code, "")
        gui_web.send({"command": "info", "nest": 0, "value": "Modul skeniran: {}".format(qr_code)})

        return

    def tear_down(self):
        # Close the device?
        self.scanner.close()

class PowerTest(Task):
    def set_up(self):
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B572.voltage1", 0.1)
        self.ammeter = devices.YoctoVoltageMeter("YAMPMK01-EC255.current1", 0.1)
        self.selected_voltage = 48

    def run(self):
        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje moči"})

        # Set relays to NO
        GPIO.output(gpios['12V_AC'], GPIO.LOW)
        GPIO.output(gpios['12V_DC'], GPIO.LOW)
        GPIO.output(gpios['24V_AC'], GPIO.LOW)
        GPIO.output(gpios['24V_DC'], GPIO.LOW)
        GPIO.output(gpios['48V_AC'], GPIO.LOW)
        GPIO.output(gpios['48V_DC'], GPIO.LOW)

        time.sleep(0.1)  # Relay debouncing

        if "12V" in strips_tester.data['program'][1]:
            self.selected_voltage = 12
            GPIO.output(gpios['12V_DC'], GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpios['12V_AC'], GPIO.HIGH)
        elif "24V" in strips_tester.data['program'][1]:
            self.selected_voltage = 24
            GPIO.output(gpios['24V_DC'], GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpios['24V_AC'], GPIO.HIGH)
        else:  # Assume it is 48V
            GPIO.output(gpios['48V_DC'], GPIO.HIGH)
            time.sleep(0.1)
            GPIO.output(gpios['48V_AC'], GPIO.HIGH)

        self.voltage_thread = threading.Thread(target=self.measure_voltage)
        self.voltage_thread.daemon = True
        self.voltage_thread.start()

        self.current_thread = threading.Thread(target=self.measure_current)
        self.current_thread.daemon = True
        self.current_thread.start()

        self.voltage_thread.join()
        self.current_thread.join()

        return

    def measure_voltage(self):
        # Measure voltage
        num_of_tries = 10

        voltage = self.voltmeter.read()
        gui_web.send({"command": "measurements", "voltmeter": voltage})

        while not self.in_range(voltage, self.selected_voltage, 0.1, False):
            num_of_tries = num_of_tries - 1

            voltage = self.voltmeter.read()
            gui_web.send({"command": "measurements", "voltmeter": voltage})

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Voltage is out of bounds: meas: %sV", voltage)
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti je izven območja: {}V".format(voltage)})
            self.add_measurement(0, False, "Voltage", voltage, "V")
        else:
            module_logger.info("Voltage in bounds: meas: %sV", voltage)
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti: {}V".format(voltage)})
            self.add_measurement(0, True, "Voltage", voltage, "V")

    def measure_current(self):
        # Measure current
        num_of_tries = 10

        currents = [int(s) for s in strips_tester.data['program'][2].split() if s.isdigit()]
        min_current = currents[0]
        max_current = currents[1]

        expected = (min_current + max_current) / 2
        tolerance = abs(min_current - max_current) / 2

        # print("Expected: {}" . format(expected))
        # print("Tolerance: {}" . format(tolerance))
        current = self.ammeter.read()
        gui_web.send({"command": "measurements", "ammeter": round(current, 2)})
        while not self.in_range(current, expected, tolerance, False):
            num_of_tries = num_of_tries - 1

            current = self.ammeter.read()
            gui_web.send({"command": "measurements", "ammeter": round(current, 2)})

            if not num_of_tries:
                break

        if not num_of_tries:
            module_logger.warning("Current is out of bounds: meas: %smA", current)
            gui_web.send({"command": "error", "nest": 0, "value": "Meritev toka je izven območja: {}mA".format(current)})
            self.add_measurement(0, False, "Current", current, "mA")
        else:
            module_logger.info("Current in bounds: meas: %smA", current)
            gui_web.send({"command": "info", "nest": 0, "value": "Meritev toka: {}mA".format(current)})
            self.add_measurement(0, True, "Current", current, "mA")

    def tear_down(self):
        self.voltmeter.close()
        self.ammeter.close()

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
        pass

    def run(self):
        # gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 1, 0)})
        gui_web.send({"command": "status", "nest": 0, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": 0, "value": "90"})

        # Set off working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.LOW)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.LOW)

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

        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        # Wait for lid to open
        while not self.lid_closed():
            time.sleep(0.001)

        # Set relays to NO
        GPIO.output(gpios['12V_AC'], GPIO.LOW)
        GPIO.output(gpios['12V_DC'], GPIO.LOW)
        GPIO.output(gpios['24V_AC'], GPIO.LOW)
        GPIO.output(gpios['24V_DC'], GPIO.LOW)
        GPIO.output(gpios['48V_AC'], GPIO.LOW)
        GPIO.output(gpios['48V_DC'], GPIO.LOW)

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
        pass
