import logging
import sys
import time

import serial
import wifi
import RPi.GPIO as GPIO
import devices
from config import *
# sys.path.append("/strips_tester_project/garo_flash/")
from garo_flash.stm32loader import CmdException
from strips_tester import *
from tester import task_results, Task, Product, connect_to_wifi
from garo_flash import Flash, garo_uart_mitm

module_logger = logging.getLogger(".".join((PACKAGE_NAME, __name__)))

# You may set global test level and logging level in config.py file
# Tests severity levels matches python's logging levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Failing "CRITICAL" test will immediately block execution of further tests! (and call "on_critical_event()")


# Define tests and task as classes that inheriting from tester.Task
# First param is test level, default is set to CRITICAL
# run method should return test status (True if test passed/False if it failed) and result (value)

current_product = Product()


class BarCodeReadTask(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def set_up(self):
        self.reader = devices.Honeywell1400(path="/dev/hidraw1", max_code_length=50)

    def run(self) -> (bool, str):
        module_logger.info("Prepared for reading")
        serial = self.reader.wait_for_read()
        module_logger.debug("Code read successful: %s", serial)
        # TODO PARSE SERIAL V 3 stvari
        current_product = Product(serial=455)  # todo kreiraj testni produkt
        # TODO SHRANI V BAZO

        return True, "Code read successful: " + str(serial)

    def tear_down(self):
        pass


class StartProcedureTask(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def run(self) -> (bool, str):
        if "START_SWITCH" in gpios_config:
            logger.info("Waiting for DETECT_SWITCH...")
            # todo
            # while True:
            #     GPIO.wait_for_edge(gpios.get("DETECT_SWITCH"), GPIO.FALLING)
            #     time.sleep(0.1)
            #     if not GPIO.input(gpios.get("DETECT_SWITCH")):
            #         break
            logger.debug("Detect switch: %s", GPIO.input(gpios.get("DETECT_SWITCH")))
            logger.info("Waiting for START_SWITCH...")
            # prevent switch bounce
            while True:
                GPIO.wait_for_edge(gpios.get("START_SWITCH"), GPIO.FALLING)
                time.sleep(0.1)
                if not GPIO.input(gpios.get("START_SWITCH")):
                    logger.info("START_SWITCH pressed")
                    break
            current_product.variant = "wifi" if GPIO.input(gpios.get("WIFI_PRESENT_SWITCH")) else "basic"
            logger.info("Product variant set to: %s", current_product.variant)
        else:
            logger.info("START_SWITCH not defined in config.py!")
        return True, "Test started manually with start switch " + current_product.variant


class VoltageTest(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.vc820 = devices.DigitalMultiMeter(port='/dev/ttyUSB1')
        self.mesurement_delay = 0.1

    def run(self) -> (bool, str):
        # Vc
        self.relay_board.close_relay(relays["Vc"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["Vc"])
        if 13.5 < dmm_value.numeric_val < 16.5:
            logger.debug("Vc looks normal, measured: %sV", dmm_value.val)
        else:
            logger.error("Vc is out of bounds: %sV", dmm_value.val)
            # raise CriticalEventException("Voltage out of bounds")
            pass  # todo remove
        # 12V
        self.relay_board.close_relay(relays["12V"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["12V"])
        if 11 < dmm_value.numeric_val < 13:
            logger.debug("12V looks normal, measured: %sV", dmm_value.val)
        else:
            logger.error("12V is out of bounds: %sV", dmm_value.val)
            # raise CriticalEventException("Voltage out of bounds")
            pass  # todo remove
        # 5V
        self.relay_board.close_relay(relays["5V"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["5V"])
        if 4.5 < dmm_value.numeric_val < 5.5:
            logger.debug("5V looks normal, measured: %sV", dmm_value.val)
        else:
            logger.error("5V is out of bounds: %sV", dmm_value.val)
            # raise CriticalEventException("Voltage out of bounds")
            pass  # todo remove
        # 3V3
        self.relay_board.close_relay(relays["3V3"])
        time.sleep(self.mesurement_delay)
        dmm_value = self.vc820.read()
        self.relay_board.open_relay(relays["3V3"])
        if 3.0 < dmm_value.numeric_val < 3.8:
            logger.debug("3V3 looks normal, measured: %sV", dmm_value.val)
        else:
            logger.error("3V3 is out of bounds: %sV", dmm_value.val)
            # raise CriticalEventException("Voltage out of bounds")
            pass  # todo remove
        return True, "All Voltages in specified ranges"

    def tear_down(self):
        self.vc820.close()
        self.relay_board.board.close()


class FlashWifiModuleTask(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_WIFI_RX"])
        self.relay_board.close_relay(relays["UART_WIFI_TX"])

    def run(self):
        if current_product.variant.lower().startswith("wifi"):
            success = Flash.flash_wifi()
            if success:
                return True, "Flash SUCCESS"
            else:
                return False, "Flash FAILED"
        else:
            logger.info("Not wifi product, no flashing needed!")
            return True, "Flash not needed"
    def tear_down(self):
        self.relay_board.open_relay(relays["UART_WIFI_RX"])
        self.relay_board.open_relay(relays["UART_WIFI_TX"])
        self.relay_board.board.close()


class FlashMCUTask(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])

    def run(self):
        Flash.flashUC()
        return True, "MCU flash went through"

    def tear_down(self):
        self.relay_board.open_relay(relays["UART_MCU_RX"])
        self.relay_board.open_relay(relays["UART_MCU_TX"])
        self.relay_board.board.close()


class UartPingTest(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.serial_port = garo_uart_mitm.open_mitm(aport="/dev/ttyAMA0", abaudrate=115200)

    def run(self):
        timer = time.time()
        logger.debug("Listening for internal ping")
        buffer = bytes(5)
        while 1:#todo uncomment time.time() < timer + 10:  # 10 sec timeout
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
                    logger.debug("Unknown packet")

        return False, "Not implemented yet"

    def tear_down(self):
        self.serial_port.close()
        self.relay_board.open_relay(relays["UART_MCU_RX"])
        self.relay_board.open_relay(relays["UART_MCU_TX"])
        self.relay_board.board.close()



class InternalTest(Task):
    def __init__(self):
        super().__init__(CRITICAL)

    def set_up(self):
        self.relay_board = devices.SainBoard16(vid=0x0416, pid=0x5020, initial_status=None, number_of_relays=16)
        self.relay_board.close_relay(relays["UART_MCU_RX"])
        self.relay_board.close_relay(relays["UART_MCU_TX"])
        self.serial_port = garo_uart_mitm.open_mitm(aport="/dev/ttyAMA0", abaudrate=115200)

    def run(self):
        test_passed = True
        try:
            self.serial_port.write((0x00, 0x04, 0x06, 0x21, 0x10))
            buffer = bytes(3)
            test_result = bytearray()
            while True:
                logger.debug("Start listening on uart...")
                resp = self.serial_port.read(1, timeout=0)
                buffer = buffer[1:] + resp
                print(buffer)
                if buffer[0] == 0x00 and buffer[2] == 0x06:
                    for b in range(buffer[1]):
                        test_result.append(self.serial_port.read(1))
                    if test_result[-2:] == garo_uart_mitm.crc16_ccitt(buffer[1:]+test_result[:-2]):
                        logger.debug("CRC ok")
                    break
            temperature_sensor_value = int.from_bytes(test_result[0:2], "big") / 100
            rtc_status = test_result[2]
            flash_status = test_result[3]

            if 0 < temperature_sensor_value < 50:
                logger.debug("temperature in bounds")
            else:
                logger.warning("temperature out of bounds")
                test_passed = False
            if rtc_status > 0:
                logger.warning("temperature out of bounds")
                test_passed = False
            if flash_status > 0:
                logger.debug("flash failed")
                test_passed = False
        except:
            raise CmdException("Can't read port or timeout")

        return test_passed, ""

    def tear_down(self):
        self.serial_port.close()
        self.relay_board.open_relay(relays["UART_MCU_RX"])
        self.relay_board.open_relay(relays["UART_MCU_TX"])
        self.relay_board.board.close()


class PrintSticker(Task):
    def __init__(self):
        super().__init__(ERROR)

    def set_up(self):
        pass

    def run(self):
        g = devices.GoDEXG300()
        label = g.generate("article_type", "release", "wifi", "mac_address", "test_result")
        logger.debug("Printed sticker with label : %s", label)
        g.send_to_printer(label)
        return False, "Not implemented yet"

    def tear_down(self):
        pass


class FinishProcedureTask(Task):
    def __init__(self):
        super().__init__(ERROR)

    def set_up(self):
        pass

    def run(self):
        rb = devices.SainBoard16(0x0416, 0x5020, initial_status=0x0000)
        if all(task_results):
            rb.close_relay(relays["LED_RED"])
            logger.debug("Test SUCCESSFUL!")
            GPIO.wait_for_edge(gpios.get("CONFIRM_GOOD_SWITCH"), GPIO.RISING)
            rb.open_relay(relays["LED_RED"])

        else:
            rb.close_relay(relays["LED_RED"])
            logger.debug("Tests FAILED!")
            rb.open_relay(relays["LED_RED"])
            GPIO.wait_for_edge(gpios.get("CONFIRM_BAD_SWITCH"), GPIO.RISING)

    def tear_down(self):
        pass


class TestTask(Task):
    def __init__(self):
        super().__init__(ERROR)

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
