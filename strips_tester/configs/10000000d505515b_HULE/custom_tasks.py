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
        except KeyError:
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
        except KeyError:
            strips_tester.data['device_feasa1'] = devices.Feasa("/dev/feasaN218")

        try:
            strips_tester.data['device_feasa2']
        except KeyError:
            strips_tester.data['device_feasa2'] = devices.Feasa("/dev/feasaM335")

        self.feasa1 = strips_tester.data['device_feasa1']
        self.feasa2 = strips_tester.data['device_feasa2']

        return

    def run(self):
        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje svetilnosti"})

        # Capture all measurements from Feasa
        if not self.feasa1.capture(5) or not self.feasa2.capture(5):
            print("ERROR Capturing from Feasa device")

        # Retrieve CCT values for all LEDs
        cct = self.feasa1.get_CCT()
        rgb = self.feasa1.get_RGB()
        hsi = self.feasa1.get_HSI()

        # Retrieve values from second Feasa module
        cct.extend(self.feasa2.get_CCT())
        rgb.extend(self.feasa2.get_RGB())
        hsi.extend(self.feasa2.get_HSI())

        for current_led in range(len(cct)):  # Loop through all LEDs
            if strips_tester.data['program'][1] == 'P2Z':
                # Check colour
                pass
            else:
                if not self.in_range(cct[current_led], 4300, 1000, False):
                    module_logger.warning("CCT of LED{} is out of bounds: meas: {}K" . format(current_led + 1, cct[current_led]))
                    gui_web.send({"command": "error", "nest": 0, "value": "Meritev barve na LED #{} je izven območja: {}K".format(current_led + 1, cct[current_led])})
                    self.add_measurement(0, False, "LED{}_CCT" . format(current_led + 1), cct[current_led], "K")
                else:
                    module_logger.info("CCT of LED{} in bounds: meas: {}K" . format(current_led + 1, cct[current_led]))
                    gui_web.send({"command": "info", "nest": 0, "value": "Meritev barve LED#{}: {}K".format(current_led + 1, cct[current_led])})
                    self.add_measurement(0, True, "LED{}_CCT" . format(current_led + 1), cct[current_led], "K")

                if not self.in_range(hsi[current_led]['I'], 15000, 5000, False):
                    module_logger.warning("Intensity of LED{} is out of bounds: meas: {}" . format(current_led + 1, hsi[current_led]['I']))
                    gui_web.send({"command": "error", "nest": 0, "value": "Meritev svetilnosti na LED #{} je izven območja: {}i".format(current_led + 1, hsi[current_led]['I'])})
                    self.add_measurement(0, False, "LED{}_Intensity" . format(current_led + 1), hsi[current_led]['I'], "i")
                else:
                    module_logger.info("Intensity of LED{} in bounds: meas: {}i" . format(current_led + 1, hsi[current_led]['I']))
                    gui_web.send({"command": "info", "nest": 0, "value": "Meritev svetilnosti LED#{}: {}i".format(current_led + 1, hsi[current_led]['I'])})
                    self.add_measurement(0, True, "LED{}_Intensity" . format(current_led + 1), hsi[current_led]['I'], "i")

            gui_web.send({"command": "measurements", "led": {'position': current_led + 1, 'cct': cct[current_led], 'rgb': rgb[current_led], 'hsi': hsi[current_led]}})

        # Wait for switch to be released
        while self.lid_closed():
            time.sleep(0.001)

        return

    def tear_down(self):
        pass


class ProductConfigTask(Task):
    def set_up(self):
        module_logger.debug("ProductConfigTask init")

    def run(self):
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == -1:  # If product is marked as untested
                strips_tester.data['status'][0] = True

        return

    def tear_down(self):
        pass


