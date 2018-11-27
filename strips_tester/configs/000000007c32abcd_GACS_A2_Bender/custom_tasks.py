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


# DONE
class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        time.sleep(self.get_definition("start_time"))

        # Make sure that all relays are opened before test
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
        self.relay_board.open_all_relays()

        while not self.is_lid_closed():
            time.sleep(0.1)

        # Lock test device
        #GPIO.output(gpios['LOCK'], False)

        for i in range(3):
            time.sleep(0.1)
            GPIO.output(gpios['BUZZER'],True)
            time.sleep(0.1)
            GPIO.output(gpios['BUZZER'],False)

        # Working lights on
        GPIO.output(gpios['LIGHT_GREEN'],True)
        GPIO.output(gpios['LIGHT_RED'],True)
        GPIO.output(gpios['LOCK'],True) # Lock test device

    def run(self) -> (bool, str):
        # Product detection
        detect = GPIO.input(strips_tester.settings.gpios.get("DETECT_PRODUCT"))

        if not detect:
            strips_tester.product[0].exist = True
            server.send_broadcast({"text": {"text": "Zaznan kos.\n", "tag": "black"}})
        else:
            server.send_broadcast({"text": {"text": "Ni zaznanega kosa v ležišču.\n", "tag": "black"}})
            raise Exception("No products found in nests.")

        return type(self).__name__


    def tear_down(self):
        # Open all relays
        self.relay_board.hid_device.close()

        time.sleep(self.get_definition("end_time"))

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

class EndProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        pass

    def run(self) -> (bool, str):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
        self.relay_board.open_all_relays()
        self.relay_board.hid_device.close()

        GPIO.output(gpios["Discharge1"], True)
        GPIO.output(gpios["Discharge2"], True)

        server.send_broadcast({"text": {"text": "Odprite pokrov in odstranite testirane kose.\n", "tag": "black"}})
        GPIO.output(gpios['LOCK'],False)

        GPIO.output(gpios['LIGHT_GREEN'],False)
        GPIO.output(gpios['LIGHT_RED'],False)

        while self.is_lid_closed():
            GPIO.output(gpios['LIGHT_GREEN'], True)
            GPIO.output(gpios['LIGHT_RED'], True)
            time.sleep(0.2)
            GPIO.output(gpios['LIGHT_GREEN'], False)
            GPIO.output(gpios['LIGHT_RED'], False)
            time.sleep(0.2)

        beep = False
        if strips_tester.product[0].exist:
            if strips_tester.product[0].ok: # Product is bad
                beep = True
                GPIO.output(gpios['LIGHT_RED'], True)
            else:
                GPIO.output(gpios['LIGHT_GREEN'], True)
        else:
            beep = True

        if beep:
            GPIO.output(gpios['BUZZER'], True)
            time.sleep(1)
            GPIO.output(gpios['BUZZER'], False)

        GPIO.output(gpios['LOCK'],True)

        return type(self).__name__

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def tear_down(self):
        #GPIO.output(gpios['LOCK'],True)
        #server.afterlock = 10
        pass




