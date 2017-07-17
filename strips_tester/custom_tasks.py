import logging
import sys
import time
import multiprocessing

import serial
import struct
import wifi
import RPi.GPIO as GPIO
import devices
from config import *
# sys.path.append("/strips_tester_project/garo/")
from garo.stm32loader import CmdException
# from strips_tester import *
import strips_tester
from tester import Task, Product, connect_to_wifi
from garo import Flash
from datetime import datetime
import numpy as np

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

# You may set global test level and logging level in config.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)


class BarCodeReadTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)


    def set_up(self):
        self.reader = devices.Honeywell1400(path="/dev/hidraw1", max_code_length=50)

    def run(self) -> (bool, str):
        module_logger.info("Prepared for reading matrix code:")
        # global current_product
        raw_scanned_string = self.reader.wait_for_read()
        module_logger.info("Code read successful")
        strips_tester.current_product.raw_scanned_string = raw_scanned_string
        strips_tester.current_product.parse_2017_raw_scanned_string(raw_scanned_string)
        module_logger.debug("%s", strips_tester.current_product)
        # TODO SHRANI V BAZO

        return True, "Code read successful: " + str(serial)

    def tear_down(self):
        pass


class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def run(self) -> (bool, str):
        if "START_SWITCH" in gpios_config:
            module_logger.info("Waiting for DETECT_SWITCH...")
            # todo
            # while True:
            #     GPIO.wait_for_edge(gpios.get("DETECT_SWITCH"), GPIO.FALLING)
            #     time.sleep(0.1)
            #     if not GPIO.input(gpios.get("DETECT_SWITCH")):
            #         break
            module_logger.debug("Detect switch: %s", GPIO.input(gpios.get("DETECT_SWITCH")))
            module_logger.info("Waiting for START_SWITCH...")
            # prevent switch bounce
            while True:
                GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                time.sleep(0.1)
                if not GPIO.input(gpios.get("START_SWITCH")):
                    module_logger.info("START_SWITCH pressed")
                    break
            strips_tester.current_product.variant = "MVC " + ("wifi" if GPIO.input(gpios.get("WIFI_PRESENT_SWITCH")) else "basic")
            strips_tester.current_product.hw_release = "v1.3"
        else:
            module_logger.info("START_SWITCH not defined in config.py!")
        return True, "Test started manually with start switch " + strips_tester.current_product.variant

    def tear_down(self):
        pass


