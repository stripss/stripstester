import logging
import time
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import settings, server
from tester import Task
import cv2
from pylibdmtx.pylibdmtx import decode as decode_qr
import numpy as np

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
        # Turn signal LEDs off
        GPIO.output(gpios["LIGHT_GREEN"], True)
        GPIO.output(gpios["LIGHT_RED"], True)

    def run(self) -> (bool, str):
        if "START_SWITCH" in settings.gpios:
            server.send_broadcast({"text": {"text": "Za začetek testa zapri pokrov.\n", "tag": "black"}})

            while True:
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))

                if not state_GPIO_SWITCH:
                    # Turn working LED on

                    GPIO.output(gpios["LIGHT_GREEN"], False)
                    GPIO.output(gpios["LIGHT_RED"], False)

                    break

                time.sleep(0.1)

            # Make sure that all relays are opened before test
            self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
            self.relay_board.open_all_relays()
            self.relay_board.hid_device.close()
        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")
        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        pass




class ReadSerial(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "image_name" in definition['slug']:
                self.image_name = definition['value']

        # powering up board meanwhile
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        # IMPLEMENTIRAJ TRY METODO... kaj ce se kamera ne pricne??

        vc = cv2.VideoCapture(0)

        server.send_broadcast({"text": {"text": "Povezovanje s kamero...\n", "tag": "black"}})
        while not vc.isOpened():  # try to get the first frame
            vc = cv2.VideoCapture(0)
            time.sleep(0.5)

        GPIO.output(gpios["INTERIOR_LED"], False)

        rval, frame = vc.read()
        tim_start = time.clock()

        raw_scanned_string = ""

        num_of_tries = 5

        for i in range(num_of_tries):
            if not len(raw_scanned_string):
                #if not len(raw_scanned_string):
                rval, frame = vc.read()

                roi = frame[120:410, 120:440]
                #cv2.imwrite("/strips_tester_project/strips_tester/daaaa{}.jpg".format(self.image_name),roi)

                raw_scanned_string = decode_qr(roi)
            else:
                raw_scanned_string = raw_scanned_string[0].data.decode("utf-8")
                server.send_broadcast({"text": {"text": "Serijska številka: {}\n" . format(raw_scanned_string), "tag": "black"}})

                break

        vc.release()
        GPIO.output(gpios["INTERIOR_LED"], True)

        if not len(raw_scanned_string):
            server.send_broadcast({"text": {"text": "Ne morem prebrati serijske številke.\n", "tag": "red"}})
            return {"signal":[1, "fail", 5, "NA"]}

        # Save successfully read image
        cv2.imwrite("/strips_tester_project/strips_tester/{}.jpg".format(self.image_name),roi)

        # Assign scanned string to strips_tester class
        #raw_scanned_string = str(raw_scanned_string[0].data)[2:len(str(raw_scanned_string[0].data))-1]

        strips_tester.current_product.serial = raw_scanned_string

        return {"signal":[1, "ok", 5, "NA"]}


    def rotateImage(self,image, angle):
        image_center = tuple(np.array(image.shape[1::-1]) / 2)
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
        return result


    def tear_down(self):
        self.relay_board.hid_device.close()





class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.mesurement_delay = 0.16
        self.measurement_results = {}

        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "ref_12v" in definition['slug']:
                self.ref_12v = definition['value']

            if "reftol_12v" in definition['slug']:
                self.ref_12v_tolerance = definition['value']

            if "ref_3v3" in definition['slug']:
                self.ref_3v3 = definition['value']

            if "reftol_3v3" in definition['slug']:
                self.ref_3v3_tolerance = definition['value']

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.mesurement_delay)

        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):

        # Test 12V
        self.relay_board.close_relay(relays["12V"])
        voltage = self.voltmeter.read()  # Read voltage on 12v pin
        if not self.in_range(voltage, self.ref_12v - self.ref_12v_tolerance, self.ref_12v + self.ref_12v_tolerance):
            server.send_broadcast({"text": {"text": "Referenčna napetost 12V izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['12v'] = [voltage, "fail", 5, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Referenčna napetost 12V OK. Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['12v'] = [voltage, "ok", 5, "NA"]
        self.relay_board.open_relay(relays["12V"])

        time.sleep(0.2)

        GPIO.output(gpios["3V3"], False)
        voltage = self.voltmeter.read()  # Read voltage on 3v3 pin
        if not self.in_range(voltage, self.ref_3v3 - self.ref_3v3_tolerance, self.ref_3v3 + self.ref_3v3_tolerance):
            server.send_broadcast({"text": {"text": "Referenčna napetost 3.3V izven območja! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['3v3'] = [voltage, "fail", 5, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Referenčna napetost 3.3V OK. Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['3v3'] = [voltage, "ok", 5, "NA"]
        GPIO.output(gpios["3V3"], True)


        return self.measurement_results

    def in_range(self, value, min, max):

        if min < value and value < max:
            return True
        else:
            return False

    def tear_down(self):
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
                        self.measurement_results['current_left_blue'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na modri levi LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_left_blue'] = [current, "ok", 2, "NA"]
                elif ii == 3: # Blue right LED test
                    if not self.in_range(current, self.blue_max_current - self.current_tolerance, self.blue_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na modri desni LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_right_blue'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na modri desni LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_right_blue'] = [current, "ok", 2, "NA"]
                elif ii == 1: # Green left LED test
                    if not self.in_range(current, self.green_max_current - self.current_tolerance, self.green_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na zeleni levi LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_left_green'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na zeleni levi LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_left_green'] = [current, "ok", 2, "NA"]
                elif ii == 4: # Green right LED test
                    if not self.in_range(current, self.green_max_current - self.current_tolerance, self.green_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na zeleni desni LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_right_green'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na zeleni desni LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_right_green'] = [current, "ok", 2, "NA"]
                elif ii == 2: # Red left LED test
                    if not self.in_range(current, self.red_max_current - self.current_tolerance, self.red_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na rdeči levi LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_left_red'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na rdeči levi LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_left_red'] = [current, "ok", 2, "NA"]
                elif ii == 5: # Red right LED test
                    if not self.in_range(current, self.red_max_current - self.current_tolerance, self.red_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na rdeči desni LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_right_red'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na rdeči desni LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_right_red'] = [current, "ok", 2, "NA"]
                elif ii == 6: # White LED test
                    if not self.in_range(current, self.white_max_current - self.current_tolerance, self.white_max_current + self.current_tolerance):
                        server.send_broadcast({"text": {"text": "Tok neustrezen na beli LED! Izmerjeno {}mA.\n".format(current), "tag": "red"}})
                        self.measurement_results['current_white'] = [current, "fail", 2, "NA"]
                    else:
                        server.send_broadcast({"text": {"text": "Izmerjen tok na beli LED OK! Izmerjeno {}mA.\n".format(current), "tag": "green"}})
                        self.measurement_results['current_white'] = [current, "ok", 2, "NA"]
                self.i2c.manual_off()

            self.relay_board.close_relay(relays["Heater"])
            voltage = self.voltmeter.read() # Read voltage on Heater pin

            if not self.in_range(voltage, 11,13):
                server.send_broadcast({"text": {"text": "Grelec OFF ne deluje! Napetost izven toleranc! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
                self.measurement_results['heater_off'] = [voltage, "fail", 2, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Grelec OFF OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
                self.measurement_results['heater_off'] = [voltage, "ok", 2, "NA"]

            self.i2c.turn_heater_on()
            voltage = self.voltmeter.read() # Read voltage on Heater pin

            if not self.in_range(voltage, -1,1):
                server.send_broadcast({"text": {"text": "Grelec ON ne deluje! Napetost izven toleranc! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
                self.measurement_results['heater_on'] = [voltage, "fail", 2, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Grelec ON OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
                self.measurement_results['heater_on'] = [voltage, "ok", 2, "NA"]

            self.i2c.turn_heater_off()

            self.relay_board.open_relay(relays["Heater"])

        except Exception as err:
            server.send_broadcast({"text": {"text": "Napaka pri I2C komunikaciji.\n", "tag": "red"}})

        try:
            server.send_broadcast({"text": {"text": "Testiranje LM25 merilnika temperature...\n", "tag": "black"}})

            temperature = self.temp_sensor.read()

            if not self.in_range(temperature, self.temp - self.temp_tolerance,self.temp + self.temp_tolerance):
                server.send_broadcast({"text": {"text": "Temperatura izven območja! Izmerjeno {}°C.\n".format(temperature), "tag": "red"}})
                self.measurement_results['temperature'] = [temperature, "fail", 2, "NA"]
            else:
                server.send_broadcast({"text": {"text": "Temperatura OK! Izmerjeno {} °C.\n".format(temperature), "tag": "green"}})
                self.measurement_results['temperature'] = [temperature, "ok", 2, "NA"]



        except Exception as err:
            server.send_broadcast({"text": {"text": "Napaka pri I2C komunikaciji.\n", "tag": "red"}})

        return self.measurement_results

    def in_range(self, value, min, max):

        if min < value and value < max:
            return True
        else:
            return False

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()
        self.ampermeter.close()






class LockSimulator(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):

        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", 0.16)

        self.relay_board.close_relay(relays["Power"])

        # Test 12V
        self.relay_board.close_relay(relays["12V"])
        voltage_12v = self.voltmeter.read()  # Read voltage on 12v pin
        self.relay_board.open_relay(relays["12V"])
        time.sleep(0.5)

        self.relay_board.close_relay(relays["Vcc1"])
        volt1 = self.voltmeter.read()

        while(volt1 < voltage_12v - 0.5):
            time.sleep(0.2)
            volt1 = self.voltmeter.read()
            server.send_broadcast({"text": {"text": "Vcc1: {}V od {}V\n".format(volt1,voltage_12v), "tag": "black"}})

        self.relay_board.open_relay(relays["Vcc1"])

        # guearantee that modul is charged

    def measure_left_side(self):

        # LEFT SIDE
        self.relay_board.open_relay(relays["IN_relay_1"])
        self.relay_board.open_relay(relays["IN_relay_2"])

        GPIO.output(gpios["OUT_relay_3"], True)
        #self.relay_board.close_relay(relays["OUT_relay_3"]) # to measure left output
        self.relay_board.open_relay(relays["OUT_relay_2"])

        # IZMERI OUT1+
        GPIO.output(gpios["OUT_relay_4"], False)
        #self.relay_board.close_relay(relays["OUT_relay_4"])
        volt_plus = self.voltmeter.read()

        # IZMERI OUT1-
        self.relay_board.close_relay(relays["OUT_relay_2"])
        volt_minus = self.voltmeter.read()

        #self.relay_board.open_relay(relays["OUT_relay_4"])
        #self.relay_board.open_relay(relays["OUT_relay_3"])

        GPIO.output(gpios["OUT_relay_3"], True)
        GPIO.output(gpios["OUT_relay_4"], True)
        self.relay_board.open_relay(relays["OUT_relay_2"])

        voltage = volt_plus - volt_minus
        return voltage

    def measure_right_side(self):
        # Right input side
        self.relay_board.close_relay(relays["IN_relay_1"])
        self.relay_board.close_relay(relays["IN_relay_2"])

        GPIO.output(gpios["OUT_relay_3"], False)
        #self.relay_board.open_relay(relays["OUT_relay_3"]) # to measure right output
        self.relay_board.open_relay(relays["OUT_relay_1"])

        # IZMERI OUT2+
        GPIO.output(gpios["OUT_relay_4"], False)
        #self.relay_board.close_relay(relays["OUT_relay_4"])

        volt_plus = self.voltmeter.read()

        # IZMERI OUT2-
        self.relay_board.close_relay(relays["OUT_relay_1"])
        volt_minus = self.voltmeter.read()

        #self.relay_board.open_relay(relays["OUT_relay_4"])
        GPIO.output(gpios["OUT_relay_3"], True)
        GPIO.output(gpios["OUT_relay_4"], True)

        voltage = volt_plus - volt_minus
        return voltage

    def unlock(self):
        self.relay_board.open_relay(relays["Inv_relay_2"])
        #time.sleep(0.2)
        self.relay_board.close_relay(relays["Inv_relay_1"])


    def lock(self):
        self.relay_board.open_relay(relays["Inv_relay_1"])
        #time.sleep(0.2)
        self.relay_board.close_relay(relays["Inv_relay_2"])


    def run(self):

        server.send_broadcast({"text": {"text": "Odklep pri napajanju...\n", "tag": "black"}})

        self.unlock()
        leftunlock1 = self.measure_left_side()
        server.send_broadcast({"text": {"text": "Leva stran {}V\n" . format(leftunlock1), "tag": "black"}})

        #print("Left side: {}V".format(leftunlock1))
        rightunlock1 = self.measure_right_side()
        server.send_broadcast({"text": {"text": "Desna stran {}V\n" . format(rightunlock1), "tag": "black"}})
        #print("Right side: {}V".format(rightunlock1))

        server.send_broadcast({"text": {"text": "Zaklep pri napajanju...\n", "tag": "black"}})
        #print("LOCK POWER ON")
        self.lock()

        leftlock1 = self.measure_left_side()
        #print("Left side: {}V".format(leftlock1))
        server.send_broadcast({"text": {"text": "Leva stran {}V\n" . format(leftlock1), "tag": "black"}})
        rightlock1 = self.measure_right_side()
        #print("Right side: {}V".format(rightlock1))
        server.send_broadcast({"text": {"text": "Desna stran {}V\n" . format(rightlock1), "tag": "black"}})


        # Izklopi napajanje
        self.relay_board.open_relay(relays["Power"])
        time.sleep(0.2)

        server.send_broadcast({"text": {"text": "Zaklep brez napajanja...\n", "tag": "black"}})
        leftlock0 = self.measure_left_side()
        server.send_broadcast({"text": {"text": "Leva stran {}V\n" . format(leftlock0), "tag": "black"}})
        #print("Left side: {}V".format(leftlock0))
        rightlock0 = self.measure_right_side()
        server.send_broadcast({"text": {"text": "Desna stran {}V\n" . format(rightlock0), "tag": "black"}})
        #print("Right side: {}V".format(rightlock0))

        server.send_broadcast({"text": {"text": "Odklep brez napajanja...\n", "tag": "black"}})
        self.unlock()

        leftunlock0 = self.measure_left_side()
        #print("Left side: {}V".format(leftunlock0))
        server.send_broadcast({"text": {"text": "Leva stran {}V\n" . format(leftunlock0), "tag": "black"}})
        rightunlock0 = self.measure_right_side()
        server.send_broadcast({"text": {"text": "Desna stran {}V\n" . format(rightunlock0), "tag": "black"}})
        #print("Right side: {}V".format(rightunlock0))


        return self.measurement_results

    def tear_down(self):
        self.relay_board.open_all_relays()
        self.relay_board.hid_device.close()
        self.voltmeter.close()







class PowerOffTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.measurement_delay = 0.16
        self.measurement_results = {}

        # custom variable init
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if "green_led_voltage" in definition['slug']:
                self.green_led_voltage = definition['value']

            if "green_led_tolerance" in definition['slug']:
                self.green_led_volt_tolerance = definition['value']

            if "red_led_voltage" in definition['slug']:
                self.red_led_voltage = definition['value']

            if "red_led_tolerance" in definition['slug']:
                self.red_led_volt_tolerance = definition['value']

            if "time_before_check" in definition['slug']:
                self.time_before_check = definition['value']

            if "voltage_check" in definition['slug']:
                self.voltage_check = definition['value']

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A0917.voltage1", self.measurement_delay)
        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["Power"])

    def run(self):
        # Assume that module is already charged
        #self.relay_board.close_relay(relays["Power"])
        #time.sleep(10)

        self.relay_board.close_relay(relays["LED_green_right"])
        voltage = self.voltmeter.read()

        overtime = 0
        old_voltage = voltage
        while not self.in_range(voltage, self.green_led_voltage - self.green_led_volt_tolerance, self.green_led_voltage + self.green_led_volt_tolerance):
            voltage = self.voltmeter.read()

            overtime += 1
            if old_voltage > voltage: # PCB is discharging
                overtime = 20

            time.sleep(1)

        if overtime > 10: # if LED voltage is not nominal
            server.send_broadcast({"text": {"text": "Desna zelena LED ne deluje! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['voltage_right_green'] = [voltage, "fail", 2, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Desna zelena LED OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['voltage_right_green'] = [voltage, "ok", 2, "NA"]

        self.relay_board.open_relay(relays["LED_green_right"])
        time.sleep(0.2)

        self.relay_board.close_relay(relays["LED_green_left"])
        voltage = self.voltmeter.read()

        while not self.in_range(voltage, self.green_led_voltage - self.green_led_volt_tolerance, self.green_led_voltage + self.green_led_volt_tolerance):
            voltage = self.voltmeter.read()

            overtime += 1

            time.sleep(1)

        if overtime > 10:
            server.send_broadcast({"text": {"text": "Leva zelena LED ne deluje! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['voltage_left_green'] = [voltage, "fail", 2, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Leva zelena LED OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['voltage_left_green'] = [voltage, "ok", 2, "NA"]

        self.relay_board.open_relay(relays["LED_green_left"])

        # Disable power
        self.relay_board.open_relay(relays["Power"])





        self.relay_board.close_relay(relays["LED_red_right"])
        voltage = self.voltmeter.read()

        while not self.in_range(voltage, self.red_led_voltage - self.red_led_volt_tolerance, self.red_led_voltage + self.red_led_volt_tolerance):
            voltage = self.voltmeter.read()

            server.send_broadcast({"text": {"text": "Desna rdeča LED ne deluje! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['voltage_right_red'] = [voltage, "fail", 2, "NA"]

            time.sleep(1)
        else:
            server.send_broadcast({"text": {"text": "Desna rdeča LED OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['voltage_right_red'] = [voltage, "ok", 2, "NA"]

        self.relay_board.open_relay(relays["LED_red_right"])
        time.sleep(0.2)

        self.relay_board.close_relay(relays["LED_red_left"])
        voltage = self.voltmeter.read()
        if not self.in_range(voltage, self.red_led_voltage - self.red_led_volt_tolerance, self.red_led_voltage + self.red_led_volt_tolerance):
            server.send_broadcast({"text": {"text": "Leva rdeča LED ne deluje! Izmerjeno {}V.\n".format(voltage), "tag": "red"}})
            self.measurement_results['voltage_left_red'] = [voltage, "fail", 2, "NA"]
        else:
            server.send_broadcast({"text": {"text": "Leva rdeča LED OK! Izmerjeno {}V.\n".format(voltage), "tag": "green"}})
            self.measurement_results['voltage_left_red'] = [voltage, "ok", 2, "NA"]

        self.relay_board.open_relay(relays["LED_red_left"])


        time.sleep(self.time_before_check)

        # Safety PELV (lock stays locked until volt1 and volt2 are below threshold)

        volt1 = 999.0
        volt2 = 999.0
        server.send_broadcast({"text": {"text": "PELV initialized...\n", "tag": "blue"}})

        while(volt1 > self.voltage_check):
            self.relay_board.close_relay(relays["Vcc1"])
            time.sleep(0.2)
            server.send_broadcast({"text": {"text": "Vcc1: {}V\n".format(volt1), "tag": "black"}})
            volt1 = self.voltmeter.read()

        self.relay_board.open_relay(relays["Vcc1"])

        while(volt2 > self.voltage_check):
            self.relay_board.close_relay(relays["Vcc2"])
            time.sleep(0.2)
            server.send_broadcast({"text": {"text": "Vcc2: {}V\n".format(volt2), "tag": "black"}})
            volt2 = self.voltmeter.read()

        self.relay_board.open_relay(relays["Vcc2"])

        # Open lock
        #GPIO.output(gpios["LOCK"], G_LOW)



        return self.measurement_results

    def in_range(self, value, min, max):

        if min < value and value < max:
            return True
        else:
            return False

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()









class FinishProcedureTask(Task):
    # Signal LED and buzzer

    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        pass

    def run(self):
        strips_tester.current_product.test_status = all(strips_tester.current_product.task_results) and len(strips_tester.current_product.task_results)
        if strips_tester.current_product.test_status:
            GPIO.output(gpios["LIGHT_GREEN"], False)
            GPIO.output(gpios["LIGHT_RED"], True)
        else:
            GPIO.output(gpios["LIGHT_GREEN"], True)
            GPIO.output(gpios["LIGHT_RED"], False)

        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        server.afterlock = 10
        pass