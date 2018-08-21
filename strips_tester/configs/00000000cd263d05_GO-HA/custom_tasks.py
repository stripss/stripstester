
import importlib
import logging
import sys
import time
import multiprocessing
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import settings, server
from tester import Task




module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays

# You may set global test level and logging level in config_loader.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)


class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.pwm = GPIO.PWM(gpios["SERVO"], 50)
        self.pwm.start(0)
        self.i2c = devices.MCP23017()

        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "start_time" in definition['slug']:
                self.start_time = definition['value']

            if "end_time" in definition['slug']:
                self.end_time = definition['value']


    def run(self) -> (bool, str):
        time.sleep(self.start_time)

        GPIO.output(gpios["BUZZER"], True)
        GPIO.output(gpios["VCC"], True)
        GPIO.output(gpios["SIDE"], True)

        self.i2c.set_led_status(0x0f)

        time.sleep(0.1)

        return {"signal": [1, "ok", 5, "NA",""]}

    def SetAngle(self,angle):
        duty = angle / 18 + 2
        GPIO.output(gpios["SERVO"], True)
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(1)
        GPIO.output(gpios["SERVO"], False)
        self.pwm.ChangeDutyCycle(0)

    def tear_down(self):
        time.sleep(self.end_time)
        self.pwm.stop()



class EndProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        pass

    def run(self) -> (bool, str):

        self.SetAngle(0)

        if strips_tester.current_product.countbad:
            GPIO.output(gpios["BUZZER"],False)
            time.sleep(1)
            GPIO.output(gpios["BUZZER"], True)

        # 0 - off
        # 1 - red
        # 2 - green
        # 3 - yellow

        return {"signal": [1, "ok", 5, "NA",""]}

    def SetAngle(self,angle):
        duty = angle / 18 + 2

        self.pwm = GPIO.PWM(gpios["SERVO"], 50)
        self.pwm.start(duty)

        GPIO.output(gpios["SERVO"], True)
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(1)
        GPIO.output(gpios["SERVO"], False)
        self.pwm.stop()


    def tear_down(self):
        pass



class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.mesurement_delay = 0.16
        self.measurement_results = {}

        self.voltmeter = devices.INA219(0.1)
        self.voltmeter.configure()

        self.i2c = devices.MCP23017()

        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "max_voltage" in definition['slug']:
                self.max_voltage = definition['value']

            if "min_voltage" in definition['slug']:
                self.min_voltage = definition['value']

            if "tolerance" in definition['slug']:
                self.tolerance = definition['value']



    def run(self) -> (bool, str):
        sleep = 0.2
        led_status = 0x00
        skip_left = False
        skip_right = False

        GPIO.output(gpios["VCC"], False) # Turn VCC ON
        GPIO.output(gpios["SIDE"], False) # Measure other side
        time.sleep(sleep)

        voltage = self.voltmeter.voltage()

        # Magnet je pri levem kosu
        if not self.in_range(voltage, self.min_voltage - self.tolerance,self.min_voltage + self.tolerance):
            if voltage > 1.0 and voltage < 1.2:
                skip_left = True
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                self.measurement_results['voltage_left_min'] = [voltage, "fail", 1, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
            self.measurement_results['voltage_left_min'] = [voltage, "ok", 1, "NA"]


        GPIO.output(gpios["SIDE"], True) # Measure other side
        time.sleep(sleep)
        voltage = self.voltmeter.voltage()

        if not self.in_range(voltage, self.max_voltage - self.tolerance,self.max_voltage + self.tolerance):
            if voltage > 1.0 and voltage < 1.2:
                skip_right = True
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                self.measurement_results['voltage_right_max'] = [voltage, "fail", 1, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
            self.measurement_results['voltage_right_max'] = [voltage, "ok", 1, "NA"]

        server.send_broadcast({"text": {"text": "Premik magneta...\n", "tag": "black"}})

        self.SetAngle(180)
        time.sleep(sleep)

        voltage = self.voltmeter.voltage()

        if not self.in_range(voltage, self.min_voltage - self.tolerance,self.min_voltage + self.tolerance):
            if voltage > 1.0 and voltage < 1.2 and skip_right:
                pass
            else:

                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                self.measurement_results['voltage_right_min'] = [voltage, "fail", 1, "NA"]
        else:
            if skip_right:
                skip_right = False
                self.measurement_results['voltage_right_min'] = [voltage, "fail", 1, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
                self.measurement_results['voltage_right_min'] = [voltage, "ok", 1, "NA"]

        GPIO.output(gpios["SIDE"], False)  # Measure other side
        time.sleep(sleep)
        voltage = self.voltmeter.voltage()

        if not self.in_range(voltage, self.max_voltage - self.tolerance,self.max_voltage + self.tolerance):
            if voltage > 1.0 and voltage < 1.2 and skip_left:
                    pass
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                self.measurement_results['voltage_left_max'] = [voltage, "fail", 1, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
            self.measurement_results['voltage_left_max'] = [voltage, "ok", 1, "NA"]

        time.sleep(sleep)

        GPIO.output(gpios["VCC"], True)
        GPIO.output(gpios["SIDE"], True)

        info = ""

        if not skip_left:
            if self.measurement_results['voltage_left_min'][1] == "ok" and self.measurement_results['voltage_left_max'][1] == "ok":
                strips_tester.current_product.countgood = strips_tester.current_product.countgood + 1
                info += "- Levi kos OK\n"

                led_status = led_status | 0x01
            else:
                led_status = led_status | 0x02
                strips_tester.current_product.countbad = strips_tester.current_product.countbad + 1
                info += "- Levi kos FAIL\n"

        if not skip_right:
            if self.measurement_results['voltage_right_min'][1] == "ok" and self.measurement_results['voltage_right_max'][1] == "ok":
                strips_tester.current_product.countgood = strips_tester.current_product.countgood + 1
                led_status = led_status | 0x04
                info += "- Desni kos OK\n"
            else:
                strips_tester.current_product.countbad = strips_tester.current_product.countbad + 1
                led_status = led_status | 0x08
                info += "- Desni kos FAIL\n"

        if strips_tester.current_product.countgood != 2 and strips_tester.current_product.countbad != 2:
            server.send_broadcast({"task_update": {"task_slug": type(self).__name__, "task_info": info}})

        self.i2c.set_led_status(led_status)

        #if strips_tester.current_product.countbad:
            #GPIO.output(gpios["BUZZER"], False)

        return self.measurement_results


    def in_range(self,voltage,min,max):
        if(min < voltage < max):
            return True
        else:
            return False

    def SetAngle(self, angle):
        duty = angle / 18 + 2

        self.pwm = GPIO.PWM(gpios["SERVO"], 50)
        self.pwm.start(duty)

        GPIO.output(gpios["SERVO"], True)
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(1)
        GPIO.output(gpios["SERVO"], False)
        self.pwm.stop()


    def tear_down(self):
        pass


