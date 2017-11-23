import importlib
import logging
import sys
import time
import multiprocessing
import os

import serial
import struct
#import wifi
import RPi.GPIO as GPIO
import devices
from config_loader import *
# sys.path.append("/strips_tester_project/garo/")
from .garo.stm32loader import CmdException
# from strips_tester import *
import strips_tester
from strips_tester import settings
from tester import Task #, connect_to_wifi
from .garo import Flash
from datetime import datetime
import numpy as np
import strips_tester.db
from strips_tester import utils

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

gpios = strips_tester.settings.gpios
relays = strips_tester.settings.relays


# You may set global test level and logging level in config_loader.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)


# checks if lid is opened
# prevents cyclic import, because gpios aren't available on import time
class LidOpenCheck:
    def __init__(self):
        # if lid is opened
        state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
        if not state_GPIO_SWITCH:
            module_logger.error("Lid opened /")
            #strips_tester.current_product.task_results.append(False)
            #strips_tester.emergency_break_tasks = True
        else:
            module_logger.debug("Lid closed")

class BarCodeReadTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        #self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        which_hid = os.system('ls /sys/class/hidraw')
        self.reader = devices.Honeywell1400g(0x0c2e, 0x0b87)
        #self.camera_device = devices.CameraDevice(Xres=640, Yres=480)
        #self.meshloader = devices.MeshLoaderToList('/strips_tester_project/strips_tester/configs/000000005e16aa11_MVC2/Mask.json')

    def run(self) -> (bool, str):
        #module_logger.info("Prepared for reading matrix code:")
        module_logger.info("Skeniraj QR kodo: ")
        # global current_product
        raw_scanned_string = self.reader.get_decoded_data() # use scanned instead of camera
        #raw_scanned_string = input()
        #module_logger.info("Code read successful")
        #img = self.camera_device.take_one_picture()
        #center = self.meshloader.matrix_code_location["center"]
        #width = self.meshloader.matrix_code_location["width"]
        #height = self.meshloader.matrix_code_location["height"]
        #raw_scanned_string = utils.decode_qr(img[center[0]-height//2:center[0]+height//2+1, center[1]-width//2:center[1]+width//2+1, :]) # hard coded, add feature to mesh generator
        strips_tester.current_product.raw_scanned_string = raw_scanned_string
        #strips_tester.current_product.raw_scanned_string = 'M1706080087500004S2401877'
        module_logger.debug("%s", strips_tester.current_product)
        GPIO.output(gpios["LIGHT_GREEN"], G_LOW)

        return {"signal":[1, "ok", 5, "NA"]}

    def tear_down(self):
        pass
        #self.camera_device.close()

class ProductConfigTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)
        # global produt data structure defined in tester. Configure the product here for later use and write do DB
        self.product = strips_tester.current_product

    def run(self) -> (bool, str):
        if self.parse_2017_raw_scanned_string():
            return {"signal": [1, "ok", 5, "NA"]}
        else:
            return {"signal": [0, "fail", 5, "NA"]}

    def to_product_production_datetime(self, year: int = 2017, month: int = 1, day: int = 1):
        self.product.production_datetime = datetime.now()
        self.product.production_datetime.replace(year=(2000+year), month=month, day=day)


    def parse_2017_raw_scanned_string(self):
        """ example:
        M 170607 00875 000 04 S 2401877
        M = oznaka za material
        170607 = datum: leto, mesec, dan
        00875 = pet mestna serijska številka – števec, ki se za vsako tiskanino povečuje za 1
        000 = trimestna oznaka, ki se bo v prihodnosti uporabljala za nastavljanje stroja za valno spajkanje, po potrebi pa tudi kaj drugega
        04 = število tiskanin v enem panelu – podatek potrebuje iWare
        S = oznako potrebuje iWare za označevanje SAOP kode
        2401877 =  SAOP koda tiskanine"""

        def create_4B_serial(year, month, day, five_digit_serial):
            day_number = day - 1 + (month - 1) * 31 + year * 366
            day_number %= 2 ** 14  # wrap around every 44 years
            part_1 = day_number << 18
            part_2 = five_digit_serial
            serial = part_1 | part_2
            return serial

        if not self.product.raw_scanned_string:
            logging.error("Not scanned yet!")
            return False
        else:
            ss = self.product.raw_scanned_string
            self.to_product_production_datetime(year=int(ss[1:3]), month=int(ss[3:5])+1,day=int(ss[5:7]))
            self.product.serial = self.product.type.type << 32 | create_4B_serial(int(ss[1:3]), int(ss[3:5]), int(ss[5:7]), int(ss[7:12]))
            return True

    def tear_down(self):
        pass




