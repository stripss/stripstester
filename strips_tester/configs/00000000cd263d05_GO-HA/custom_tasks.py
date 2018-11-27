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

class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.pwm = GPIO.PWM(gpios["SERVO"], 50)
        self.pwm.start(0)

        self.lightboard = devices.MCP23017()

        time.sleep(self.get_definition("start_time"))

    def run(self) -> (bool, str):
        GPIO.output(gpios["BUZZER"], True)
        GPIO.output(gpios["VCC"], True)
        GPIO.output(gpios["SIDE"], True)

        # Hide all indicator lights
        self.lightboard.clear_bit(0xFFFF)

        # Working yellow LED lights
        self.lightboard.set_bit(0x0F)

        time.sleep(0.1)

        return type(self).__name__

    def SetAngle(self,angle):
        duty = angle / 18 + 2
        GPIO.output(gpios["SERVO"], True)
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(1)
        GPIO.output(gpios["SERVO"], False)
        #self.pwm.ChangeDutyCycle(0)
        self.pwm.stop()


    def tear_down(self):
        time.sleep(self.get_definition("end_time"))
        self.pwm.stop()



class EndProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.lightboard = devices.MCP23017()

    def run(self) -> (bool, str):

        self.SetAngle(0)


        beep = False
        if strips_tester.product[0].exist:
            if strips_tester.product[0].ok: # Product is bad
                beep = True
                self.lightboard.set_bit(0x02) # Red left light
            else:
                self.lightboard.set_bit(0x01) # Green left light
        else:
            self.lightboard.clear_bit(0x03) # No left light

        if strips_tester.product[1].exist:
            if strips_tester.product[1].ok:  # Product is bad
                beep = True
                self.lightboard.set_bit(0x08)  # Red right light
            else:
                self.lightboard.set_bit(0x04)  # Green right light
        else:
            self.lightboard.clear_bit(0x0C)  # No right light

        if not strips_tester.product[0].exist and not strips_tester.product[1].exist:
            beep = True

        if beep:
            GPIO.output(gpios["BUZZER"],False)
            time.sleep(1)
            GPIO.output(gpios["BUZZER"], True)


        # 0 - off
        # 1 - red
        # 2 - green
        # 3 - yellow

        return type(self).__name__

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

        self.voltmeter = devices.INA219(0.1)
        self.voltmeter.configure()

        self.i2c = devices.MCP23017()

        # Define custom definitions
        self.max_voltage = self.get_definition("max_voltage")
        self.min_voltage = self.get_definition("min_voltage")
        self.tolerance = self.get_definition("tolerance")


    def run(self) -> (bool, str):
        sleep = 0.2

        skip_left = False
        skip_right = False

        GPIO.output(gpios["VCC"], False) # Turn VCC ON
        GPIO.output(gpios["SIDE"], False) # Measure other side
        time.sleep(sleep)

        # Measure left voltage with magnet
        voltage = self.voltmeter.voltage()
        if voltage < 1.0 or voltage > 1.2:
            server.send_broadcast({"text": {"text": "Zaznan levi kos.\n", "tag": "black"}})

            strips_tester.product[0].exist = True

            # Kos obstaja, magnet je pri levem kosu
            if not self.in_range(voltage, self.min_voltage - self.tolerance,self.min_voltage + self.tolerance):
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_WARNING, voltage)
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_OK, voltage)
        else:
            server.send_broadcast({"text": {"text": "Ni zaznanega levega kosa.\n", "tag": "grey"}})

        # Measure right voltage with no magnet
        GPIO.output(gpios["SIDE"], True)
        time.sleep(sleep)


        voltage = self.voltmeter.voltage()
        if voltage < 1.0 or voltage > 1.2:
            server.send_broadcast({"text": {"text": "Zaznan desni kos.\n", "tag": "black"}})
            strips_tester.product[1].exist = True

            if not self.in_range(voltage, self.max_voltage - self.tolerance,self.max_voltage + self.tolerance):
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_WARNING, voltage)
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_OK, voltage)

        else:
            server.send_broadcast({"text": {"text": "Ni zaznanega desnega kosa.\n", "tag": "grey"}})

        # Premik magneta na desno stran
        self.SetAngle(180)
        time.sleep(sleep)

        if strips_tester.product[1].exist:
            voltage = self.voltmeter.voltage()

            if not self.in_range(voltage, self.min_voltage - self.tolerance,self.min_voltage + self.tolerance):
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_WARNING, voltage)
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMin", Task.TASK_OK, voltage)

        if strips_tester.product[0].exist:
            GPIO.output(gpios["SIDE"], False)  # Measure other side
            time.sleep(sleep)
            voltage = self.voltmeter.voltage()

            if not self.in_range(voltage, self.max_voltage - self.tolerance,self.max_voltage + self.tolerance):
                server.send_broadcast({"text": {"text": "Izmerjena napetost je izven območja! Izmerjeno {}V.\n" . format(voltage), "tag": "red"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_WARNING, voltage)
            else:
                server.send_broadcast({"text": {"text": "Izmerjena napetost OK! Izmerjeno {}V.\n" . format(voltage), "tag": "green"}})
                strips_tester.product[1].add_measurement(type(self).__name__, "VoltageMax", Task.TASK_OK, voltage)

        time.sleep(sleep)

        GPIO.output(gpios["VCC"], True)
        GPIO.output(gpios["SIDE"], True)


        return type(self).__name__



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


