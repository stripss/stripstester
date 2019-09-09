import logging
import time
import RPi.GPIO as GPIO
import devices
from config_loader import *
import strips_tester
from strips_tester import *
from tester import Task, timeout
import cv2
from pylibdmtx.pylibdmtx import decode as decode_qr
import numpy as np
import base64
import datetime

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays

# OK
class StartProcedureTask(Task):
    def set_up(self):
        # Make sure that all relays are opened before test
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
        self.relay_board.open_all_relays()


    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "value": "Za testiranje zapri pokrov."})
        gui_web.send({"command": "progress", "value": "0"})

        while not self.is_lid_closed():
            time.sleep(0.1)

        gui_web.send({"command": "error", "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "value": -1})  # Clear all error messages
        strips_tester.data['start_time'][0] = datetime.datetime.utcnow()  # Get start test date
        gui_web.send({"command": "time", "mode": "start"})  # Start count for test
        gui_web.send({"command": "status", "value": "Testiranje v teku..."})

        gui_web.send({"command": "semafor", "value": (0, 1, 0), "blink": (0,0,0)})
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

        '''
        # Product detection
        detect = GPIO.input(strips_tester.settings.gpios.get("DETECT_PRODUCT"))

        if not detect:
            module_logger.info("Zaznan kos GACS_A2 Bender")
            gui_web.send({"command": "info", "value": "Zaznan kos GACS_A2 Bender"})
        else:
            strips_tester.data['exist'][0] = False
            module_logger.warning("Ni zaznanega kosa v ležišču.")
            gui_web.send({"command": "info", "value": "Ni zaznanega kosa v ležišču."})
            return {"signal": [1, "fail", 5, "NA"]}
        '''''

        return


    def tear_down(self):
        # Open all relays
        self.relay_board.hid_device.close()

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def is_product_inside(self):
        state = GPIO.input(strips_tester.settings.gpios.get("DETECT_PRODUCT"))

        return state


# OK
class FinishProcedureTask(Task):
    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16, ribbon=True)
        self.relay_board.open_all_relays()
        self.relay_board.hid_device.close()

    def run(self) -> (bool, str):
        GPIO.output(gpios["Discharge1"], True)
        GPIO.output(gpios["Discharge2"], True)

        GPIO.output(gpios['LOCK'],False)

        GPIO.output(gpios['LIGHT_GREEN'],False)
        GPIO.output(gpios['LIGHT_RED'],False)

        gui_web.send({"command": "progress", "value": "95"})
        gui_web.send({"command": "status", "value": "Odpri pokrov testne naprave."})
        gui_web.send({"command": "semafor", "blink": (0, 1, 0)})

        while self.is_lid_closed():
            GPIO.output(gpios['LIGHT_GREEN'], True)
            GPIO.output(gpios['LIGHT_RED'], True)
            time.sleep(0.2)
            GPIO.output(gpios['LIGHT_GREEN'], False)
            GPIO.output(gpios['LIGHT_RED'], False)
            time.sleep(0.2)

        if strips_tester.data['status'][0] == -1:
            strips_tester.data['status'][0] = True

        gui_web.send({"command": "progress", "value": "100"})
        gui_web.send({"command": "semafor", "value": (0, 0, 0), "blink": (0,0,0)})

        beep = False
        if strips_tester.data['exist'][0]:
            if strips_tester.data['status'][0] == True: # Product is ok
                GPIO.output(gpios['LIGHT_GREEN'], True)
                gui_web.send({"command": "semafor", "value": (0, 0, 1)})
            elif strips_tester.data['status'][0] == False: # Product is not ok
                beep = True
                GPIO.output(gpios['LIGHT_RED'], True)
                gui_web.send({"command": "semafor", "value": (1, 0, 0)})
        else:
            beep = True

        if beep:
            GPIO.output(gpios['BUZZER'], True)
            time.sleep(1)
            GPIO.output(gpios['BUZZER'], False)

        GPIO.output(gpios['LOCK'],True)

        return 

    def is_lid_closed(self):
        state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

        return state

    def tear_down(self):
        #GPIO.output(gpios['LOCK'],True)
        #server.afterlock = 10
        pass

# OK
class ReadSerial(Task):
    def set_up(self):
        # Powering up board meanwhile
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        self.vc = cv2.VideoCapture('/dev/logitech')
        while not self.vc.isOpened():  # try to get the first frame of camera
            self.vc = cv2.VideoCapture('/dev/logitech')
            #module_logger.info("Odpiranje kamere...")
            time.sleep(1)

        GPIO.output(gpios["INTERIOR_LED"], False)
        gui_web.send({"command": "progress", "value": "5"})

        # First picture is corrupted, so we leave it here.
        try:
            self.vc.read()
        except Exception as e:
            print("EXCEPT: {}" . format(e))
        tim_start = time.clock()

        raw_scanned_string = ""

        num_of_tries = 2
        gui_web.send({"command": "status", "value": "Branje QR kode..."})
        module_logger.info("Branje QR kode...")

        for i in range(num_of_tries):
            if not len(raw_scanned_string):
                #if not len(raw_scanned_string):
                rval, frame = self.vc.read()

                # Dimensions of cropped image for QR code
                x = 100
                y = 100
                h = 350
                w = 390

                frame = self.rotateImage(frame, 5)  # Rotate image by 4 degrees
                roi = frame[y:y+h, x:x+w]
                #roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

                try:
                    with timeout(seconds=3):
                        raw_scanned_string = decode_qr(roi)
                except TimeoutError:
                    raw_scanned_string = ""
                    print("Retrying...")

                retval, buffer = cv2.imencode('.jpg', roi)
                jpg_as_text = base64.b64encode(buffer)
                gui_web.send({"command": "info", "value": jpg_as_text.decode(), "type": "image"})
            else:
                raw_scanned_string = raw_scanned_string[0].data.decode("utf-8")
                gui_web.send({"command": "info", "value": "Serijska številka: {}\n" . format(raw_scanned_string)})
                self.add_measurement(0, True, "Serial", raw_scanned_string)
                break

        self.vc.release()
        GPIO.output(gpios["INTERIOR_LED"], True)

        if not len(raw_scanned_string):
            gui_web.send({"command": "error", "value": "QR koda ni zaznana"})
            self.end_test()
            return

        strips_tester.data['exist'][0] = True  # Assume it exists
        # Save successfully read image
        cv2.imwrite(strips_tester.settings.test_dir + "/last_qr.jpg",roi)

        gui_web.send({"command": "progress", "value": "10"})
        return

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
    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1",0.16)

        self.relay_board.close_relay(relays["Power"])

    def run(self) -> (bool, str):
        gui_web.send({"command": "status", "value": "Meritev 12V..."})
        gui_web.send({"command": "progress", "value": "15"})

        # Test 12V
        self.relay_board.close_relay(relays["12V"])
        voltage = self.voltmeter.read()  # Read voltage on 12v pin
        if not self.in_range(voltage, 12.0, 10):
            self.add_measurement(0, False, "12V", voltage, "V")

            gui_web.send({"command": "error", "value": "Napetost 12V je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti 12V: {}V" . format(voltage)})
            self.add_measurement(0, True, "12V", voltage, "V")
        self.relay_board.open_relay(relays["12V"])

        gui_web.send({"command": "status", "value": "Meritev 3.3V..."})
        gui_web.send({"command": "progress", "value": "20"})
        time.sleep(0.1)

        # Test 3V3
        self.relay_board.close_relay(relays["3V3"])
        voltage = self.voltmeter.read()  # Read voltage on 3v3 pin
        if not self.in_range(voltage, 3.3, 10):
            self.add_measurement(0, False, "3V3", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost 3.3V je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "3V3", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti 3.3V: {}V" . format(voltage)})
            #server.send_broadcast({"text": {"text": "Meritev napetosti 3.3V: {}V\n".format(voltage), "tag": "green"}})
        self.relay_board.open_relay(relays["3V3"])

        return 


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
    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

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
                    self.add_measurement(0, False, self.measure_order[i][1], current, "mA")
                    gui_web.send({"command": "error", "value": "Tok LED diod '{}' je izven območja. Izmerjeno {}mA" . format(self.measure_order[i][1],current)})
                else:
                    gui_web.send({"command": "info", "value": "Meritev toka '{}': {}mA" . format(self.measure_order[i][1],current)})
                    self.add_measurement(0, True, self.measure_order[i][1], current, "mA")

                self.i2c.manual_off()

            self.relay_board.open_relay(relays["Yocto_plus"])
            self.relay_board.open_relay(relays["Yocto_minus"])

            gui_web.send({"command": "status", "value": "Testiranje grelca"})
            self.relay_board.close_relay(relays["Heater"])

            voltage = self.voltmeter.read()  # Read voltage on Heater pin

            if not self.in_range(voltage, 12.0, 10.0):
                self.add_measurement(0, False, "HeaterOFF", voltage, "V")
                gui_web.send({"command": "error", "value": "Napetost izklopljenega grelca je izven območja. Izmerjeno {}V" . format(voltage)})
            else:
                gui_web.send({"command": "info", "value": "Meritev napetosti grelca: {}V\n".format(voltage)})
                self.add_measurement(0, True, "HeaterOFF", voltage, "V")

            self.i2c.turn_heater_on()
            voltage = self.voltmeter.read()  # Read voltage on Heater pin

            if not self.in_range(voltage, 0.0, 0.5, False):
                gui_web.send({"command": "error", "value": "Napetost vklopljenega grelca je izven območja. Izmerjeno {}V" . format(voltage)})
                self.add_measurement(0, False, "HeaterON", voltage, "V")
            else:
                gui_web.send({"command": "info", "value": "Meritev napetosti grelca: {}V\n".format(voltage)})
                self.add_measurement(0, True, "HeaterON", voltage, "V")

            self.i2c.manual_off()

            self.relay_board.open_relay(relays["Heater"])

            self.add_measurement(0, True, "MCP23017", "OK")
        except OSError:
            self.add_measurement(0, False, "MCP23017", "Not detected")
            gui_web.send({"command": "error", "value": "Ni zaznanega IO ekspanderja MCP23017."})

        gui_web.send({"command": "status", "value": "Testiranje senzorja temperature"})

        try:
            self.temp_sensor = devices.LM75A()  # Temperature sensor initialisation

            temperature = self.temp_sensor.read()

            if not self.in_range(temperature, 25, 5, False):
                self.add_measurement(0, False, "Temperature", temperature, "C")
                gui_web.send({"command": "error", "value": "Temperatura izven območja. Izmerjeno {}°C" . format(temperature)})
            else:
                self.add_measurement(0, True, "Temperature", temperature, "C")
                gui_web.send({"command": "info", "value": "Meritev temperature: {}°C\n".format(temperature)})

            self.add_measurement(0, True, "LM75A", "OK")
        except OSError:
            self.add_measurement(0, False, "LM75A", "Not detected")
            gui_web.send({"command": "error", "value": "Ni zaznanega senzorja temperature LM25A."})

        return 

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
    def set_up(self):
        self.charging_time = 15

        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)

        self.relay_board.close_relay(relays["Power"])

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

        gui_web.send({"command": "progress", "value": 55})

        for t in range(self.charging_time):
            gui_web.send({"command": "status", "value": "Polnenje modula ({}s)..." . format(self.charging_time - t)})

            time.sleep(1)

        gui_web.send({"command": "status", "value": "Testiranje obeh ključavnic"})
        self.set_input(1, 0) # Unlock left
        self.set_input(2, 0) # Unlock right

        voltage = self.measure_output(2) # Measure left output

        if voltage <= 0:
            self.add_measurement(0, False, "LeftOutUnlockPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (odklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (odklenjen, napajanje): {}V\n".format(voltage)})
            self.add_measurement(0, True, "LeftOutUnlockPower", voltage, "V")

        voltage = self.measure_output(1)  # Measure right output

        if voltage <= 0:
            self.add_measurement(0, False, "RightOutUnlockPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (odklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "RightOutUnlockPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (odklenjen, napajanje): {}V\n".format(voltage)})

        self.set_input(1, 1)  # Lock left
        self.set_input(2, 1)  # Lock right

        gui_web.send({"command": "progress", "value": 60})
        voltage = self.measure_output(2)  # Measure left output

        if voltage >= 0:
            self.add_measurement(0, False, "LeftOutLockPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (zaklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "LeftOutLockPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (zaklenjen, napajanje): {}V\n".format(voltage)})

        voltage = self.measure_output(1)  # Measure right output

        if voltage >= 0:
            self.add_measurement(0, False, "RightOutLockPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (zaklenjen, napajanje) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "RightOutLockPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (zaklenjen, napajanje): {}V\n".format(voltage)})

        gui_web.send({"command": "progress", "value": 65})

        self.relay_board.open_relay(relays["Power"]) # Take away power
        time.sleep(0.5)

        voltage = self.measure_output(2)  # Measure left output

        if voltage >= 0:
            self.add_measurement(0, False, "LeftOutLockNoPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (zaklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "LeftOutLockNoPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage)})

        voltage = self.measure_output(1)  # Measure left output

        if voltage >= 0:
            self.add_measurement(0, False, "RightOutLockNoPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (zaklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "RightOutLockNoPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (zaklenjen, brez napajanja): {}V\n".format(voltage)})

        self.set_input(1,0) # Unlock left
        self.set_input(2,0) # Unlock right
        gui_web.send({"command": "progress", "value": 70})

        voltage = self.measure_output(2) # Measure left output

        if voltage <= 0:
            self.add_measurement(0, False, "LeftOutUnlockNoPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost levega izhoda (odklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "LeftOutUnlockNoPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti levega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage)})

        voltage = self.measure_output(1)  # Measure left output
    
        if voltage <= 0:
            self.add_measurement(0, False, "RightOutUnlockNoPower", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost desnega izhoda (odklenjen, brez napajanja) je izven območja. Izmerjeno {}V" . format(voltage)})
        else:
            self.add_measurement(0, True, "RightOutUnlockNoPower", voltage, "V")
            gui_web.send({"command": "info", "value": "Meritev napetosti desnega izhoda (odklenjen, brez napajanja): {}V\n".format(voltage)})

        self.set_input(1,-1)  # Disable left input
        self.set_input(2,-1)  # Disable right input

        return 

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
    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16,ribbon=True)
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A955C.voltage1", 0.16)
        self.camera = cv2.VideoCapture('/dev/microsoft')  # video capture source camera

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

        self.get_light_states(50, "green_leds")

        self.relay_board.open_relay(relays["12V"])
        self.relay_board.open_relay(relays["LED_Green1"])
        self.relay_board.open_relay(relays["LED_Green2"])

        if self.check_mask([1,1,-1,-1]):  # Does green LED turn on?
            self.add_measurement(0, True, "VisualGreen", True)
            gui_web.send({"command": "info", "value": "Zaznani obe zeleni LED diodi."})
        else:
            self.add_measurement(0, True, "VisualGreen", False)
            gui_web.send({"command": "error", "value": "Napaka pri zaznavanju zelenih LED diod."})

        self.relay_board.open_relay(relays["Power"])
        gui_web.send({"command": "progress", "value": 75})

        self.get_light_states(230, "red_leds")

        if self.check_mask([-1,-1,1,1]):  # Does red LED turn on?
            self.add_measurement(0, True, "VisualRed", True)
            gui_web.send({"command": "info", "value": "Zaznani obe rdeči LED diodi."})
        else:
            self.add_measurement(0, False, "VisualRed", False)
            gui_web.send({"command": "error", "value": "Napaka pri zaznavanju rdečih LED diod."})

        return 

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

        roi_painted = roi.copy()

        show_points = 1

        if show_points:
            for a in self.led:
                cv2.circle(roi_painted, (a['x'], a['y']), 5, (0, 0, 0), 2)

        retval, buffer = cv2.imencode('.jpg', roi_painted)
        jpg_as_text = base64.b64encode(buffer)
        gui_web.send({"command": "info", "value": jpg_as_text.decode(), "type": "image"})

        if save:
            cv2.imwrite(strips_tester.settings.test_dir + "/images/" + save + "_roi.jpg",roi)

        grayscale = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY) # Grayscale ROI

        # Make binary image from grayscale ROI
        th, dst = cv2.threshold(grayscale, threshold, 255, cv2.THRESH_BINARY)

        retval, buffer = cv2.imencode('.jpg', dst)
        jpg_as_text = base64.b64encode(buffer)
        gui_web.send({"command": "info", "value": jpg_as_text.decode(), "type": "image"})

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
        self.camera.release()

