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
        pass

    def run(self) -> (bool, str):
        strips_tester.data['exist_left'] = True  # Assume it exists
        strips_tester.data['exist_right'] = True  # Assume it exists
        strips_tester.data['exist'][0] = 1
        strips_tester.data['exist'][1] = 1

        strips_tester.data['status_left'] = -1  # Untested
        strips_tester.data['status_right'] = -1  # Untested

        #gui_web.send({"command": "title", "value": "GO-HA 2"})

        if "START_SWITCH" in settings.gpios:
            gui_web.send({"command": "status", "value": "Za testiranje pritisni tipko."})

            for i in range(2):
                gui_web.send({"command": "progress", "nest": i, "value": "0"})

            while True:
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
                if not state_GPIO_SWITCH:
                    break

                time.sleep(0.01)

            for i in range(2):
                gui_web.send({"command": "error", "nest": i, "value": -1})  # Clear all error messages
                gui_web.send({"command": "info", "nest": i, "value": -1})  # Clear all error messages
                gui_web.send({"command": "semafor", "nest": i, "value": (0, 1, 0), "blink": (0, 0, 0)})

                strips_tester.data['start_time'][i] = datetime.datetime.utcnow()  # Get start test date
                gui_web.send({"command": "time", "mode": "start", "nest": i})  # Start count for test


            gui_web.send({"command": "status", "value": "Testiranje v teku..."})

            # Set working LED
            GPIO.output(gpios["left_red_led"], True)
            GPIO.output(gpios["left_green_led"], True)
            GPIO.output(gpios["right_red_led"], True)
            GPIO.output(gpios["right_green_led"], True)

        # Move stepper to zero
        arduino = devices.ArduinoSerial('/dev/ttyUSB0', baudrate=9600)
        status = arduino.write("move 0", 5)

        if not status:
            for current_nest in range(strips_tester.data['test_device_nests']):
                strips_tester.data['exist'][current_nest] = False

            self.end_test()

        arduino.close()

        gui_web.send({"command": "progress", "value": "10", "nest": 0})
        gui_web.send({"command": "progress", "value": "20", "nest": 1})

        return

    def tear_down(self):
        pass



# OK
class FinishProcedureTask(Task):
    def set_up(self):
        pass

    def run(self):
        for current_nest in range(strips_tester.data['test_device_nests']):
            if strips_tester.data['exist'][current_nest]:
                if strips_tester.data['status'][current_nest] == -1:
                    strips_tester.data['status'][current_nest] = True

        for i in range(2):
            gui_web.send({"command": "semafor", "nest": i, "value": (0, 0, 0), "blink": (0, 0, 0)})
            gui_web.send({"command": "progress", "nest": i, "value": "100"})

        # Disable all relays
        GPIO.output(gpios["relay1"], True)
        GPIO.output(gpios["relay2"], True)
        GPIO.output(gpios["relay3"], True)
        GPIO.output(gpios["relay4"], True)

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

        time.sleep(1)
        return

    def tear_down(self):
        pass