class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.vc820 = devices.DigitalMultiMeter(port='/dev/ttyUSB1')
        self.mesurement_delay = 0.2

    def run(self) -> (bool, str):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")
        # Vc
        self.relay_board.close_relay(relays["Vc"])
        time.sleep(self.mesurement_delay)
        time.sleep(0.9)  # additional delay for multimeter to figure out proper auto range
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["Vc"])
        if dmm_value.numeric_val and 13.5 < dmm_value.numeric_val < 16.5:
            module_logger.info("Vc looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("Vc is out of bounds: %sV", dmm_value.val)
            strips_tester.current_product.task_results.append(False)
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        # 12V
        self.relay_board.close_relay(relays["12V"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["12V"])
        if dmm_value.numeric_val and 11 < dmm_value.numeric_val < 13:
            module_logger.info("12V looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("12V is out of bounds: %sV", dmm_value.val)
            strips_tester.current_product.task_results.append(False)
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        # 5V
        self.relay_board.close_relay(relays["5V"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["5V"])
        if dmm_value.numeric_val and 4.5 < dmm_value.numeric_val < 5.5:
            module_logger.info("5V looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("5V is out of bounds: %sV", dmm_value.val)
            strips_tester.current_product.task_results.append(False)
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        # 3V3
        self.relay_board.close_relay(relays["3V3"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["3V3"])
        if dmm_value.numeric_val and 3.0 < dmm_value.numeric_val < 3.8:
            module_logger.info("3V3 looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("3V3 is out of bounds: %sV", dmm_value.val)
            strips_tester.current_product.task_results.append(False)
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        return True, "All Voltages in specified ranges"

    def tear_down(self):
        self.vc820.close()
        self.relay_board.hid_device.close()



class FlashWifiModuleTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_WIFI_RX"])
        self.relay_board.close_relay(relays["UART_WIFI_TX"])

    def run(self):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")
        if strips_tester.current_product.variant.lower().startswith("wifi"):
            success = Flash.flash_wifi()
            if success:
                return True, "Flash SUCCESS"
            else:
                return False, "Flash FAILED"
        else:
            module_logger.info("Not wifi product, no flashing needed!")
            return True, "Flash not needed"

    def tear_down(self):
        self.relay_board.open_relay(relays["UART_WIFI_RX"])
        self.relay_board.open_relay(relays["UART_WIFI_TX"])
        self.relay_board.hid_device.close()



class FlashMCUTask(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.open_all_relays()
        self.relay_board.close_relay(relays["GND"])
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.relay_board.close_relay(relays["DTR_MCU"])
        self.relay_board.close_relay(relays["RST"])
        time.sleep(1)

    def run(self):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")
        module_logger.info("Flashing MCU...")
        try:
            Flash.flashUC()
        except Exception as e:
            strips_tester.current_product.task_results.append(False)
            raise strips_tester.CriticalEventException("Flashing FAIL")
        module_logger.info("Flash successful")
        return True, "MCU flash went through"

    def tear_down(self):
        self.relay_board.open_all_relays()
        self.relay_board.close()



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
        self.vc820 = devices.DigitalMultiMeter(port='/dev/ttyUSB1')
        self.serial_port = serial.Serial(
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
        self.camera_device = devices.CameraDevice("/strips_tester_project/garo/cameraConfig.json")
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
        module_logger.info("Testing_relays...")
        relay_tests = []
        self.relay_board.open()

        def assert_voltage(voltage):
            tolerance = voltage * 0.1 if voltage else 0.1
            #print("before vc read")
            dmm_measurement = self.vc820.read()
            #print("after vc read")

            if dmm_measurement.numeric_val and voltage - tolerance < dmm_measurement.numeric_val < voltage + tolerance:
                #print("in if ")
                module_logger.debug("Voltage OK: %s ", dmm_measurement.numeric_val)
                #print("a if ")
            else:
                #print("in el ")
                module_logger.error("Voltage FAIL: %s ", dmm_measurement.numeric_val)
                #print("a el ")
                return False
            return True
        #print(1)
        # Before zero time
        self.relay_board.close_relay(relays["RE1"])
        self.relay_board.close_relay(relays["RE2"])
        module_logger.debug("both open")
        time.sleep(1.2)
        relay_tests.append(assert_voltage(15))
        # Zero time
        #print("before q")
        start_t = queue.get(block=True, timeout=10)
        #print("after q")
        time.sleep(1)
        module_logger.debug("both open ")
        relay_tests.append(assert_voltage(0))
        relay_tests.append(assert_voltage(0))
        relay_tests.append(assert_voltage(0))
        module_logger.debug("last relay wait time: %s", max(0, start_t + 6 + 1 - time.time()))
        time.sleep(max(0, start_t + 6 + 1 - time.time()))
        relay_tests.append(assert_voltage(15))



        # # both open - RE1 measurement
        # self.relay_board.close_relay(relays["RE1"])
        # self.relay_board.open_relay(relays["RE2"])
        # module_logger.debug("both open - RE1 measurement")
        # time.sleep(1.1)
        # relay_tests.append(assert_voltage(15))
        # # both open - RE2 measurement
        # self.relay_board.open_relay(relays["RE1"])
        # self.relay_board.close_relay(relays["RE2"])
        # time.sleep(0.3)
        # module_logger.debug("both open - RE2 measurement")
        # relay_tests.append(assert_voltage(15))
        #
        # start_t = queue.get(block=True, timeout=10)
        #
        # # RE1 ON - RE1 measurement
        # self.relay_board.close_relay(relays["RE1"])
        # self.relay_board.open_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 0 - time.time())))
        # module_logger.debug("elapsed: %ss RE1 ON - RE1 measurement", time.time()-start_t)
        # relay_tests.append(assert_voltage(0))
        # # RE1 ON - RE2 measurement
        # self.relay_board.open_relay(relays["RE1"])
        # self.relay_board.close_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 1 - time.time())))
        # module_logger.debug("elapsed: %ss # RE1 ON - RE2 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(15))
        #
        # # both ON, RE1 measurement
        # self.relay_board.close_relay(relays["RE1"])
        # self.relay_board.open_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 2 - time.time())))
        # module_logger.debug("elapsed: %ss # both ON, RE1 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(0))
        # # both ON, RE2 measurement
        # self.relay_board.open_relay(relays["RE1"])
        # self.relay_board.close_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 3 - time.time())))
        # module_logger.debug("elapsed: %ss both ON, RE2 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(0))
        #
        # # RE2 ON - RE1 measurement
        # self.relay_board.close_relay(relays["RE1"])
        # self.relay_board.open_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 4 - time.time())))
        # module_logger.debug("elapsed: %ss RE2 ON - RE1 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(15))
        # # RE2 ON - RE2 measurement
        # self.relay_board.open_relay(relays["RE1"])
        # self.relay_board.close_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 5 - time.time())))
        # module_logger.debug("elapsed: %ss RE2 ON - RE2 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(0))
        #
        # # both OFF, RE1 measurement
        # self.relay_board.close_relay(relays["RE1"])
        # self.relay_board.open_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 6 - time.time())))
        # module_logger.debug("elapsed: %ss both OFF, RE1 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(15))
        # # both OFF, RE2 measurement
        # self.relay_board.open_relay(relays["RE1"])
        # self.relay_board.close_relay(relays["RE2"])
        # time.sleep(max((0, start_t + 7 - time.time())))
        # module_logger.debug("elapsed: %ss both OFF, RE2 measurement", time.time() - start_t)
        # relay_tests.append(assert_voltage(15))
        #print("before cl")
        self.relay_board.close()
        #print("aftr cl")

        queue.put(all(relay_tests))
        #print("aftr qput")
        return all(relay_tests)

    def run(self):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")
        internal_tests = []
        try:
            queue = multiprocessing.Queue()
            relay_process = multiprocessing.Process(target=self.test_relays, args=(queue,))
            self.relay_board.close()  #  can't pass relay board to other process so we close it here and reopen in relay process
            relay_process.start()
            module_logger.debug("Wait, boot time 3.5s...")
            time.sleep(4)
            op_code = bytearray([0x06])
            crc_part_1, crc_part_2 = self.crc(op_code)
            self.serial_port.write(bytes([0x00, 0x04, int().from_bytes(op_code, "big"), crc_part_1, crc_part_2]))
            # self.serial_port.write(bytes([0x00, 0x04, 0x06, 0xC6, 0x60]))  # full start_test packet
            module_logger.info("Testing segment display...")

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
            module_logger.info("Input button sequence...")
            self.camera_device.save_img()
            internal_tests.append(self.camera_device.compare_bin_shift(14))
            #internal_tests.append(self.camera_device.compare_bin(14))

            payload = bytearray()
            module_logger.debug("Start listening on uart...")
            for try_number in range(40):
                module_logger.debug("Trying to read header \x00")
                header = self.serial_port.read(1)
                if header == b'\x00':
                    module_logger.debug("Receiving test results...")
                    message_length = self.serial_port.read(1)
                    module_logger.debug("Message length: %s: ", message_length)
                    for i in range(int().from_bytes(message_length, "big") -1):
                        payload.extend(self.serial_port.read(1))
                    module_logger.debug("payload: %s", payload)

                    msg_type, keyboard, temperature, rtc, flash, switches, board, crc1, crc2= struct.unpack("<BHHBBBBBB", payload)
                    # #print(crc1, crc2)
                    # #print(self.crc(reversed(message_length+payload[:-2])))
                    # #print(self.crc(message_length+payload[:-2]))

                    if keyboard == 0xb03b: #0x8030:
                        module_logger.info("keyboard ok")
                        internal_tests.append(True)
                    else:
                        module_logger.warning("keyboard error: %s", hex(keyboard))
                        internal_tests.append(False)

                    if 800 < temperature < 2500:
                        module_logger.info("temperature in bounds: %s", temperature)
                        internal_tests.append(True)
                    else:
                        module_logger.warning("temperature out of bounds: %s", temperature)
                        internal_tests.append(False)
                    if rtc != 1:
                        module_logger.warning("rtc error: %s", rtc)
                        internal_tests.append(False)
                    else:
                        module_logger.info("RTC test successful")
                        internal_tests.append(True)
                    if flash != 1:
                        module_logger.warning("flash error: %s", flash)
                        internal_tests.append(False)
                    else:
                        module_logger.info("Flash test successful")
                        internal_tests.append(True)
                    if switches != 0x06:
                        module_logger.warning("switches error: %s", switches)
                        internal_tests.append(False)
                    else:
                        module_logger.info("Switches test successful")
                        internal_tests.append(True)
                    if board != 2:
                        module_logger.warning("board error: %s", board)
                        internal_tests.append(False)
                    else:
                        module_logger.info("Board test successful")
                        internal_tests.append(True)
                    break
                # if there is no data, like timeout
                elif header == b'':
                    module_logger.debug("No data from uart")
                    continue
                else:
                    module_logger.error("Wrong packet header when reading internal test response")
                    internal_tests.append(False)
            # if there is no hit(break) in this for loop
            else:
                internal_tests.append(False)
                module_logger.warning("Unable to get any data from uart")
        except:
            raise Exception("Internal test exception")
        #print("before join")
        relay_process.join(timeout=30)
        #print("after join")
        result = queue.get()
        #print("result", result)
        if result == False:
            module_logger.warning("Relay error ")
            internal_tests.append(False)
        else:
            module_logger.info("Relay test successful")
            internal_tests.append(True)

        #internal_tests.append(queue.get())
        module_logger.debug("Internal tests :%s ", internal_tests)
        return all(internal_tests), ""
        #return True, "All tests passed"

    def tear_down(self):

        self.camera_device.close()
        self.vc820.close()
        self.serial_port.close()
        self.relay_board.open()
        self.relay_board.open_all_relays()
        self.relay_board.close()



class ManualLCDTest(Task):

    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        pass

    def run(self):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")
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
        return True if good_triggered else False, "Button pressed"

    def tear_down(self):
        pass


class FinishProcedureTask(Task):
    def __init__(self):
        module_logger.debug("FinishProcedureTask init")
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.relay_board = devices.SainBoard16(0x0416, 0x5020, initial_status=0x0000)

    def run(self):
        strips_tester.current_product.test_status = all(strips_tester.current_product.task_results) and len(strips_tester.current_product.task_results)
        if strips_tester.current_product.test_status:

            module_logger.info("Test SUCCESSFUL!")

        else:
            #print(22, GPIO.input(gpios["START_SWITCH"]))
            module_logger.error("Tests FAILED!")
            #print(22, GPIO.input(gpios["START_SWITCH"]))
            for i in range(7):
                #print(22,GPIO.input(gpios["START_SWITCH"]))
                if GPIO.input(gpios["START_SWITCH"]):
                    module_logger.debug("Lid opened /")
                    return True, "finished, lid opened"
                self.relay_board.close_relay(relays["LED_RED"])
                time.sleep(0.3)
                self.relay_board.open_relay(relays["LED_RED"])
                time.sleep(0.3)
        module_logger.info("Open lid and remove product.")
        GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.RISING)
        module_logger.debug("Lid opened")
        return True, "finished"

    def tear_down(self):
        self.relay_board.hid_device.close()


class PrintSticker(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.g = devices.GoDEXG300(port='/dev/ttyUSB0', timeout=3.0)

    def run(self):
        # label_params = (strips_tester.current_product.product_type,
        #                 "hw_release",
        #                 strips_tester.current_product.variant,
        #                 "mac_address",
        #                 "PASS" if strips_tester.current_product.test_status else "FAIL")
        label_params = (strips_tester.current_product.product_type,
                        strips_tester.current_product.hw_release,
                        strips_tester.current_product.variant,
                        strips_tester.current_product.serial,
                        "PASS" if strips_tester.current_product.test_status else "FAIL")
        module_logger.debug("label_params: %s: ", label_params)
        label = self.g.generate(*label_params)
        module_logger.info("Printed sticker with label : article_type:%s, hw_release:%s, wifi:%s, mac_address:%s, test_result:%s", *label_params)
        self.g.send_to_printer(label)
        return True, "Sticker printed"

    def tear_down(self):
        self.g.close()



class TestTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def run(self):
        if GPIO.input(gpios["START_SWITCH"]):
            module_logger.error("Lid opened /")
            raise strips_tester.CriticalEventException("Lid opened Exception")

        connect_to_wifi("STRIPS_GUEST", "yourbestpartner")
        # connect_to_wifi("STRIPS_GUEST", "yourbestpartner")

        return False, "not implemented yet"

    def tear_down(self):
        pass





# self.test_voltages,
# self.connect_uart,
# self.flash_wifi_module,
# self.flash_mcu,
# self.test_ping,
# self.get_self_test_report,
# self.test_segment_screen,
# self.test_leds,
# self.test_buttons,
# self.test_relay,
# self.test_slider,
# self.print_sticker,
# self.test_wifi_connect,
# self.test_voltages,
# )