# OK
class RCTest(Task):
    def set_up(self):
        self.disharge_time = 12
        self.rc_time = 5
        self.rc_voltage = 6

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
            self.add_measurement(0, True, "RC_RightVoltage", voltage, "V")
            gui_web.send({"command": "info", "value": "Napetost desnega RC člena po {}s: {}V\n".format(self.rc_time,voltage)})
        else:
            self.add_measurement(0, False, "RC_RightVoltage", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost desnega RC člena izven območja. Izmerjeno {}V" . format(voltage)})

        self.relay_board.open_relay(relays["Vcc1"])

        self.relay_board.close_relay(relays["Vcc2"])
        voltage = self.voltmeter.read()

        if voltage >= self.rc_voltage:
            self.add_measurement(0, True, "RC_LeftVoltage", voltage, "V")
            gui_web.send({"command": "info", "value": "Napetost levega RC člena po {}s: {}V\n".format(self.rc_time,voltage)})
        else:
            self.add_measurement(0, False, "RC_LeftVoltage", voltage, "V")
            gui_web.send({"command": "error", "value": "Napetost levega RC člena izven območja. Izmerjeno {}V" . format(voltage)})

        self.relay_board.open_relay(relays["Vcc2"])

        gui_web.send({"command": "status", "value": "Praznjenje modula..."})
        gui_web.send({"command": "progress", "value": "90"})

        GPIO.output(gpios["Discharge1"], False)
        GPIO.output(gpios["Discharge2"], False)

        time.sleep(self.disharge_time)

        GPIO.output(gpios["Discharge1"], True)
        GPIO.output(gpios["Discharge2"], True)

        gui_web.send({"command": "info", "value": "Modul izpraznjen."})

        return 

    def tear_down(self):
        self.relay_board.hid_device.close()
        self.voltmeter.close()