class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def run(self) -> (bool, str):
        if "START_SWITCH" in settings.gpios:
            #module_logger.info("Waiting for START_SWITCH...")
            module_logger.info("Za nadaljevanje zapri pokrov")
            while True:
                # GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
                if state_GPIO_SWITCH:
                    #module_logger.info("START_SWITCH pressed(lid closed)")
                    break
                time.sleep(0.1)
        else:
            module_logger.info("START_SWITCH not defined in config_loader.py!")
        return {"signal": [1, "ok", 5, "NA"]}

    def tear_down(self):
        pass


class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.mesurement_delay = 0.16
        self.measurement_results = {}
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A08C8.voltage1", self.mesurement_delay)

    def run(self) -> (bool, str):
        module_logger.info("Testiranje napetosti...")
        #Vc
        self.relay_board.close_relay(relays["Vc"])
        if self.voltmeter.in_range(13.5, 16.5):
            self.measurement_results['Vc'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['Vc'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["Vc"])
        # 12V
        self.relay_board.close_relay(relays["12V"])
        if self.voltmeter.in_range(11, 13):
            self.measurement_results['12V'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['12V'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["12V"])
        # 5V
        self.relay_board.close_relay(relays["5V"])
        if self.voltmeter.in_range(4.5, 5.5):
            self.measurement_results['5V'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['5V'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["5V"])
        # 3V3
        self.relay_board.close_relay(relays["3V3"])
        if self.voltmeter.in_range(3.0, 3.8):
            self.measurement_results['3V3'] = [self.voltmeter.value, "ok", 5, "V"]
        else:
            self.measurement_results['3V3'] = [self.voltmeter.value, "fail", 5, "V"]
        self.relay_board.open_relay(relays["3V3"])

        LidOpenCheck()
        return self.measurement_results

    def tear_down(self):
        self.voltmeter.close()
        self.relay_board.hid_device.close()


class FlashWifiModuleTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_WIFI_RX"])
        self.relay_board.close_relay(relays["UART_WIFI_TX"])

    def run(self):
        if strips_tester.current_product.variant.lower().startswith("wifi"):
            success = Flash.flash_wifi()
            if success:
                LidOpenCheck()
                return True, "Flash SUCCESS"
            else:
                LidOpenCheck()
                return False, "Flash FAILED"
        else:
            module_logger.info("Not wifi product, no flashing needed!")
            LidOpenCheck()
            return True, "Flash not needed"

    def tear_down(self):
        self.relay_board.open_relay(relays["UART_WIFI_RX"])
        self.relay_board.open_relay(relays["UART_WIFI_TX"])
        self.relay_board.hid_device.close()



class FlashMCUTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        # every flasher has reset, dtr pin( determined by device in hw_"serial" and number of retries
        self.flasher = Flash.STM32M0Flasher(gpios["RST"], gpios["DTR"], 5)
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["GND"])
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.relay_board.close_relay(relays["DTR_MCU"])
        self.relay_board.close_relay(relays["RST"])
        time.sleep(0.5)

    def run(self):
        if not lid_closed():
            return {"signal": [0, "fail", 5, "NA"]}
        result = self.flasher.flash()
        if result:
            return {"MCU flash": [1, "ok", 5, "bool"]}
        else:
            return {"MCU flash": [0, "fail", 5, "bool"]}


    def tear_down(self):
        self.relay_board.open_all_relays()
        self.relay_board.close()
        self.flasher.close()



class UartPingTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["GND"])
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.serial_port = serial.Serial(
            port="/dev/ttyAMA0",
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=0,
            rtscts=0,
            timeout=3,
            dsrdtr=0
        )

    def run(self):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")
        timer = time.time()
        module_logger.info("Listening for internal ping")
        buffer = bytes(5)
        ping_request = [0x00, 0x04, 0x01, 0x21, 0x10]
        self.serial_port.write(ping_request)
        try:
            resp = self.serial_port.read(5)
            # print(resp)
            if resp == bytes(ping_request):
                # print("ping ok")
                return True, "Ping intercepted"
        except:
            raise CmdException("Can't read port or timeout")
        else:
            if resp == 0x79:
                # ACK
                CmdException("ACK")
            elif resp == 0x1F:
                # NACK
                raise CmdException("NACK")
            else:
                module_logger.warning("Unknown packet")

        return False, "Not implemented yet"

    def tear_down(self):
        self.serial_port.close()
        self.relay_board.open_all_relays()
        self.relay_board.close()



class InternalTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["GND"])
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.relay_board.close_relay(relays["COMMON"])
        self.measurement_results = {}
        self.serial_port_uart = serial.Serial(
            port="/dev/ttyAMA0",
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=0,
            rtscts=0,
            timeout=0.5,
            dsrdtr=0
        )
        self.meshloader = devices.MeshLoaderToList('/strips_tester_project/strips_tester/configs/000000005e16aa11_MVC2/Mask.json')
        self.camera_algorithm = devices.CompareAlgorithm(span=3)
        self.camera_device = devices.CameraDevice(Xres=640, Yres=480)
        self.temp_sensor = devices.IRTemperatureSensor(0)  # meas delay = 0
        self.start_t = None

    @staticmethod
    def crc(data):
        def _update_crc( crc, byte_):
            crc = (crc >> 8) | ((crc & 0xFF) << 8)
            crc ^= byte_ & 0xFF
            crc ^= (crc & 0xFF) >> 4
            crc ^= ((crc & 0x0F) << 8) << 4
            crc ^= ((crc & 0xFF) << 4) << 1
            # print (crc)
            return crc
        crc = 0
        for c in data:
            crc = _update_crc(crc, c)
        return struct.unpack("BB", struct.pack("<H", crc))  # change endianess

    def test_relays(self, queue):
        #module_logger.info("Testing_relays...")
        module_logger.info("Testiranje relejev...")
        relay_tests = []
        self.relay_board.open()
        self.mesurement_delay = 0.0
        self.voltmeter = devices.YoctoVoltageMeter("VOLTAGE1-A08C8.voltage1", self.mesurement_delay)

        ''' | delay_R1 delay_R2  sum_delay
            |     |      |     |  ...
            |-----------------------
            |     0.3   0.7    1.0
        '''
        delay_R1 = 0.3
        delay_R2 = 0.7
        sum_delay = 1.0
        R2_voltage = [14.5, 0.0, 0.0]
        R1_voltage = [0.0, 0.0, 14.5]


        # time.sleep(1.0)  # relay board open time
        # # before test, both open
        # # RE1
        # self.relay_board.close_relay(relays["RE1"])
        # time.sleep(0.250)
        # if not self.voltmeter.in_range(14.5 - 1.0, 14.5 + 1.0):
        #     self.relay_exit(queue)
        #     return False
        # else:
        #     relay_tests.append(True)
        # self.relay_board.open_relay(relays["RE1"])
        # # RE2
        # time.sleep(0.5)
        # self.relay_board.close_relay(relays["RE2"])
        # time.sleep(0.250)
        # if not self.voltmeter.in_range(14.5 - 1.0, 14.5 + 1.0):
        #     self.relay_exit(queue)
        #     return False
        # else:
        #     relay_tests.append(True)
        # self.relay_board.open_relay(relays["RE2"])

        #print(time.time())
        start_time = queue.get(block=True, timeout=10)
        #print('s',start_time)
        for i in range(len(R1_voltage)):
            # RE1
            self.relay_board.close_relay(relays["RE1"])
            dt = (start_time + i * (sum_delay) + delay_R1) - time.time()
            while 0.0 < dt:
                time.sleep(0.5 * dt)
                dt = (start_time + i * (sum_delay) + delay_R1) - time.time()
            # relay_tests.append(self.voltmeter.in_range(R1_voltage[i] - 1.0, R1_voltage[i] + 1.0))
            #print(time.time())
            #module_logger.info('Voltage %s', self.voltmeter.read())
            if not self.voltmeter.in_range(R1_voltage[i] - 1.0, R1_voltage[i] + 1.0):
                #print(time.time())
                module_logger.error("Releji ne delujejo1." + str(i))
                self.relay_exit(queue)
                return False
            else:
                relay_tests.append(True)
            #print(time.time())
            self.relay_board.open_relay(relays["RE1"])
            # RE2
            self.relay_board.close_relay(relays["RE2"])
            dt = (start_time + i * (sum_delay) + delay_R2) - time.time()
            while 0.0 < dt:
                time.sleep(0.5 * dt)
                dt = (start_time + i * (sum_delay) + delay_R2) - time.time()
            # relay_tests.append(self.voltmeter.in_range(R2_voltage[i] - 1.0, R2_voltage[i] + 1.0))
            #print(time.time())
            if not self.voltmeter.in_range(R2_voltage[i] - 1.0, R2_voltage[i] + 1.0):
                #print(time.time())
                module_logger.error("Releji ne delujejo2." + str(i))
                self.relay_exit(queue)
                return False
            else:
                relay_tests.append(True)
            #print(time.time())
            self.relay_board.open_relay(relays["RE2"])
            #print('\n\n\n')

        self.relay_board.close()
        self.voltmeter.close()
        result = all(relay_tests)
        queue.put(result)
        return all(relay_tests)

    def relay_exit(self, queue):
        self.relay_board.close()
        self.voltmeter.close()
        queue.put(False)

    def run(self):

        internal_tests = []
        if not lid_closed():
            return {"signal": [0, "fail", 5, "NA"]}

        try:
            queue = multiprocessing.Queue()
            relay_process = multiprocessing.Process(target=self.test_relays, args=(queue,))
            self.relay_board.close()  #  can't pass relay board to other process so we close it here and reopen in relay process
            relay_process.start()

            module_logger.info("STM32M0 boot time %ss", 5)
            time.sleep(5) # process sync and UC boot time

            op_code = bytearray([0x06])
            crc_part_1, crc_part_2 = self.crc(op_code)
            self.serial_port_uart.write(bytes([0x00, 0x04, int().from_bytes(op_code, "big"), crc_part_1, crc_part_2]))
            # self.serial_port.write(bytes([0x00, 0x04, 0x06, 0xC6, 0x60]))  # full start_test packet

            #module_logger.info("Testing segment display...")
            module_logger.info("Testiranje zaslona...")
            self.start_t = time.time()  # everything synchronizes to this time
            queue.put(self.start_t)  # send start time to relay process for relay sync
            for i in range(14):
                dt = (self.start_t + 0.08 + (i * 0.2)) - time.time()
                while 0.0 < dt:
                    time.sleep(0.5 * dt)
                    dt = (self.start_t + 0.08 + (i * 0.2)) - time.time()
                pic_start_time = time.time()
                self.camera_device.take_picture()
                module_logger.debug('Took picture %s at %s s, %s', i, pic_start_time - self.start_t, time.time() - pic_start_time)
            self.camera_device.save_all_imgs_to_file()

            camera_result = self.camera_algorithm.run(self.camera_device.img, self.meshloader.indices, self.meshloader.indices_length, 14)
            if camera_result == True:
                self.measurement_results["display"] = [1, "ok", 0, "bool"]
                module_logger.info("Zaslon ok")
            else:
                self.measurement_results["display"] = [0, "fail", 0, "bool"]
                module_logger.error("Zaslon ne deluje")

            relay_process.join(timeout=25)
            module_logger.info("Testiranje tipk...")
            result = queue.get()
            if result == True:
                module_logger.info("Releji ok")
                self.measurement_results["relays"] = [1, "ok", 0, "bool"]
            else:
                module_logger.error("Releji ne delujejo")
                self.measurement_results["relays"] = [0, "fail", 0, "bool"]

            # default, even if no data from uart
            ###
            self.measurement_results["keyboard"] = [0, "fail", 0, "bool"]
            self.measurement_results["temperature"] = [0.0, "fail", 0, "°C"]
            self.measurement_results["RTC"] = [0, "fail", 0, "bool"]
            self.measurement_results["flash test"] = [0, "fail", 0, "bool"]
            self.measurement_results["switches"] = [0, "fail", 0, "bool"]
            self.measurement_results["board test"] = [0, "fail", 0, "bool"]
            ###

            payload = bytearray()
            #module_logger.info("Start listening on uart...")
            # retries end with serial timeout which is in set_up
            self.serial_port_uart.flush()
            for try_number in range(40):
                if not lid_closed():
                    return self.measurement_results
                time.sleep(0.015)
                module_logger.debug("Trying to read header \x00")
                header = self.serial_port_uart.read(1)
                if header == b'\x00':
                    module_logger.debug("Receiving test results...")
                    message_length = self.serial_port_uart.read(1)
                    module_logger.debug("Message length: %s: ", message_length)
                    for i in range(int().from_bytes(message_length, "big") -1):
                        payload.extend(self.serial_port_uart.read(1))
                    module_logger.debug("payload: %s", payload)
                    msg_type, keyboard, temperature, rtc, flash, switches, board, crc1, crc2= struct.unpack("<BHhBBBBBB", payload)
                    if keyboard == 0xb03b: #0x8030:
                        module_logger.debug("keyboard ok");
                        self.measurement_results["keyboard"] = [1, "ok", 0, "bool"]
                    else:
                        module_logger.warning("keyboard error: %s", hex(keyboard))
                        self.measurement_results["keyboard"] = [0, "fail", 0, "bool"]

                    temp_in_C = ((temperature/100)+15.8) # calibration in MVC
                    if self.temp_sensor.in_range(temp_in_C-5, temp_in_C+5):
                        module_logger.debug("temperature in bounds: %s vs %s", temp_in_C, self.temp_sensor.value)
                        self.measurement_results["temperature"] = [temp_in_C, "ok", 0, "°C"]
                    else:
                        module_logger.warning("temperature out of bounds: %s vs %s", temp_in_C, self.temp_sensor.value)
                        self.measurement_results["temperature"] = [temp_in_C, "fail", 0, "°C"]
                    if rtc != 1:
                        module_logger.warning("rtc error: %s", rtc)
                        self.measurement_results["RTC"] = [0, "fail", 0, "bool"]
                    else:
                        module_logger.debug("RTC test successful")
                        self.measurement_results["RTC"] = [1, "ok", 0, "bool"]
                    if flash != 1:
                        module_logger.warning("flash error: %s", flash)
                        self.measurement_results["flash test"] = [0, "fail", 0, "bool"]
                    else:
                        module_logger.debug("Flash test successful")
                        self.measurement_results["flash test"] = [1, "ok", 0, "bool"]
                    if switches != 0x00:
                        module_logger.warning("switches error: %s", switches)
                        self.measurement_results["switches"] = [0, "fail", 0, "bool"]
                    else:
                        module_logger.debug("Switches test successful")
                        self.measurement_results["switches"] = [1, "ok", 0, "bool"]
                    if board != 2:
                        module_logger.warning("board error: %s", board)
                        self.measurement_results["board test"] = [0, "fail", 0, "bool"]
                    else:
                        module_logger.debug("Board test successful")
                        self.measurement_results["board test"] = [1, "ok", 0, "bool"]
                    break
                # if there is no data, like timeout
                elif header == b'':
                    module_logger.debug("No data from uart")
                    continue
                else:
                    pass
                    #module_logger.error("Wrong packet header when reading internal test response")
                    #self.measurement_results["signal"] = [0, "fail", 2, "NA"]
            # if there is no hit(break) in this for loop
            else:
                #self.measurement_results["signal"] = [0, "fail", 2, "NA"]
                module_logger.warning("Unable to get any data from uart")
        except:
            raise Exception("Internal test exception")

        return self.measurement_results

    def tear_down(self):
        self.camera_device.close()
        self.serial_port_uart.close()
        self.relay_board.open()
        self.relay_board.open_all_relays()
        self.relay_board.close()