class ReadSerial(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # Powering up board meanwhile
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        # IMPLEMENTIRAJ TRY METODO... kaj ce se kamera ne pricne??

        self.vc = cv2.VideoCapture('/dev/logitech')
        while not self.vc.isOpened():  # try to get the first frame of camera
            self.vc = cv2.VideoCapture('/dev/logitech')
            server.send_broadcast({"text": {"text": "Odpiranje kamere...\n", "tag": "black"}})
            time.sleep(1)

        GPIO.output(gpios["INTERIOR_LED"], False)

        # First picture is corrupted, so we leave it here.
        rval, frame = self.vc.read()
        tim_start = time.clock()

        raw_scanned_string = ""

        num_of_tries = 5

        for i in range(num_of_tries):
            if not len(raw_scanned_string):
                #if not len(raw_scanned_string):
                rval, frame = self.vc.read()

                # Dimensions of cropped image for QR code
                x = 120
                y = 120
                h = 300
                w = 350

                roi = frame[y:y+h, x:x+w]

                raw_scanned_string = decode_qr(roi)
            else:
                raw_scanned_string = raw_scanned_string[0].data.decode("utf-8")
                server.send_broadcast({"text": {"text": "Serijska številka: {}\n" . format(raw_scanned_string), "tag": "black"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "Decode", Task.TASK_OK, num_of_tries)
                break

        self.vc.release()
        GPIO.output(gpios["INTERIOR_LED"], True)

        if not len(raw_scanned_string):
            strips_tester.product[0].add_measurement(type(self).__name__, "Decode", Task.TASK_WARNING, num_of_tries)
            server.send_broadcast({"text": {"text": "Serijske številke ni mogoče prebrati.\n", "tag": "red"}})

        # Save successfully read image
        cv2.imwrite("/strips_tester_project/strips_tester/{}.jpg".format(self.get_definition("image_name")),roi)

        strips_tester.product[0].serial = raw_scanned_string

        return type(self).__name__


    def rotateImage(self,image, angle):
        image_center = tuple(np.array(image.shape[1::-1]) / 2)
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
        return result

    def tear_down(self):
        GPIO.output(gpios["INTERIOR_LED"], True)
        self.relay_board.hid_device.close()




class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1",0.16)

        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):

        # Test 12V
        self.relay_board.close_relay(relays["12V"])
        voltage = self.voltmeter.read()  # Read voltage on 12v pin
        if not self.in_range(voltage, "ref_12v", "reftol_12v"):
            strips_tester.product[0].add_measurement(type(self).__name__, "12V", Task.TASK_WARNING, voltage)
            server.send_broadcast({"text": {"text": "Meritev napetosti 12V: {}V\n".format(voltage), "tag": "red"}})
        else:
            strips_tester.product[0].add_measurement(type(self).__name__, "12V", Task.TASK_OK, voltage)
            server.send_broadcast({"text": {"text": "Meritev napetosti 12V: {}V\n".format(voltage), "tag": "green"}})
        self.relay_board.open_relay(relays["12V"])

        time.sleep(0.1)

        # Test 3V3
        self.relay_board.close_relay(relays["3V3"])
        voltage = self.voltmeter.read()  # Read voltage on 3v3 pin
        if not self.in_range(voltage, "ref_3v3", "reftol_3v3"):
            strips_tester.product[0].add_measurement(type(self).__name__, "3.3V", Task.TASK_WARNING, voltage)
            server.send_broadcast({"text": {"text": "Meritev napetosti 3.3V: {}V\n".format(voltage), "tag": "red"}})
        else:
            strips_tester.product[0].add_measurement(type(self).__name__, "3.3V", Task.TASK_OK, voltage)
            server.send_broadcast({"text": {"text": "Meritev napetosti 3.3V: {}V\n".format(voltage), "tag": "green"}})
        self.relay_board.open_relay(relays["3V3"])

        return type(self).__name__

    def in_range(self, value, definition, tolerance):
        expected = self.get_definition(definition)
        if self.is_unit_percent(self.get_definition_unit(tolerance)):
            #print("in_range: {} is in percent" . format(tolerance))
            tolerance_min = expected - expected * (self.get_definition(tolerance) / 100.0)
            tolerance_max = expected + expected * (self.get_definition(tolerance) / 100.0)
        else:
            #print("in_range: {} is not percent" . format(tolerance))
            tolerance_min = expected - self.get_definition(tolerance)
            tolerance_max = expected + self.get_definition(tolerance)

        if value > tolerance_min and value < tolerance_max:
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
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)

        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

        # Measure order: lednum,color_I_def,toleranca_I_def,
        self.measure_order = [
            (0, "blue", " left"),
            (1, "green", " left"),
            (2, "red", " left"),
            (3, "blue", " right"),
            (4, "green", " right"),
            (5, "red", " right"),
            (6, "white", "")
        ]

        self.relay_board.close_relay(relays["Power"])

    def run(self):
        # Set voltmeter as ampermeter for this test
        self.relay_board.close_relay(relays["Yocto_plus"])
        self.relay_board.close_relay(relays["Yocto_minus"])

        try:
            self.i2c = devices.MCP23017()  # IO Expander initialisation

            for i in range(len(self.measure_order)):
                self.i2c.test_one_led(self.measure_order[i][0])
                current = (self.voltmeter.read() / self.get_definition("shunt")) * 1000.0

                if not self.in_range(current, self.measure_order[i][1] + "_current","current_tolerance"):
                    server.send_broadcast({"text": {"text": "Meritev toka '{}{}' LED: {}mA\n".format(self.measure_order[i][1],self.measure_order[i][2],current), "tag": "red"}})
                    strips_tester.product[0].add_measurement(type(self).__name__, "{}{}" . format(self.measure_order[i][1],self.measure_order[i][2]), Task.TASK_WARNING, current)
                else:
                    server.send_broadcast({"text": {"text": "Meritev toka '{}{}' LED: {}mA\n".format(self.measure_order[i][1],self.measure_order[i][2],current), "tag": "green"}})
                    strips_tester.product[0].add_measurement(type(self).__name__, "{}{}" . format(self.measure_order[i][1],self.measure_order[i][2]), Task.TASK_OK, current)
                self.i2c.manual_off()

            self.relay_board.open_relay(relays["Yocto_plus"])
            self.relay_board.open_relay(relays["Yocto_minus"])


            self.relay_board.close_relay(relays["Heater"])

            voltage = self.voltmeter.read()  # Read voltage on Heater pin

            if not self.in_range(voltage, "heater_off_voltage", "heater_tolerance"):
                server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "red"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "HeaterOFF", Task.TASK_WARNING, voltage)
            else:
                server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "green"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "HeaterOFF", Task.TASK_OK, voltage)

            self.i2c.turn_heater_on()
            voltage = self.voltmeter.read()  # Read voltage on Heater pin

            if not self.in_range(voltage, "heater_on_voltage", "heater_tolerance"):
                server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "red"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "HeaterON", Task.TASK_WARNING, voltage)
            else:
                server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "green"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "HeaterON", Task.TASK_OK, voltage)

            self.i2c.manual_off()

            self.relay_board.open_relay(relays["Heater"])
        except OSError:
            server.send_broadcast({"text": {"text": "Napaka branja iz IO ekspanderja MCP23017.\n", "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "MCP23017", Task.TASK_WARNING, "Sensor not found.")

        try:
            self.temp_sensor = devices.LM75A()  # Temperature sensor initialisation

            temperature = self.temp_sensor.read()

            if not self.in_range(temperature, "temperature", "temp_tolerance"):
                server.send_broadcast({"text": {"text": "Meritev temperature: {}°C\n".format(temperature), "tag": "red"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "Temperature", Task.TASK_WARNING, temperature)
            else:
                server.send_broadcast({"text": {"text": "Meritev temperature: {}°C\n".format(temperature), "tag": "green"}})
                strips_tester.product[0].add_measurement(type(self).__name__, "Temperature", Task.TASK_OK, temperature)

        except OSError:
            server.send_broadcast({"text": {"text": "Napaka branja iz senzorja LM75A.\n", "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LM75A", Task.TASK_WARNING, "Sensor not found.")

        return type(self).__name__

    def in_range(self, value, definition, tolerance):
        expected = self.get_definition(definition)
        if self.is_unit_percent(self.get_definition_unit(tolerance)):
            #print("in_range: {} is in percent" . format(tolerance))
            tolerance_min = expected - expected * (self.get_definition(tolerance) / 100.0)
            tolerance_max = expected + expected * (self.get_definition(tolerance) / 100.0)
        else:
            #print("in_range: {} is not percent" . format(tolerance))
            tolerance_min = expected - self.get_definition(tolerance)
            tolerance_max = expected + self.get_definition(tolerance)

        if value > tolerance_min and value < tolerance_max:
            return True
        else:
            return False

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()





class LockSimulator(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

        self.relay_board.close_relay(relays["Power"])

    def run(self):
        '''
        self.relay_board.close_relay(relays["Vcc1"])
        voltage = self.voltmeter.read()

        while voltage < 11.78:
            voltage = self.voltmeter.read()
            server.send_broadcast({"text": {"text": "Dvigovanje desne napetosti: {}V\n".format(voltage), "tag": "black"}})

            time.sleep(0.5)

        self.relay_board.open_relay(relays["Vcc1"])
        time.sleep(0.05)
        self.relay_board.close_relay(relays["Vcc2"])
        voltage = self.voltmeter.read()

        while voltage < 11.78:
            voltage = self.voltmeter.read()
            server.send_broadcast({"text": {"text": "Dvigovanje leve napetosti: {}V\n".format(voltage), "tag": "black"}})
            time.sleep(0.5)

        self.relay_board.open_relay(relays["Vcc2"])
        '''

        server.send_broadcast({"text": {"text": "Polnenje modula...\n", "tag": "black"}})
        time.sleep(self.get_definition('charging_time'))

        self.set_input(1,0) # Unlock left
        self.set_input(2,0) # Unlock right

        voltage = self.measure_output(2) # Measure left output

        if voltage <= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutUnlockPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutUnlockPower", Task.TASK_OK, voltage)

        voltage = self.measure_output(1)  # Measure right output

        if voltage <= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutUnlockPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutUnlockPower", Task.TASK_OK, voltage)

        self.set_input(1, 1)  # Lock left
        self.set_input(2, 1)  # Lock right

        voltage = self.measure_output(2)  # Measure left output

        if voltage >= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutLockPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutLockPower", Task.TASK_OK, voltage)

        voltage = self.measure_output(1)  # Measure right output

        if voltage >= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutLockPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutLockPower", Task.TASK_OK, voltage)


        # Take away power
        self.relay_board.open_relay(relays["Power"])
        time.sleep(0.5)

        voltage = self.measure_output(2)  # Measure left output

        if voltage >= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutLockNoPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutLockNoPower", Task.TASK_OK, voltage)

        voltage = self.measure_output(1)  # Measure left output

        if voltage >= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutLockNoPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutLockNoPower", Task.TASK_OK, voltage)

        self.set_input(1,0) # Unlock left
        self.set_input(2,0) # Unlock right

        voltage = self.measure_output(2) # Measure left output

        if voltage <= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutUnlockNoPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "LeftOutUnlockNoPower", Task.TASK_OK, voltage)

        voltage = self.measure_output(1) # Measure left output
    
        if voltage <= 0:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutUnlockNoPower", Task.TASK_WARNING, voltage)
        else:
            server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            strips_tester.product[0].add_measurement(type(self).__name__, "RightOutUnlockNoPower", Task.TASK_OK, voltage)

        self.set_input(1,-1)  # Disable left input
        self.set_input(2,-1)  # Disable right input

        return type(self).__name__

    def set_input(self,side,state):
        # State:
        # 0 - Unlocked
        # 1 - Locked

        if state != -1:
            GPIO.output(gpios["In{}+" . format(side)], state)
            GPIO.output(gpios["In{}-" . format(side)], not state)
        else:
            GPIO.output(gpios["In{}+" . format(side)], True)
            GPIO.output(gpios["In{}-" . format(side)], True)

    def measure_output(self,side):
        self.relay_board.close_relay(relays["Out{}+" . format(side)])
        time.sleep(0.1)
        voltage_plus = self.voltmeter.read()
        self.relay_board.open_relay(relays["Out{}+" . format(side)])

        time.sleep(0.1)

        self.relay_board.close_relay(relays["Out{}-" . format(side)])
        time.sleep(0.1)
        voltage_minus = self.voltmeter.read()
        self.relay_board.open_relay(relays["Out{}-" . format(side)])

        voltage = voltage_minus - voltage_plus

        return voltage

    def tear_down(self):
        self.relay_board.open_all_relays()
        self.relay_board.hid_device.close()
        self.voltmeter.close()



class VisualTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # custom variable init

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)
        self.camera = cv2.VideoCapture('/dev/microsoft')  # video capture source camera

        while not self.camera.isOpened():  # try to get the first frame of camera
            self.camera = cv2.VideoCapture('/dev/microsoft')
            time.sleep(0.1)

        # First picture is corrupted, so we leave it here.
        rval, frame = self.camera.read()

        self.led = []
        for i in range(4):
            self.led.append({}) # Append dictionary
            self.led[-1]['x'] = self.get_definition("led{}_posx" . format(i + 1))
            self.led[-1]['y'] = self.get_definition("led{}_posy" . format(i + 1))

        self.roi_x = 80
        self.roi_y = 200
        self.roi_width = 440
        self.roi_height = 180

        self.relay_board.close_relay(relays["Power"])

    def run(self):
        # Assume that module is already charged
        #self.relay_board.close_relay(relays["Power"])

        # Manual LED
        self.relay_board.close_relay(relays["12V"])
        self.relay_board.close_relay(relays["LED_Green1"])
        self.relay_board.close_relay(relays["LED_Green2"])

        self.get_light_states(self.get_definition("green_led_threshold"),"green_leds")

        self.relay_board.open_relay(relays["12V"])
        self.relay_board.open_relay(relays["LED_Green1"])
        self.relay_board.open_relay(relays["LED_Green2"])

        if self.check_mask([1,1,-1,-1]):  # Does green LED turn on?
            strips_tester.product[0].add_measurement(type(self).__name__, "VisualGreen", Task.TASK_OK, "n/a")
            server.send_broadcast({"text": {"text": "Vizualni pregled (VisualGreen)\n", "tag": "green"}})
        else:
            strips_tester.product[0].add_measurement(type(self).__name__, "VisualGreen", Task.TASK_WARNING, "n/a")
            server.send_broadcast({"text": {"text": "Vizualni pregled (VisualGreen)\n", "tag": "red"}})

        self.relay_board.open_relay(relays["Power"])

        self.get_light_states(self.get_definition("red_led_threshold"),"red_leds")

        if self.check_mask([-1,-1,1,1]):  # Does red LED turn on?
            strips_tester.product[0].add_measurement(type(self).__name__, "VisualRed", Task.TASK_OK, "n/a")
            server.send_broadcast({"text": {"text": "Vizualni pregled (VisualRed)\n", "tag": "green"}})
        else:
            strips_tester.product[0].add_measurement(type(self).__name__, "VisualRed", Task.TASK_WARNING, "n/a")
            server.send_broadcast({"text": {"text": "Vizualni pregled (VisualRed)\n", "tag": "red"}})

        return type(self).__name__

    def in_range(self, value, min, max):

        if min < value and value < max:
            return True
        else:
            return False

    def get_threshold_image(self,threshold,save=False):
        # Update few frames to get accurate image
        for refresh in range(20):
            ret, frame = self.camera.read()  # return a single frame in variable `frame`
            time.sleep(0.1)
        roi = frame[self.roi_y:self.roi_y + self.roi_height,self.roi_x:self.roi_width + self.roi_x] # Make region of interest

        if save:
            cv2.imwrite(strips_tester.settings.test_dir + "/images/" + save + "_roi.jpg",roi)

        grayscale = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) # Grayscale ROI

        # Make binary image from grayscale ROI
        th, dst = cv2.threshold(grayscale, threshold, 255, cv2.THRESH_BINARY)

        return dst

    def check_mask(self,mask):
        # If mask[i] == -1, ignore
        result = True
        for i in range(len(self.led)):
            if self.led[i]['state'] != mask[i] and mask[i] != -1:
                result = False
                break

        return result

    # Get all the lights in test device
    def get_light_states(self,threshold,save=False):
        img = self.get_threshold_image(threshold,save)

        for i in range(len(self.led)):
            #cv2.imwrite(strips_tester.settings.test_dir + "/images/" + save + "_led{}.jpg" . format(i), img)
            self.led[i]['state'] = self.detect_led_state(img, int(self.led[i]['x']), int(self.led[i]['y']), 10)

        if save:
            cv2.imwrite(strips_tester.settings.test_dir + "/images/" + save + "_th.jpg", img)

    def detect_led_state(self, th, x, y, rng):
        state = False

        black = 0
        white = 0

        for yy in range(-rng, rng):
            for xx in range(-rng, rng):
                pixel = th[y + yy][x + xx] % 254

                if pixel:
                    white += 1
                else:
                    black += 1

        # Return True if there is more white than black
        if white > black:
            state = True

        return state

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()


class RCTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # custom variable init

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

    def run(self):
        # Assume that module is already charged
        self.relay_board.open_relay(relays["Power"])

        server.send_broadcast({"text": {"text": "Preverba RC člena ({}{})...\n" . format(self.get_definition("rc_time"),self.get_definition_unit("rc_time")), "tag": "black"}})
        time.sleep(self.get_definition("rc_time"))

        self.relay_board.close_relay(relays["Vcc1"])
        voltage = self.voltmeter.read()

        if voltage >= self.get_definition("rc_voltage"):
            strips_tester.product[0].add_measurement(type(self).__name__, "RC_RightVoltage", Task.TASK_OK, voltage)
            server.send_broadcast({"text": {"text": "Napetost desnega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "green"}})
        else:
            strips_tester.product[0].add_measurement(type(self).__name__, "RC_RightVoltage", Task.TASK_WARNING, voltage)
            server.send_broadcast({"text": {"text": "Napetost desnega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "red"}})

        self.relay_board.open_relay(relays["Vcc1"])

        self.relay_board.close_relay(relays["Vcc2"])
        voltage = self.voltmeter.read()

        if voltage >= self.get_definition("rc_voltage"):
            strips_tester.product[0].add_measurement(type(self).__name__, "RC_LeftVoltage", Task.TASK_OK, voltage)
            server.send_broadcast({"text": {"text": "Napetost levega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "green"}})
        else:
            strips_tester.product[0].add_measurement(type(self).__name__, "RC_LeftVoltage", Task.TASK_WARNING, voltage)
            server.send_broadcast({"text": {"text": "Napetost levega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "red"}})

        self.relay_board.open_relay(relays["Vcc2"])

        server.send_broadcast({"text": {"text": "Praznjenje kondenzatorjev ({}{})...\n" . format(self.get_definition("discharge_time"),self.get_definition_unit("discharge_time")), "tag": "black"}})

        GPIO.output(gpios["Discharge1"], False)
        GPIO.output(gpios["Discharge2"], False)

        time.sleep(self.get_definition("discharge_time"))

        GPIO.output(gpios["Discharge1"], True)
        GPIO.output(gpios["Discharge2"], True)

        return type(self).__name__

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()