class VoltageTest(Task):
    def set_up(self):
        self.voltmeter = devices.INA219()

    def run(self) -> (bool, str):
        GPIO.output(gpios["relay1"], False) # Measure left side
        GPIO.output(gpios["relay2"], False) # Turn VCC ON
        GPIO.output(gpios["relay3"], True)
        GPIO.output(gpios["relay4"], True) # Measure left side
        normal_left_off = self.measure()
        gui_web.send({"command": "progress", "value": "20", "nest": 0})
        GPIO.output(gpios["relay3"], False) # Measure left side
        hall_left_off = self.measure()
        gui_web.send({"command": "progress", "value": "30", "nest": 0})

        GPIO.output(gpios["relay1"], True) # Measure left side
        GPIO.output(gpios["relay4"], False) # Measure left side
        hall_right_on = self.measure()
        gui_web.send({"command": "progress", "value": "30", "nest": 1})
        GPIO.output(gpios["relay3"], True) # Measure left side
        normal_right_on = self.measure()
        gui_web.send({"command": "progress", "value": "50", "nest": 0})
        gui_web.send({"command": "progress", "value": "50", "nest": 1})

        # Move stepper to end
        arduino = devices.ArduinoSerial('/dev/ttyUSB0', baudrate=9600)
        status = arduino.write("move 5500", 5)

        if not status:
            for current_nest in range(strips_tester.data['test_device_nests']):
                strips_tester.data['exist'][current_nest] = False

            self.end_test()
        arduino.close()

        normal_right_off = self.measure()
        gui_web.send({"command": "progress", "value": "70", "nest": 1})
        GPIO.output(gpios["relay3"], False) # Measure left side
        hall_right_off = self.measure()
        gui_web.send({"command": "progress", "value": "80", "nest": 1})

        GPIO.output(gpios["relay4"], True) # Measure left side
        GPIO.output(gpios["relay1"], False) # Measure right side
        hall_left_on = self.measure()
        gui_web.send({"command": "progress", "value": "70", "nest": 0})

        GPIO.output(gpios["relay3"], True) # Measure left side
        normal_left_on = self.measure()
        gui_web.send({"command": "progress", "value": "80", "nest": 0})

        GPIO.output(gpios["relay2"], True) # Turn VCC FF

        if 0.5 < hall_left_off < 1 and 0.5 < hall_left_on < 1 and 4.5 < normal_left_off < 5.0 and 4.5 < normal_left_on < 5.0:
            strips_tester.data['exist'][0] = False

        if 0.5 < hall_right_off < 1 and 0.5 < hall_right_on < 1 and 4.5 < normal_right_off < 5.0 and 4.5 < normal_right_on < 5.0:
            strips_tester.data['exist'][1] = False

        if strips_tester.data['exist'][0]:
            strips_tester.data['status'][0] = True  # Set as good

            if self.in_range(normal_left_off,4.5,1,False):
                self.add_measurement(0, True, "normal_off", normal_left_off,"V")
                gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti levega hall senzorja brez magneta: {}V\n".format(normal_left_off)})
            else:
                self.add_measurement(0, False, "normal_off", normal_left_off,"V")
                gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti levega hall senzorja brez magneta: {}V\n".format(normal_left_off)})

            if self.in_range(normal_left_on,0,1,False):
                self.add_measurement(0, True, "normal_on", normal_left_on,"V")
                gui_web.send({"command": "info", "nest": 0, "value": "Meritev napetosti levega hall senzorja v okolici magneta: {}V\n".format(normal_left_on)})
            else:
                self.add_measurement(0, False, "normal_on", normal_left_on,"V")
                gui_web.send({"command": "error", "nest": 0, "value": "Meritev napetosti levega hall senzorja v okolici magneta: {}V\n".format(normal_left_on)})

        if strips_tester.data['exist'][1]:
            strips_tester.data['status'][1] = True  # Set as good

            if self.in_range(normal_right_off,4.5,1,False):
                self.add_measurement(1, True, "normal_off", normal_right_off,"V")
                gui_web.send({"command": "info", "nest": 1, "value": "Meritev napetosti desnega hall senzorja brez magneta: {}V\n".format(normal_right_off)})
            else:
                self.add_measurement(1, False, "normal_off", normal_right_off,"V")
                gui_web.send({"command": "error", "nest": 1, "value": "Meritev napetosti desnega hall senzorja brez magneta: {}V\n".format(normal_right_off)})

            if self.in_range(normal_right_on,0,1,False):
                self.add_measurement(1, True, "normal_on", normal_right_on,"V")
                gui_web.send({"command": "info", "nest": 1, "value": "Meritev napetosti desnega hall senzorja v okolici magneta: {}V\n".format(normal_right_on)})
            else:
                self.add_measurement(1, False, "normal_on", normal_right_on,"V")
                gui_web.send({"command": "error", "nest": 1, "value": "Meritev napetosti desnega hall senzorja v okolici magneta: {}V\n".format(normal_right_on)})

        return

    def tear_down(self):
        pass

    def measure(self,tag = "none"):
        sleep = 0.2
        time.sleep(sleep)
        voltage = self.voltmeter.voltage()
        #print("{}: {}V" . format(tag,voltage))
        return voltage

    def in_range(self, value, expected, tolerance, percent=True):
        if percent:
            tolerance_min = expected - expected * (tolerance / 100.0)
            tolerance_max = expected + expected * (tolerance / 100.0)
        else:
            tolerance_min = expected - tolerance
            tolerance_max = expected + tolerance

        if value > tolerance_min and value < tolerance_max:
            return True
        else:
            return False