class ManualLCDTest(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        pass

    def run(self):
        good_triggered = False
        bad_triggered = False

        def on_good_action(pin: int):
            nonlocal good_triggered
            good_triggered = True

        def on_bad_action(pin:int):
            nonlocal bad_triggered
            bad_triggered = True

        module_logger.info("Waiting for GOOD/BAD switch:")

        GPIO.add_event_detect(gpios["CONFIRM_GOOD_SWITCH"], GPIO.FALLING, on_good_action, 111)
        GPIO.add_event_detect(gpios["CONFIRM_BAD_SWITCH"],  GPIO.FALLING, on_bad_action, 111)
        while True:
            time.sleep(0.01)
            if good_triggered or bad_triggered:
                module_logger.info("User pressed: %s", "CONFIRM_GOOD_SWITCH" if good_triggered else "CONFIRM_BAD_SWITCH")
                break

        GPIO.remove_event_detect(gpios["CONFIRM_GOOD_SWITCH"])
        GPIO.remove_event_detect(gpios["CONFIRM_BAD_SWITCH"])
        LidOpenCheck()
        return True if good_triggered else False, "Button pressed"

    def tear_down(self):
        pass


class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        module_logger.debug("FinishProcedureTask init")
        self.relay_board = devices.SainBoard16(0x0416, 0x5020, initial_status=0x0000)

    def run(self):
        strips_tester.current_product.test_status = all(strips_tester.current_product.task_results) and len(strips_tester.current_product.task_results)
        if strips_tester.current_product.test_status:
            GPIO.output(gpios["LIGHT_GREEN"], G_HIGH)
            module_logger.debug("LIGHT_GREEN ON")
        else:
            self.relay_board.close_relay(relays["LIGHT_RED"])
            module_logger.debug("LIGHT_RED ON")

        return {"signal":[1, 'ok', 0, 'NA']}

    def tear_down(self):
        self.relay_board.close()


class PrintSticker(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.g = devices.GoDEXG300(port='/dev/ttyUSB0', timeout=3.0)

    def run(self):
        if strips_tester.current_product.test_status:
            test_status = 'PASS'
            inverse = '^L\r'
        else:
            test_status = 'FAIL'
            inverse = '^LI\r'

        label=('^Q10,3\r'
                '^W21\r'
                '^H5\r'
                '^P1\r'
                '^S2\r'
               '^AD\r'
               '^C1\r'
               '^R0\r'
               '~Q+0\r'
               '^O0\r'
               '^D0\r'
               '^E12\r'
               '~R200\r'
               '^XSET,ROTATION,0\r'
               '{}'
               'Dy2-me-dd\r'
               'Th:m:s\r'
               'XRB115,14,3,0,{}\r'
               '{}\r'
               'ATC,13,43,14,14,0,0E,C,0,{}, fw{}\r'
               'ATA,17,13,25,25,0,0E,A,0,{}\r'
               'ATC,12,63,14,14,0,0E,C,0,SN {}\r'
               'E\r').format(inverse,
                            len(str(strips_tester.current_product.serial)),
                            strips_tester.current_product.serial,
                            strips_tester.current_product.type.name,
                            strips_tester.current_product.hw_release,
                            test_status,
                            hex(strips_tester.current_product.serial))
        # wait for open lid
        module_logger.info("Za tiskanje nalepke odpri pokrov")
        while lid_closed():
            time.sleep(0.010)
        self.g.send_to_printer(label)
        return {"signal": [1, 'ok', 0, 'NA']}

    def tear_down(self):
        self.g.close()


class TestTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def run(self):
        connect_to_wifi("STRIPS_GUEST", "yourbestpartner")
        return False, "not implemented yet"

    def tear_down(self):
        pass

# Utils part due to import problems
#########################################################################################
def lid_closed():
    # if lid is opened
    state_GPIO_SWITCH = GPIO.input(gpios.get("START_SWITCH"))
    if state_GPIO_SWITCH:
        #module_logger.error("Lid opened /")
        #strips_tester.current_product.task_results.append(False)
        #strips_tester.emergency_break_tasks = True
        return True
    else:
        #module_logger.debug("Lid closed")
        return False