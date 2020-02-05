import RPi.GPIO as GPIO
import devices
from config_loader import *
from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task, timeout
import datetime

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


class StartProcedureTask(Task):
    def set_up(self):
        pass

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

        module_logger.info("Waiting for detection switch")
        gui_web.send({"command": "status", "nest": 0, "value": "Za začetek testa priklopi modul"})

        # Wait for lid to close
        while not self.lid_closed():
            time.sleep(0.001)

        # Assume that product exists, because the start switch is made this way
        strips_tester.data['exist'][0] = True
        self.add_measurement(0, True, "Type", strips_tester.data['program'][1], "")

        # Set on working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)

        gui_web.send({"command": "measurements", "led": None})

        # Start counting, clear GUI
        self.start_test(0)

        return

    def tear_down(self):
        pass


class CurrentTest(Task):
    def set_up(self):
        try:
            strips_tester.data['device_yocto']
        except KeyError:  # Ammeter not initialized yet
            strips_tester.data['device_yocto'] = devices.YoctoVoltageMeter("YAMPMK01-EC277.current1", 0.1)

        self.ammeter = strips_tester.data['device_yocto']
        return

    def run(self):
        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje toka"})

        # Measure current
        num_of_tries = 10

        currents = [int(s) for s in strips_tester.data['program'][2].split() if s.isdigit()]
        min_current = currents[0]
        max_current = currents[1]

        expected = (min_current + max_current) / 2
        tolerance = abs(min_current - max_current) / 2

        current = self.ammeter.read()
        while not self.in_range(current, expected, tolerance, False):
            num_of_tries = num_of_tries - 1

            current = self.ammeter.read()

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

        return

    def tear_down(self):
        pass