class PrintSticker(Task):
    def set_up(self):
        self.godex = devices.Godex()

    def run(self):
        # Lid is now opened.
        #if self.is_product_ready(0):
        if not self.godex.found:
            gui_web.send({"command": "error", "nest": 0, "value": "Tiskalnika ni mogoče najti!"})
        else:
            if strips_tester.data['status'][0] == True:
                self.print_sticker()

        return

    def print_sticker(self):
        date = datetime.datetime.now()
        date_week = date.strftime("%y%V")  # Generate calendar week

        serial = "{:07d}".format(self.get_new_serial())
        self.add_measurement(0, True, "serial", serial, "")

        if "LINO" in strips_tester.data['program'][1]:  # LINO Product - stickers 38x13mm
            params = [s for s in strips_tester.data['program'][1].split()]
            color = params[3]  # split program[1] and pick the color
            length = params[4]  # split program[1] and pick the length

            label_pcb = (
                '^Q13,3\n'
                '^W38\n'
                '^H15\n'
                '^P1\n'
                '^S2\n'
                '^AD\n'
                '^C1\n'
                '^R0\n'
                '~Q-8\n'
                '^O0\n'
                '^D0\n'
                '^E12\n'
                '~R255\n'
                '^L\n'
                'Dy2-me-dd\n'
                'Th:m:s\n'
                'AB,8,4,1,1,0,0E,LINO {color} {length}\n'
                'Lo,6,30,158,31\n'
                'AA,11,41,1,1,0,0E,Rated power: {power}\n'
                'AA,11,60,1,1,0,0E,Input: 24Vdc\n'
                'AA,11,79,1,1,0,0E,CCT: {cct}\n'
                'AA,174,10,1,1,0,0E,Class 2 input only\n'
                'AA,150,40,1,1,0,0E,Lieb. no.: {liebcode}\n'
                'AB,157,68,1,1,0,0E,www.strips.eu\n'
                'E\n').format(color=color, length=length, power=strips_tester.data['program'][4], cct=strips_tester.data['program'][5],liebcode=strips_tester.data['program'][2])

            self.godex.send_to_printer(label_pcb)

        elif "US" in strips_tester.data['program'][1]:  # LIEB US Modul - stickers 30x11mm
            label_pcb = (
                '^Q11,3\n'
                '^W30\n'
                '^H15\n'
                '^P1\n'
                '^S2\n'
                '^AD\n'
                '^C1\n'
                '^R0\n'
                '~Q-8\n'
                '^O0\n'
                '^D0\n'
                '^E12\n'
                '~R255\n'
                '^L\n'
                'Dy2-me-dd\n'
                'Th:m:s\n'
                'XRB11,8,4,0,26\n'
                '{ledcodeformat} {liebcode} {date}\n'
                'AB,97,6,1,1,0,0E,{ledcode}\n'
                'AB,97,32,1,1,0,0E,{liebcode}\n'
                'AB,97,58,1,1,0,0E,{date}/{serial}\n'
                'E\n').format(date=date_week,ledcodeformat=strips_tester.data['program'][4].replace("_"," "),ledcode=strips_tester.data['program'][4],liebcode=strips_tester.data['program'][2],serial=serial)

            self.godex.send_to_printer(label_pcb)
        else:  # LIEB LED Modul - stickers 25x7mm
            label_pcb = (
                '^Q7,3\n'
                '^W25\n'
                '^H15\n'
                '^P1\n'
                '^S2\n'
                '^AD\n'
                '^C1\n'
                '^R0\n'
                '~Q-8\n'
                '^O0\n'
                '^D0\n'
                '^E12\n'
                '~R255\n'
                '^L\n'
                'Dy2-me-dd\n'
                'Th:m:s\n'
                'XRB33,12,2,0,26\n'
                '{ledcodeformat} {liebcode} {date}\n'
                'AA,82,0,1,1,0,0E,{ledcode}\n'
                'AA,82,19,1,1,0,0E,{liebcode}\n'
                'AA,82,38,1,1,0,0E,{date}/{serial}\n'
                'E\n').format(date=date_week,ledcodeformat=strips_tester.data['program'][4].replace("_"," "),ledcode=strips_tester.data['program'][4],liebcode=strips_tester.data['program'][5],serial=serial)

            self.godex.send_to_printer(label_pcb)
            time.sleep(1)

            label_profile = (
                '^Q7,3\n'
                '^W25\n'
                '^H15\n'
                '^P1\n'
                '^S2\n'
                '^AD\n'
                '^C1\n'
                '^R0\n'
                '~Q-8\n'
                '^O0\n'
                '^D0\n'
                '^E12\n'
                '~R255\n'
                '^L\n'
                'Dy2-me-dd\n'
                'Th:m:s\n'
                'XRB29,4,3,0,15\n'
                '{liebcode} {date}\n'
                'AA,85,10,1,1,0,0E,{liebcode}\n'
                'AA,85,29,1,1,0,0E,{date}/{serial}\n'
                'E\n').format(date=date_week,liebcode=strips_tester.data['program'][2],serial=serial)

            self.godex.send_to_printer(label_profile)

        return

    def tear_down(self):
        self.godex.close()


class FinishProcedureTask(Task):
    def set_up(self):
        module_logger.debug("FinishProcedureTask init")

    def run(self):
        # gui_web.send({"command": "semafor", "nest": 0, "value": (0, 1, 0), "blink": (0, 1, 0)})
        gui_web.send({"command": "status", "nest": 0, "value": "Odstrani kos iz ležišča."})  # Clear all info messages
        gui_web.send({"command": "progress", "nest": 0, "value": "90"})

        # Set off working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.LOW)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.LOW)
        GPIO.output(gpios['BUZZER'], GPIO.HIGH)

        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0]:
                GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (0, 0, 1)})
            else:
                GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
                gui_web.send({"command": "semafor", "nest": 0, "value": (1, 0, 0)})

        gui_web.send({"command": "progress", "nest": 0, "value": "100"})

        GPIO.output(gpios['BUZZER'], GPIO.LOW)

        # Wait for lid to open
        #while self.lid_closed():
        #    time.sleep(0.01)

        return

    def tear_down(self):
        pass
