import logging
import time
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import *
from tester import Task
import cv2
from pylibdmtx.pylibdmtx import decode as decode_qr
import numpy as np
import base64


module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays

# OK
class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        strips_tester.data['exist'] = True  # Assume it exists
        strips_tester.data['status'] = 1  # Tested good
        gui_web.send({"command": "title", "value": "GACS_A2 Bender"})

        # Make sure that all relays are opened before test
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
        self.relay_board.open_all_relays()

        gui_web.send({"command": "status", "value": "Za testiranje zapri pokrov."})
        gui_web.send({"command": "progress", "value": "0"})

        while not self.is_lid_closed():
            time.sleep(0.1)

        gui_web.send({"command": "error", "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "value": -1})  # Clear all error messages
        gui_web.send({"command": "nests", "value": 1})

        gui_web.send({"command": "status", "value": "Testiranje v teku..."})

        gui_web.send({"command": "blink", "which": 1, "value": (0, 0, 0)})
        gui_web.send({"command": "semafor", "which": 1, "value": (0, 1, 0)})
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
            module_logger.info("Zaznan kos GACS_A2 Bender")
            gui_web.send({"command": "info", "value": "Zaznan kos GACS_A2 Bender"})
        else:
            strips_tester.data['exist'] = False
            module_logger.warning("Ni zaznanega kosa v ležišču.")
            gui_web.send({"command": "info", "value": "Ni zaznanega kosa v ležišču."})
            return {"signal": [1, "fail", 5, "NA"]}

        return {"signal": [1, "ok", 5, "NA"]}


    def tear_down(self):
        # Open all relays
        self.relay_board.hid_device.close()

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

# OK
class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        pass

    def run(self) -> (bool, str):
        strips_tester.data['result_ok'] = 0
        strips_tester.data['result_fail'] = 0

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
        self.relay_board.open_all_relays()
        self.relay_board.hid_device.close()

        GPIO.output(gpios["Discharge1"], True)
        GPIO.output(gpios["Discharge2"], True)

        #server.send_broadcast({"text": {"text": "Odprite pokrov in odstranite testirane kose.\n", "tag": "black"}})
        GPIO.output(gpios['LOCK'],False)

        GPIO.output(gpios['LIGHT_GREEN'],False)
        GPIO.output(gpios['LIGHT_RED'],False)

        gui_web.send({"command": "progress", "value": "95"})
        gui_web.send({"command": "status", "value": "Odpri pokrov testne naprave."})

        while self.is_lid_closed():
            GPIO.output(gpios['LIGHT_GREEN'], True)
            GPIO.output(gpios['LIGHT_RED'], True)
            time.sleep(0.2)
            GPIO.output(gpios['LIGHT_GREEN'], False)
            GPIO.output(gpios['LIGHT_RED'], False)
            time.sleep(0.2)

        gui_web.send({"command": "progress", "value": "100"})
        gui_web.send({"command": "semafor", "which": 1, "value": (0, 0, 0)})

        beep = False
        if strips_tester.data['exist']:
            if strips_tester.data['status'] == 1: # Product is ok
                strips_tester.data['result_ok'] += 1
                GPIO.output(gpios['LIGHT_GREEN'], True)
                gui_web.send({"command": "semafor", "which": 1, "value": (0, 0, 1)})
            elif strips_tester.data['status'] == 0: # Product is not ok
                strips_tester.data['result_fail'] += 1
                beep = True
                GPIO.output(gpios['LIGHT_RED'], True)
                gui_web.send({"command": "semafor", "which": 1, "value": (1, 0, 0)})
        else:
            beep = True

        if beep:
            GPIO.output(gpios['BUZZER'], True)
            time.sleep(1)
            GPIO.output(gpios['BUZZER'], False)

        GPIO.output(gpios['LOCK'],True)

        return {"signal": [1, "ok", 5, "NA"]}

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def tear_down(self):
        #GPIO.output(gpios['LOCK'],True)
        #server.afterlock = 10
        pass

# OK
class ReadSerial(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # Powering up board meanwhile
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        self.vc = cv2.VideoCapture('/dev/logitech')
        while not self.vc.isOpened():  # try to get the first frame of camera
            self.vc = cv2.VideoCapture('/dev/logitech')
            module_logger.info("Odpiranje kamere...")
            time.sleep(1)

        GPIO.output(gpios["INTERIOR_LED"], False)
        gui_web.send({"command": "progress", "value": "5"})

        # First picture is corrupted, so we leave it here.
        rval, frame = self.vc.read()
        tim_start = time.clock()

        raw_scanned_string = ""

        num_of_tries = 5
        gui_web.send({"command": "status", "value": "Branje QR kode..."})
        module_logger.info("Branje QR kode...")

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
                retval, buffer = cv2.imencode('.jpg', roi)
                jpg_as_text = base64.b64encode(buffer)
                gui_web.send({"command": "image", "value": jpg_as_text.decode()})
            else:
                raw_scanned_string = raw_scanned_string[0].data.decode("utf-8")
                gui_web.send({"command": "info", "value": "Serijska številka: {}\n" . format(raw_scanned_string)})

                #server.send_broadcast({"text": {"text": "Serijska številka: {}\n" . format(raw_scanned_string), "tag": "black"}})
                #strips_tester.current_product.serial = raw_scanned_string
                break

        self.vc.release()
        GPIO.output(gpios["INTERIOR_LED"], True)

        if not len(raw_scanned_string):
            gui_web.send({"command": "error", "value": "QR koda ni zaznana"})
            strips_tester.data['status'] = 0
            return {"signal": [1, 'fail', 5, 'NA']}
            #server.send_broadcast({"text": {"text": "Serijske številke ni mogoče prebrati.\n", "tag": "red"}})

        # Save successfully read image
        cv2.imwrite("/strips_tester_project/strips_tester/last_qr.jpg",roi)

        gui_web.send({"command": "progress", "value": "10"})
        return {"signal": [1, 'ok', 0, 'NA']}


    def rotateImage(self,image, angle):
        image_center = tuple(np.array(image.shape[1::-1]) / 2)
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR)
        return result

    def tear_down(self):
        GPIO.output(gpios["INTERIOR_LED"], True)
        self.relay_board.hid_device.close()

# OK
class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1",0.16)

        self.measurement_results = {}

        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "value": "Meritev 12V..."})
        gui_web.send({"command": "progress", "value": "15"})

        # Test 12V
        self.relay_board.close_relay(relays["12V"])
        voltage = self.voltmeter.read()  # Read voltage on 12v pin
        if not self.in_range(voltage, 12.0, 10):
            self.measurement_results["12v"] = [voltage, "fail", 5, "V"]
            strips_tester.data['status'] = 0
            gui_web.send({"command": "error", "value": "Napetost 12V je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti 12V: {}V" . format(voltage)})
            self.measurement_results["12v"] = [voltage, "ok", 0, "V"]
        self.relay_board.open_relay(relays["12V"])

        gui_web.send({"command": "status", "value": "Meritev 3.3V..."})
        gui_web.send({"command": "progress", "value": "20"})
        time.sleep(0.1)

        # Test 3V3
        self.relay_board.close_relay(relays["3V3"])
        voltage = self.voltmeter.read()  # Read voltage on 3v3 pin
        if not self.in_range(voltage, 3.3, 10):
            self.measurement_results["3v3"] = [voltage, "fail", 5, "V"]
            strips_tester.data['status'] = 0
            gui_web.send({"command": "error", "value": "Napetost 3.3V je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.measurement_results["3v3"] = [voltage, "ok", 0, "V"]
            gui_web.send({"command": "info", "value": "Meritev napetosti 3.3V: {}V" . format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti 3.3V: {}V\n".format(voltage), "tag": "green"}})
        self.relay_board.open_relay(relays["3V3"])

        return self.measurement_results


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

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()

class I2C_Communication(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)

        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)
        self.measurement_results = {}

        # Measure order: lednum,color_I_def,toleranca_I_def,
        self.measure_order = [
            (0, "blue left", 40.0, 20.0),
            (1, "green left", 40.0, 20.0),
            (2, "red left", 40.0, 20.0),
            (3, "blue right", 40.0, 20.0),
            (4, "green right", 40.0, 20.0),
            (5, "red right", 40.0, 20.0),
            (6, "white", 120.0, 20.0)
        ]

        self.relay_board.close_relay(relays["Power"])

    def run(self):
        percent = 20

        # Set voltmeter as ampermeter for this test
        self.relay_board.close_relay(relays["Yocto_plus"])
        self.relay_board.close_relay(relays["Yocto_minus"])

        try:
            self.i2c = devices.MCP23017()  # IO Expander initialisation

            for i in range(len(self.measure_order)):
                percent = percent + 5
                gui_web.send({"command": "status", "value": "Meritev '{}'" . format(self.measure_order[i][1])})
                gui_web.send({"command": "progress", "value": percent})
                self.i2c.test_one_led(self.measure_order[i][0])
                current = self.voltmeter.read() * 1000.0

                if not self.in_range(current, self.measure_order[i][2], self.measure_order[i][3]):
                    #server.send_broadcast({"text": {"text": "Meritev toka '{}{}' LED: {}mA\n".format(self.measure_order[i][1],self.measure_order[i][2],current), "tag": "red"}})
                    self.measurement_results[self.measure_order[i][1]] = [current, "fail", 5, "mA"]
                    gui_web.send({"command": "error", "value": "Tok LED diod '{}' je izven območja. Izmerjeno {}mA" . format(self.measure_order[i][1],current)})
                    strips_tester.data['status'] = 0
                else:
                    #server.send_broadcast({"text": {"text": "Meritev toka '{}{}' LED: {}mA\n".format(self.measure_order[i][1],self.measure_order[i][2],current), "tag": "green"}})
                    gui_web.send({"command": "info", "value": "Meritev toka '{}': {}mA" . format(self.measure_order[i][1],current)})
                    self.measurement_results[self.measure_order[i][1]] = [current, "ok", 0, "mA"]

                self.i2c.manual_off()

            self.relay_board.open_relay(relays["Yocto_plus"])
            self.relay_board.open_relay(relays["Yocto_minus"])

            gui_web.send({"command": "status", "value": "Testiranje grelca"})
            self.relay_board.close_relay(relays["Heater"])

            voltage = self.voltmeter.read()  # Read voltage on Heater pin

            if not self.in_range(voltage, 12.0, 10.0):
                #server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "red"}})
                self.measurement_results["HeaterOFF"] = [voltage, "fail", 5, "V"]
                gui_web.send({"command": "error", "value": "Napetost izklopljenega grelca je izven območja. Izmerjeno {}V" . format(voltage)})
                strips_tester.data['status'] = 0
            else:
                #server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "green"}})
                gui_web.send({"command": "info", "value": "Meritev napetosti grelca: {}V\n".format(voltage)})
                self.measurement_results["HeaterOFF"] = [voltage, "ok", 0, "V"]

            self.i2c.turn_heater_on()
            voltage = self.voltmeter.read()  # Read voltage on Heater pin

            if not self.in_range(voltage, 0.0, 0.5, False):
                #server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "red"}})
                self.measurement_results["HeaterON"] = [voltage, "fail", 5, "V"]
                gui_web.send({"command": "error", "value": "Napetost vklopljenega grelca je izven območja. Izmerjeno {}V" . format(voltage)})
                strips_tester.data['status'] = 0
            else:
                #server.send_broadcast({"text": {"text": "Meritev napetosti grelca: {}V\n".format(voltage), "tag": "green"}})
                gui_web.send({"command": "info", "value": "Meritev napetosti grelca: {}V\n".format(voltage)})
                self.measurement_results["HeaterON"] = [voltage, "ok", 0, "V"]

            self.i2c.manual_off()

            self.relay_board.open_relay(relays["Heater"])
        except OSError:
            #server.send_broadcast({"text": {"text": "Napaka branja iz IO ekspanderja MCP23017.\n", "tag": "red"}})
            self.measurement_results["MCP23017"] = [0, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Ni zaznanega IO ekspanderja MCP23017."})
            strips_tester.data['status'] = 0

            #strips_tester.product[0].add_measurement(type(self).__name__, "MCP23017", Task.TASK_WARNING, "Sensor not found.")

        gui_web.send({"command": "status", "value": "Testiranje senzorja temperature"})

        try:
            self.temp_sensor = devices.LM75A()  # Temperature sensor initialisation

            temperature = self.temp_sensor.read()

            if not self.in_range(temperature, 25, 5, False):
                #server.send_broadcast({"text": {"text": "Meritev temperature: {}°C\n".format(temperature), "tag": "red"}})
                self.measurement_results["Temperature"] = [temperature, "fail", 5, "C"]
                gui_web.send({"command": "error", "value": "Temperatura izven območja. Izmerjeno {}°C" . format(temperature)})
                strips_tester.data['status'] = 0
            else:
                self.measurement_results["Temperature"] = [temperature, "ok", 0, "C"]
                gui_web.send({"command": "info", "value": "Meritev temperature: {}°C\n".format(temperature)})
                #server.send_broadcast({"text": {"text": "Meritev temperature: {}°C\n".format(temperature), "tag": "green"}})

        except OSError:
            #server.send_broadcast({"text": {"text": "Napaka branja iz senzorja LM75A.\n", "tag": "red"}})
            gui_web.send({"command": "error", "value": "Ni zaznanega senzorja temperature LM25A."})
            self.measurement_results["Temperature"] = [-1, "fail", 5, "C"]
            strips_tester.data['status'] = 0

        return self.measurement_results

    def in_range(self, value, expected, tolerance, percent = True):
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

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()

#OK
class LockSimulator(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.charging_time = 10

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

        self.relay_board.close_relay(relays["Power"])
        self.measurement_results = {}

    def run(self):
        '''
        self.relay_board.close_relay(relays["Vcc1"])
        voltage = self.voltmeter.read()

        while voltage < 11.78:
            voltage = self.voltmeter.read()
            #server.send_broadcast({"text": {"text": "Dvigovanje desne napetosti: {}V\n".format(voltage), "tag": "black"}})

            time.sleep(0.5)

        self.relay_board.open_relay(relays["Vcc1"])
        time.sleep(0.05)
        self.relay_board.close_relay(relays["Vcc2"])
        voltage = self.voltmeter.read()

        while voltage < 11.78:
            voltage = self.voltmeter.read()
            #server.send_broadcast({"text": {"text": "Dvigovanje leve napetosti: {}V\n".format(voltage), "tag": "black"}})
            time.sleep(0.5)

        self.relay_board.open_relay(relays["Vcc2"])
        '''

        #server.send_broadcast({"text": {"text": "Polnenje modula...\n", "tag": "black"}})
        gui_web.send({"command": "status", "value": "Polnenje modula..."})
        gui_web.send({"command": "progress", "value": 55})
        time.sleep(self.charging_time)

        gui_web.send({"command": "status", "value": "Testiranje obeh ključavnic"})
        self.set_input(1,0) # Unlock left
        self.set_input(2,0) # Unlock right

        voltage = self.measure_output(2) # Measure left output

        if voltage <= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["LeftOutUnlockPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (odklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})

            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (odklenjen, napajanje): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["LeftOutUnlockPower"] = [voltage, "ok", 0, "V"]

        voltage = self.measure_output(1)  # Measure right output

        if voltage <= 0:

            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["RightOutUnlockPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (odklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (odklenjen, napajanje): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["RightOutUnlockPower"] = [voltage, "ok", 0, "V"]

        self.set_input(1, 1)  # Lock left
        self.set_input(2, 1)  # Lock right

        gui_web.send({"command": "progress", "value": 60})
        voltage = self.measure_output(2)  # Measure left output

        if voltage >= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["LeftOutLockPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (zaklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (zaklenjen, napajanje): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["LeftOutLockPower"] = [voltage, "ok", 0, "V"]

        voltage = self.measure_output(1)  # Measure right output

        if voltage >= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["RightOutLockPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (zaklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (zaklenjen, napajanje): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, napajanje): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["RightOutLockPower"] = [voltage, "ok", 0, "V"]


        gui_web.send({"command": "progress", "value": 65})
        # Take away power
        self.relay_board.open_relay(relays["Power"])
        time.sleep(0.5)

        voltage = self.measure_output(2)  # Measure left output

        if voltage >= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["LeftOutLockNoPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (zaklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["LeftOutLockNoPower"] = [voltage, "ok", 0, "V"]

        voltage = self.measure_output(1)  # Measure left output

        if voltage >= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["RightOutLockNoPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (zaklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["RightOutLockNoPower"] = [voltage, "ok", 0, "V"]

        self.set_input(1,0) # Unlock left
        self.set_input(2,0) # Unlock right
        gui_web.send({"command": "progress", "value": 70})

        voltage = self.measure_output(2) # Measure left output

        if voltage <= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["LeftOutUnlockNoPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (odklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti levega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["LeftOutUnlockNoPower"] = [voltage, "ok", 0, "V"]

        voltage = self.measure_output(1) # Measure left output
    
        if voltage <= 0:
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "red"}})
            self.measurement_results["RightOutUnlockNoPower"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (odklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti desnega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage), "tag": "green"}})
            self.measurement_results["RightOutUnlockNoPower"] = [voltage, "ok", 0, "V"]

        self.set_input(1,-1)  # Disable left input
        self.set_input(2,-1)  # Disable right input

        return self.measurement_results

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


        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)
        self.camera = cv2.VideoCapture('/dev/microsoft')  # video capture source camera
        self.measurement_results = {}

        gui_web.send({"command": "status", "value": "Vizualni pregled LED diod"})
        while not self.camera.isOpened():  # try to get the first frame of camera
            self.camera = cv2.VideoCapture('/dev/microsoft')
            time.sleep(0.1)

        # First picture is corrupted, so we leave it here.
        rval, frame = self.camera.read()

        self.led = []

        self.led.append({"x": 138,"y": 111}) # Append dictionary
        self.led.append({"x": 369,"y": 110}) # Append dictionary
        self.led.append({"x": 182,"y": 110}) # Append dictionary
        self.led.append({"x": 320,"y": 106}) # Append dictionary

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

        self.get_light_states(70, "green_leds")

        self.relay_board.open_relay(relays["12V"])
        self.relay_board.open_relay(relays["LED_Green1"])
        self.relay_board.open_relay(relays["LED_Green2"])

        if self.check_mask([1,1,-1,-1]):  # Does green LED turn on?
            self.measurement_results["VisualGreen"] = [1, "ok", 0, "n/a"]
            gui_web.send({"command": "info", "value": "Zaznani obe zeleni LED diodi."})
        else:
            self.measurement_results["VisualGreen"] = [1, "fail", 5, "n/a"]
            gui_web.send({"command": "error", "value": "Napaka pri zaznavanju zelenih LED diod."})
            strips_tester.data['status'] = 0

        self.relay_board.open_relay(relays["Power"])
        gui_web.send({"command": "progress", "value": 75})

        self.get_light_states(230, "red_leds")

        if self.check_mask([-1,-1,1,1]):  # Does red LED turn on?
            self.measurement_results["VisualRed"] = [1, "ok", 0, "n/a"]
            gui_web.send({"command": "info", "value": "Zaznani obe rdeči LED diodi."})
        else:
            self.measurement_results["VisualRed"] = [1, "fail", 5, "n/a"]
            gui_web.send({"command": "error", "value": "Napaka pri zaznavanju rdečih LED diod."})
            strips_tester.data['status'] = 0

        return self.measurement_results

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

        retval, buffer = cv2.imencode('.jpg', roi)
        jpg_as_text = base64.b64encode(buffer)
        gui_web.send({"command": "image", "value": jpg_as_text.decode()})

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

# OK
class RCTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.disharge_time = 12
        self.rc_time = 5
        self.rc_voltage = 6

        self.measurement_results = {}

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

    def run(self):
        # Assume that module is already charged
        self.relay_board.open_relay(relays["Power"])

        gui_web.send({"command": "status", "value": "Preverjanje RC člena..."})
        gui_web.send({"command": "progress", "value": "80"})

        time.sleep(self.rc_time)
        gui_web.send({"command": "progress", "value": "85"})

        self.relay_board.close_relay(relays["Vcc1"])
        voltage = self.voltmeter.read()

        if voltage >= self.rc_voltage:
            self.measurement_results["RC_RightVoltage"] = [voltage, "ok", 0, "V"]
            gui_web.send({"command": "info", "value": "Napetost desnega RC člena po {}s: {}V\n".format(self.rc_time,voltage)})
            #server.send_broadcast({"text": {"text": "Napetost desnega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "red"}})
        else:
            self.measurement_results["RC_RightVoltage"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost desnega RC člena izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
            #server.send_broadcast({"text": {"text": "Napetost desnega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "red"}})

        self.relay_board.open_relay(relays["Vcc1"])

        self.relay_board.close_relay(relays["Vcc2"])
        voltage = self.voltmeter.read()

        if voltage >= self.rc_voltage:
            self.measurement_results["RC_LeftVoltage"] = [voltage, "ok", 0, "V"]
            gui_web.send({"command": "info", "value": "Napetost levega RC člena po {}s: {}V\n".format(self.rc_time,voltage)})
            #server.send_broadcast({"text": {"text": "Napetost levega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "green"}})
        else:
            self.measurement_results["RC_LeftVoltage"] = [voltage, "fail", 5, "V"]
            gui_web.send({"command": "error", "value": "Napetost levega RC člena izven območja. Izmerjeno {}V" . format(voltage)})
            strips_tester.data['status'] = 0
            #server.send_broadcast({"text": {"text": "Napetost levega RC člena po {}{}: {}V\n".format(self.get_definition("rc_time"),self.get_definition_unit("rc_time"),voltage), "tag": "red"}})

        self.relay_board.open_relay(relays["Vcc2"])

        gui_web.send({"command": "status", "value": "Praznjenje modula..."})
        gui_web.send({"command": "progress", "value": "90"})
        #server.send_broadcast({"text": {"text": "Praznjenje kondenzatorjev ({}{})...\n" . format(self.get_definition("discharge_time"),self.get_definition_unit("discharge_time")), "tag": "black"}})

        GPIO.output(gpios["Discharge1"], False)
        GPIO.output(gpios["Discharge2"], False)

        time.sleep(self.disharge_time)

        GPIO.output(gpios["Discharge1"], True)
        GPIO.output(gpios["Discharge2"], True)

        gui_web.send({"command": "info", "value": "Modul izpraznjen."})

        return self.measurement_results

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()
