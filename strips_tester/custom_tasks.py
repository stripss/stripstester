import logging
import sys
import time

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
from garo import Flash, garo_uart_mitm
from datetime import datetime
import numpy as np

module_logger = logging.getLogger(".".join((strips_tester.PACKAGE_NAME, __name__)))

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
        module_logger.info("Prepared for reading")
        # global current_product
        raw_scanned_string = self.reader.wait_for_read()
        module_logger.debug("Code read successful: %s", serial)
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
            strips_tester.current_product.variant = "wifi" if GPIO.input(gpios.get("WIFI_PRESENT_SWITCH")) else "basic"
            module_logger.info("Product variant set to: %s", strips_tester.current_product.variant)
        else:
            module_logger.info("START_SWITCH not defined in config.py!")
        return True, "Test started manually with start switch " + strips_tester.current_product.variant


class VoltageTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.vc820 = devices.DigitalMultiMeter(port='/dev/ttyUSB1')
        self.mesurement_delay = 0.2

    def run(self) -> (bool, str):
        # Vc
        self.relay_board.close_relay(relays["Vc"])
        time.sleep(self.mesurement_delay)
        time.sleep(0.9)  # additional delay for multimeter to figure out proper auto range
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["Vc"])
        if dmm_value.numeric_val and 13.5 < dmm_value.numeric_val < 16.5:
            module_logger.debug("Vc looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("Vc is out of bounds: %sV", dmm_value.val)
            self.tear_down()
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        # 12V
        self.relay_board.close_relay(relays["12V"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["12V"])
        if dmm_value.numeric_val and 11 < dmm_value.numeric_val < 13:
            module_logger.debug("12V looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("12V is out of bounds: %sV", dmm_value.val)
            self.tear_down()
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        # 5V
        self.relay_board.close_relay(relays["5V"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["5V"])
        if dmm_value.numeric_val and 4.5 < dmm_value.numeric_val < 5.5:
            module_logger.debug("5V looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("5V is out of bounds: %sV", dmm_value.val)
            self.tear_down()
            raise strips_tester.CriticalEventException("Voltage out of bounds")
        # 3V3
        self.relay_board.close_relay(relays["3V3"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["3V3"])
        if dmm_value.numeric_val and 3.0 < dmm_value.numeric_val < 3.8:
            module_logger.debug("3V3 looks normal, measured: %sV", dmm_value.val)
        else:
            module_logger.error("3V3 is out of bounds: %sV", dmm_value.val)
            self.tear_down()
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
        self.relay_board.close_relay(relays["GND"])
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.relay_board.close_relay(relays["DTR_MCU"])
        self.relay_board.close_relay(relays["RST"])
        time.sleep(1)

    def run(self):
        Flash.flashUC()
        return True, "MCU flash went through"

    def tear_down(self):
        self.relay_board.open_relay(relays["RST"])
        self.relay_board.open_relay(relays["DTR_MCU"])
        self.relay_board.open_relay(relays["UART_MCU_RX"])
        self.relay_board.open_relay(relays["UART_MCU_TX"])
        self.relay_board.open_relay(relays["GND"])
        self.relay_board.hid_device.close()


class UartPingTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.serial_port = garo_uart_mitm.open_mitm(aport="/dev/ttyAMA0", abaudrate=115200)

    def run(self):
        timer = time.time()
        module_logger.debug("Listening for internal ping")
        buffer = bytes(5)
        while time.time() < timer + 10:  # 10 sec timeout
            try:
                resp = self.serial_port.read(64)
                print(resp)
                buffer = buffer[1:] + resp
                print(buffer)
            except:
                raise CmdException("Can't read port or timeout")
            else:
                if buffer == (0x00, 0x04, 0x01, 0x21, 0x10):
                    return True, "Ping intercepted"
                elif resp == 0x79:
                    # ACK
                    CmdException("ACK")
                elif resp == 0x1F:
                    # NACK
                    raise CmdException("NACK")
                else:
                    module_logger.debug("Unknown packet")

        return False, "Not implemented yet"

    def tear_down(self):
        self.serial_port.close()
        self.relay_board.open_relay(relays["UART_MCU_RX"])
        self.relay_board.open_relay(relays["UART_MCU_TX"])
        self.relay_board.hid_device.close()


class InternalTest(Task):
    def __init__(self):
        super().__init__(strips_tester.CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        # self.vc820 = devices.DigitalMultiMeter(port='/dev/ttyUSB1')
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.serial_port = garo_uart_mitm.open_mitm(aport="/dev/ttyAMA0", abaudrate=115200)
        self.camera_device = devices.CameraDevice("/strips_tester_project/garo/cameraConfig.json")
        self.start_t = None

    def _update_crc(self, crc, byte_):
        crc = (crc >> 8) | ((crc & 0xFF) << 8)
        crc ^= byte_ & 0xFF
        crc ^= (crc & 0xFF) >> 4
        crc ^= ((crc & 0x0F) << 8) << 4
        crc ^= ((crc & 0xFF) << 4) << 1
        # print (crc)
        return crc

    def crc(self, data):
        crc = 0
        for c in data:
            crc = self._update_crc(crc, c)
        # change endianess
        return struct.unpack("BB", struct.pack("<H", crc))

    def test_relays(self):
        # before test start
        self.relay_board.close_relay(relays["COMMON"])
        self.relay_board.close_relay(relays["RE1"])
        self.relay_board.close_relay(relays["RE1"])
        dmm_measurement = self.vc820.read()
        if abs(dmm_measurement.numeric_val) < 0.1:
            module_logger.debug("Open Voltage ok: %s ", dmm_measurement.numeric_val)
        else:
            module_logger.error("Open Voltage fail: %s ", dmm_measurement.numeric_val)
        time.sleep()


    def run(self):
        test_passed = False
        try:
            module_logger.debug("Wait, boot time 5s...")
            time.sleep(5)
            op_code = bytearray([0x01])
            crc_part_1 = self.crc(op_code)[0]
            crc_part_2 = self.crc(op_code)[1]
            self.serial_port.write([0x00, 0x04, int().from_bytes(op_code, "big"), crc_part_1, crc_part_2])
            self.start_t = time.time()
            for i in range(14):
                self.camera_device.take_picture()
                dt = time.time() - self.start_t
                while dt < (i + 1) * 0.1:
                    dt = time.time() - self.start_t
                    time.sleep(0.001)
                module_logger.debug('Took picture %s at %s ms', i, dt)
            self.camera_device.save_img()

            # buffer = bytes(3)
            # test_result = bytearray()
            # while True:
            #     module_logger.debug("Start listening on uart...")
            #     resp = self.serial_port.read(1, timeout=0)
            #     buffer = buffer[1:] + resp
            #     print(buffer)
            #     if buffer[0] == 0x00 and buffer[2] == 0x06:
            #         for b in range(buffer[1]):
            #             test_result.append(self.serial_port.read(1))
            #         if test_result[-2:] == garo_uart_mitm.crc16_ccitt(buffer[1:]+test_result[:-2]):
            #             module_logger.debug("CRC ok")
            #         break
            # temperature_sensor_value = int.from_bytes(test_result[0:2], "big") / 100
            # rtc_status = test_result[2]
            # flash_status = test_result[3]
            #
            # if 0 < temperature_sensor_value < 50:
            #     module_logger.debug("temperature in bounds")
            # else:
            #     module_logger.warning("temperature out of bounds")
            #     test_passed = False
            # if rtc_status > 0:
            #     module_logger.warning("temperature out of bounds")
            #     test_passed = False
            # if flash_status > 0:
            #     module_logger.debug("flash failed")
            #     test_passed = False

        except:
            raise CmdException("Can't read port or timeout")

        return test_passed, ""

    def tear_down(self):
        self.serial_port.close()
        self.relay_board.open_relay(relays["UART_MCU_RX"])
        self.relay_board.open_relay(relays["UART_MCU_TX"])
        self.relay_board.hid_device.close()


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

        module_logger.debug("Waiting for GOOD/BAD switch...")

        GPIO.add_event_detect(gpios["CONFIRM_GOOD_SWITCH"], GPIO.FALLING, on_good_action, 111)
        GPIO.add_event_detect(gpios["CONFIRM_BAD_SWITCH"],  GPIO.FALLING, on_bad_action, 111)
        while True:
            time.sleep(0.01)
            if good_triggered or bad_triggered:
                module_logger.debug("User pressed: %s", "CONFIRM_GOOD_SWITCH" if good_triggered else "CONFIRM_BAD_SWITCH")
                break

        GPIO.remove_event_detect(gpios["CONFIRM_GOOD_SWITCH"])
        GPIO.remove_event_detect(gpios["CONFIRM_BAD_SWITCH"])
        return True if good_triggered else False, "Button pressed"

    def tear_down(self):
        pass

class CameraTest(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.camera_device = devices.CameraDevice("/strips_tester_project/garo/cameraConfig.json")
        self.camera_device.calibrate()

    def run(self):
        if  self.camera_device.take_pictures(5):
            self.camera_device.run_test()
        else:
            module_logger.error("Failed taking pictures")

        return True, "Display test went through"

    def tear_down(self):
        self.camera_device.close()


class FinishProcedureTask(Task):
    def __init__(self):
        module_logger.debug("FinishProcedureTask init")
        super().__init__(strips_tester.ERROR)

    def set_up(self):
        self.relay_board = devices.SainBoard16(0x0416, 0x5020, initial_status=0x0000)

    def run(self):
        strips_tester.current_product.test_status = all(strips_tester.current_product.task_results) and len(strips_tester.current_product.task_results)
        if strips_tester.current_product.test_status:

            module_logger.debug("Test SUCCESSFUL!")

        else:
            module_logger.debug("Tests FAILED!")
            for i in range(7):
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
        label_params = (strips_tester.current_product.product_type,
                        "hw_release",
                        strips_tester.current_product.variant,
                        "mac_address",
                        "PASS" if strips_tester.current_product.test_status else "FAIL")
        module_logger.debug("label_params: %s: ", label_params)
        label = self.g.generate(*label_params)
        module_logger.debug("Printed sticker with label : article_type:%s, hw_release:%s, wifi:%s, mac_address:%s, test_result:%s", *label_params)
        self.g.send_to_printer(label)
        return True, "Sticker printed"

    def tear_down(self):
        self.g.close()


class TestTask(Task):
    def __init__(self):
        super().__init__(strips_tester.ERROR)

    def run(self):

        connect_to_wifi("STRIPS_GUEST", "yourbestpartner")
        # connect_to_wifi("STRIPS_GUEST", "yourbestpartner")

        return False, "not implemented yet"





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
