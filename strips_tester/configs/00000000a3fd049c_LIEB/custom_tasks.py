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

class StartProcedureTask(Task):
    def set_up(self):
        pass

    def run(self) -> (bool, str):
        gui_web.send({"command": "progress", "nest": 0, "value": "0"})

        # Set relays to NC
        GPIO.output(gpios['13V_AC'], GPIO.HIGH)
        GPIO.output(gpios['24V_AC'], GPIO.HIGH)

        # Set relays to NO
        GPIO.output(gpios['13V_DC'], GPIO.LOW)
        GPIO.output(gpios['24V_DC'], GPIO.LOW)

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

        if "US" in strips_tester.data['program'][1]:
            GPIO.output(gpios['13V_DC'], GPIO.HIGH)
        else:  # Assume it is 24V (not US product)
            GPIO.output(gpios['24V_DC'], GPIO.HIGH)

        # Assume that product exists, because the start switch is made this way
        strips_tester.data['exist'][0] = True
        self.add_measurement(0, True, "SAOP", strips_tester.data['program'][0], "")

        # Set on working lights
        GPIO.output(gpios['LIGHT_RED'], GPIO.HIGH)
        GPIO.output(gpios['LIGHT_GREEN'], GPIO.HIGH)

        # Start counting, clear GUI
        self.start_test(0)

        return

    def tear_down(self):
        pass


class PowerTest(Task):
    def set_up(self):
        #self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B5AF.voltage1", 0.16)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-10B59C.voltage1", 0.1)
        self.ammeter = devices.YoctoVoltageMeter("YAMPMK01-110B4A.current1", 0.1)

        self.selected_voltage = 24

    def run(self):
        gui_web.send({"command": "status", "nest": 0, "value": "Merjenje moči"})

        if "US" in strips_tester.data['program'][1]:
            self.selected_voltage = 13.1

        self.voltage_thread = threading.Thread(target=self.measure_voltage)
        self.voltage_thread.daemon = True
        self.voltage_thread.start()

        self.current_thread = threading.Thread(target=self.measure_current)
        self.current_thread.daemon = True
        self.current_thread.start()

        # Wait for switch to be released
        while self.lid_closed():
            time.sleep(0.001)

        self.voltage_thread.join()
        self.current_thread.join()


        if "US" in strips_tester.data['program'][1]:
            GPIO.output(gpios['13V_DC'], GPIO.LOW)
        else:  # Assume it is 24V (not US product)
            GPIO.output(gpios['24V_DC'], GPIO.LOW)

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

        currents = [int(s) for s in strips_tester.data['program'][3].split() if s.isdigit()]
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

        # Set relays to NO
        #GPIO.output(gpios['13V_AC'], GPIO.LOW)
        GPIO.output(gpios['13V_DC'], GPIO.LOW)
        #GPIO.output(gpios['24V_AC'], GPIO.LOW)
        GPIO.output(gpios['24V_DC'], GPIO.LOW)

        time.sleep(0.75)

        GPIO.output(gpios['BUZZER'], GPIO.LOW)

        # Wait for lid to open
        #while self.lid_closed():
        #    time.sleep(0.01)

        return

    def tear_down(self):
        pass