class LightTest(Task):
    def set_up(self):
        try:
            strips_tester.data['device_feasa1']
            module_logger.info("Device FeasaM335 initalized successfully.")
        except KeyError:  # Feasa not initialized yet
            strips_tester.data['device_feasa1'] = devices.Feasa("/dev/feasaM335")

        try:
            strips_tester.data['device_feasa2']
            module_logger.info("Device FeasaN218 initalized successfully.")
        except KeyError:  # Feasa not initialized yet
            strips_tester.data['device_feasa2'] = devices.Feasa("/dev/feasaN218")

        self.feasa1 = strips_tester.data['device_feasa1']
        self.feasa2 = strips_tester.data['device_feasa2']

        return

    def run(self):
        min_left = 9999
        max_left = 0
        min_right = 9999
        max_right = 0
        min = 9999
        max = 0

        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje svetilnosti"})

        # Capture all measurements from Feasa
        if not self.feasa1.capture(5) or not self.feasa2.capture(5):
            module_logger.error("ERROR Capturing from Feasa device")

        # Retrieve CCT values for all LEDs
        cct = self.feasa1.get_CCT()
        rgb = self.feasa1.get_RGB()
        hsi = self.feasa1.get_HSI()

        # Retrieve values from second Feasa module
        cct.extend(self.feasa2.get_CCT())
        rgb.extend(self.feasa2.get_RGB())
        hsi.extend(self.feasa2.get_HSI())

        for current_led in range(len(cct)):  # Loop through all LEDs
            if current_led <= 8:
                if cct[current_led] < min_left: min_left = cct[current_led]
                if cct[current_led] > max_left: max_left = cct[current_led]
            else:
                if cct[current_led] < min_right: min_right = cct[current_led]
                if cct[current_led] > max_right: max_right = cct[current_led]

            if cct[current_led] < min: min = cct[current_led]
            if cct[current_led] > max: max = cct[current_led]

            if strips_tester.data['program'][1] == 'P2Z':
                # Check colour
                pass
            else:
                if cct[current_led] < 4000 or cct[current_led] > 5000:
                    module_logger.warning("CCT of LED{} is out of bounds: meas: {}K" . format(current_led + 1, cct[current_led]))
                    gui_web.send({"command": "error", "nest": 0, "value": "Meritev barve na LED #{} je izven območja: {}K".format(current_led + 1, cct[current_led])})
                    self.add_measurement(0, False, "LED{}_CCT" . format(current_led + 1), cct[current_led], "K")
                else:
                    module_logger.info("CCT of LED{} in bounds: meas: {}K" . format(current_led + 1, cct[current_led]))
                    gui_web.send({"command": "info", "nest": 0, "value": "Meritev barve LED#{}: {}K".format(current_led + 1, cct[current_led])})
                    self.add_measurement(0, True, "LED{}_CCT" . format(current_led + 1), cct[current_led], "K")

            # Check intensity range
            if hsi[current_led]['I'] < 30000:
                module_logger.warning("Intensity of LED{} is out of bounds: meas: {}" . format(current_led + 1, hsi[current_led]['I']))
                gui_web.send({"command": "error", "nest": 0, "value": "Meritev svetilnosti na LED #{} je izven območja: {}i".format(current_led + 1, hsi[current_led]['I'])})
                self.add_measurement(0, False, "LED{}_Intensity" . format(current_led + 1), hsi[current_led]['I'], "i")
            else:
                module_logger.info("Intensity of LED{} in bounds: meas: {}i" . format(current_led + 1, hsi[current_led]['I']))
                gui_web.send({"command": "info", "nest": 0, "value": "Meritev svetilnosti LED#{}: {}i".format(current_led + 1, hsi[current_led]['I'])})
                self.add_measurement(0, True, "LED{}_Intensity" . format(current_led + 1), hsi[current_led]['I'], "i")

            gui_web.send({"command": "measurements", "led": {'position': current_led + 1, 'cct': cct[current_led], 'rgb': rgb[current_led], 'hsi': hsi[current_led]}})

        print("left: ", end="")
        print(min_left, max_left, abs(min_left-max_left))
        print("right: ", end="")
        print(min_right, max_right, abs(min_right-max_right))
        print("both: ", end="")
        print(min, max, abs(min-max))

        # Wait for switch to be released
        while self.lid_closed():
            time.sleep(0.001)

        return

    def tear_down(self):
        pass


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


class PrintSticker(Task):
    def set_up(self):
        # Initalize Godex with USB interface
        self.godex = devices.Godex(interface=2)

    def run(self):

        if not self.godex.found:
            gui_web.send({"command": "error", "nest": 0, "value": "Tiskalnika ni mogoče najti!"})
        else:
            if strips_tester.data['status'][0] == True:
                self.print_sticker()

        return

    def print_sticker(self):
        date = datetime.datetime.now()
        date_format = date.strftime("%Y-%V")  # Generate date format

        serial = "HULE-{:07d}".format(self.get_new_serial())
        self.add_measurement(0, True, "serial", serial, "")

        # Get correct code and revision
        hulecode = strips_tester.data['program'][3]
        revision = strips_tester.data['program'][4]

        # Load label with macros
        label = self.godex.load_label(strips_tester.settings.test_dir + "/label/HULE_Label.txt")
        label = label.format(hulecode=hulecode, datetime=date_format, revision=revision, serial=serial)
        label = self.godex.set_datamatrix_size(label, len(serial))

        # Execute printing
        self.godex.send_to_printer(label)
        time.sleep(1)

        return

    def tear_down(self):
        # Close Godex device if serial interface
        self.godex.close()


class FinishProcedureTask(Task):
    def set_up(self):
        return

    def run(self):
        # gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 1, 0)})
        gui_web.send({"command": "status", "nest": 0, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": 0, "value": "90"})

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

        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        self.start_buzzer_thread = threading.Thread(target=self.start_buzzer, args=(mode,))
        self.start_buzzer_thread.start()

        # Wait for lid to open
        #while self.lid_closed():
        #    time.sleep(0.01)

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
