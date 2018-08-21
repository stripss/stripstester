import logging
import time
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import settings, server
from tester import Task
import cv2

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
        # Make sure that all relays are opened before test
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.open_all_relays()

    def run(self) -> (bool, str):
        if "START_SWITCH" in settings.gpios:
            server.send_broadcast({"text": {"text": "Za začetek testa zapri pokrov.", "tag": "black"}})

            while True:
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))

                if state_GPIO_SWITCH:
                    break

                time.sleep(0.1)
        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")
        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        self.relay_board.hid_device.close()






class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.mesurement_delay = 0.16
        self.measurement_results = {}
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.mesurement_delay)

        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):

        # Test 12V
        self.relay_board.close_relay(relays["12V"])
        time.sleep(0.2)
        voltage = self.voltmeter.read()  # Read voltage on 12v pin
        if not self.in_range(voltage, 11,13):
            server.send_broadcast({"text": {"text": "Referenčna napetost 12V izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['12v'] = [voltage, "fail", 5, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Referenčna napetost 12V OK. Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['12v'] = [voltage, "ok", 5, "NA"]
        self.relay_board.open_relay(relays["12V"])

        time.sleep(0.2)

        '''
        GPIO.output(gpios["3V3"], False)
        time.sleep(0.2)
        voltage = self.voltmeter.read()  # Read voltage on 3v3 pin
        if not self.in_range(voltage, 11,13):
            server.send_broadcast({"text": {"text": "Referenčna napetost 3.3V izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['3v3'] = [voltage, "fail", 5, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Referenčna napetost 3.3V OK. Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['3v3'] = [voltage, "ok", 5, "NA"]
        GPIO.output(gpios["3V3"], True)
        '''

        return self.measurement_results

    def in_range(self, value, min, max):

        if min < value and value < max:
            return True
        else:
            return False

    def tear_down(self):
        self.relay_board.open_relay(relays["Power"])
        self.relay_board.hid_device.close()
        self.voltmeter.close()






class I2C_Communication(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.measurement_delay = 0.16
        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.measurement_delay)
        self.ampermeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", self.measurement_delay)
        self.temp_sensor = devices.LM75A(0)
        self.i2c = devices.MCP23017()

        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "blue_max_current" in definition['slug']:
                self.blue_max_current = definition['value']

            if "green_max_current" in definition['slug']:
                self.green_max_current = definition['value']

            if "red_max_current" in definition['slug']:
                self.red_max_current = definition['value']

            if "white_max_current" in definition['slug']:
                self.white_max_current = definition['value']

            if "tolerance" in definition['slug']:
                self.current_tolerance = definition['value']

            if "temperature" in definition['slug']:
                self.temp = definition['value']

            if "temp_tolerance" in definition['slug']:
                self.temp_tolerance = definition['value']


        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])

    def run(self):
        try:
            server.send_broadcast({"text": {"text": "Testiranje komunikacije z MCP23017...\n", "tag": "black"}})

            for ii in range(7):

                # LED ORDER:
                # 0,3 = modra
                # 1,4 = zelena
                # 2,5 = rdeca
                # 6 = bela
                # 7 heater

                self.i2c.test_one_led(ii)

                resistor = 1.0
                current = (self.ampermeter.read() / resistor) * 1000.0

                if ii == 0: # Blue left LED test
                    if not self.in_range(current, self.blue_max_current - self.current_tolerance, self.blue_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na modri levi LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_left_blue'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na modri levi LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_left_blue'] = [current, "ok", 5, "NA"]
                elif ii == 3: # Blue right LED test
                    if not self.in_range(current, self.blue_max_current - self.current_tolerance, self.blue_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na modri desni LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_right_blue'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na modri desni LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_right_blue'] = [current, "ok", 5, "NA"]
                elif ii == 1: # Green left LED test
                    if not self.in_range(current, self.green_max_current - self.current_tolerance, self.green_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na zeleni levi LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_left_green'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na zeleni levi LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_left_green'] = [current, "ok", 5, "NA"]
                elif ii == 4: # Green right LED test
                    if not self.in_range(current, self.green_max_current - self.current_tolerance, self.green_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na zeleni desni LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_right_green'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na zeleni desni LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_right_green'] = [current, "ok", 5, "NA"]
                elif ii == 2: # Red left LED test
                    if not self.in_range(current, self.red_max_current - self.current_tolerance, self.red_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na rdeči levi LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_left_red'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na rdeči levi LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_left_red'] = [current, "ok", 5, "NA"]
                elif ii == 5: # Red right LED test
                    if not self.in_range(current, self.red_max_current - self.current_tolerance, self.red_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na rdeči desni LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_right_red'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na rdeči desni LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_right_red'] = [current, "ok", 5, "NA"]
                elif ii == 6: # White LED test
                    if not self.in_range(current, self.white_max_current - self.current_tolerance, self.white_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na beli LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_white'] = [current, "fail", 5, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na beli LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_white'] = [current, "ok", 5, "NA"]
                self.i2c.manual_off()

            self.relay_board.close_relay(relays["Heater"])
            voltage = self.voltmeter.read() # Read voltage on Heater pin

            if not self.in_range(voltage, 11,13):
                server.send_broadcast({"text": {"text": "Grelec OFF ne deluje! Napetost izven toleranc! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
                self.measurement_results['heater_off'] = [voltage, "fail", 5, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Grelec OFF OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
                self.measurement_results['heater_off'] = [voltage, "ok", 5, "NA"]

            self.i2c.turn_heater_on()
            voltage = self.voltmeter.read() # Read voltage on Heater pin

            if not self.in_range(voltage, -1,1):
                server.send_broadcast({"text": {"text": "Grelec ON ne deluje! Napetost izven toleranc! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
                self.measurement_results['heater_on'] = [voltage, "fail", 5, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Grelec ON OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
                self.measurement_results['heater_on'] = [voltage, "ok", 5, "NA"]

            self.i2c.turn_heater_off()

            self.relay_board.open_relay(relays["Heater"])

        except Exception as err:
            server.send_broadcast({"text": {"text": "Napaka pri I2C komunikaciji.\n", "tag": "red"}})

        try:
            server.send_broadcast({"text": {"text": "Testiranje LM25 merilnika temperature...\n", "tag": "black"}})

            temperature = self.temp_sensor.read()

            if not self.in_range(temperature, self.temp - self.temp_tolerance,self.temp + self.temp_tolerance):
                server.send_broadcast({"text": {"text": "Temperatura izven območja! Izmerjeno {}°C.\n".format(temperature), "tag": "red"}})
                self.measurement_results['temperature'] = [temperature, "fail", 5, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Temperatura OK! Izmerjeno {} °C.\n".format(temperature), "tag": "green"}})
                self.measurement_results['temperature'] = [temperature, "ok", 5, "NA"]



        except Exception as err:
            server.send_broadcast({"text": {"text": "Napaka pri I2C komunikaciji.\n", "tag": "red"}})


        return self.measurement_results

    def in_range(self, value, min, max):

        if min < value and value < max:
            return True
        else:
            return False

    def tear_down(self):
        self.relay_board.open_relay(relays["Power"])
        self.relay_board.hid_device.close()
        self.voltmeter.close()
        self.ampermeter.close()
