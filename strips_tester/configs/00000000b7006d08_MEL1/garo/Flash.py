import RPi.GPIO as GPIO
import sys, os

import logging

from . import esptool
#import stmtool as STM
import json
# from esptool import ESPLoader
# from esptool import NotImplementedInROMError
from argparse import Namespace
from . import stm32loader as STM
from strips_tester.abstract_devices import AbstractFlasher
import strips_tester


module_logger = logging.getLogger("strips_tester.garo.flash")

chip_ids = {
    0x412: "STM32 Low-density",
    0x410: "STM32 Medium-density",
    0x414: "STM32 High-density",
    0x420: "STM32 Medium-density value line",
    0x428: "STM32 High-density value line",
    0x430: "STM32 XL-density",
    0x416: "STM32 Medium-density ultralow power line",
    0x411: "STM32F2xx",
    0x413: "STM32F4xx",
    0x440: "STM32F030C8T6"
}

class ESP8266Flasher(AbstractFlasher):
    def __init__(self, port, resetPin, bootPin, baud, wifibinFile='bin/wifi.bin'):
        '''
        :param port: dev/ttyAMA0
        :param resetPin: RST
        :param bootPin: DTR
        :param baud: 115200 max tested
        :param wifibinFile: 'bin/wifi.bin'
        '''
        super().__init__(resetPin, bootPin, retries=5)
        self.esp = None
        self.erase_before_flash = True
        self.wifibinFile = wifibinFile

        initial_baud = min(esptool.ESPLoader.ESP_ROM_BAUD, baud)
        self.esp = esptool.ESPLoader.detect_chip(port, resetPin, bootPin, initial_baud)
        # esp = esp.run_stub()
        if baud > initial_baud:
            try:
                self.esp.change_baud(baud)
            except esptool.NotImplementedInROMError:
                module_logger.warning("WARNING: ROM doesn't support changing baud rate. Keeping initial baud rate %s",
                                      initial_baud)


    def run_flashing(self):
        try:
            dir1 = os.path.join(os.path.dirname(__file__), self.wifibinFile)
            args = Namespace()
            args.flash_size = "detect"
            args.flash_mode = "qio"
            args.flash_freq = "40m"
            args.no_progress = False
            args.no_stub = False
            args.verify = False  # TRUE is deprecated
            args.compress = True
            args.addr_filename = [[int("0x00000", 0), open(dir1, 'relay_board')]]

            if self.erase_before_flash:
                esptool.erase_flash(self.esp, args)
            esptool.write_flash(self.esp, args)

            module_logger.debug("Hard reseting")
            self.esp.hard_reset()
            module_logger.debug("Wifi upload done ")
            return True
        except:
            return False

    def setup(self, reset, dtr):
        # get mac to connect to wifi
        strips_tester.current_product.mac = self.esp.get_mac()
        # already initialized at startup
        #GPIO.setup(reset, GPIO.OUT)
        #GPIO.setup(dtr, GPIO.OUT)

    def close(self):
        if self.esp != None:
            self.esp.close()


class STM32M0Flasher(AbstractFlasher):
    '''
    :param configFile: configuration file for stm flash
    :param UCbinFile:  binary file for stm
    :return:
    '''
    def __init__(self,reset, dtr, retries, configFile='/stmConfig.json', UCbinFile='bin/mcu0'):
        super().__init__(reset, dtr, retries)
        self.cmd = None
        self.UCbinFile = UCbinFile
        self.configFile = configFile
        self.config = UCFlashConfig.load(os.path.dirname(__file__) + configFile)

    def run_flashing(self):
        self.cmd = STM.CommandInterface( self.config)
        self.cmd.open( self.config.port,  self.config.baud)
        module_logger.debug("Open port %s, baud %s",  self.config.port,  self.config.baud)
        module_logger.debug("Open port %s", self.cmd.sp.get_settings())

        try:
            self.cmd.initChip()
            module_logger.debug("Init done")
        except Exception as ex:
            module_logger.debug("Can't init. Ensure that BOOT0 is enabled and reset device, exception: %s", ex)
            return False

        bootversion = self.cmd.cmdGet()
        module_logger.debug("Bootloader version %s", bootversion)
        id = self.cmd.cmdGetID()
        module_logger.debug("Chip id: 0x%s (%s)", id, chip_ids.get(id, "Unknown"))
        dir = os.path.dirname(__file__) + '/' + self.UCbinFile
        # data = map(lambda c: ord(c), file(dir, 'relay_board').read())
        data = open(dir, 'rb').read()

        self.cmd.cmdEraseMemory()
        self.cmd.writeMemory(0x08000000, data)

        self.cmd.unreset()
        return True

    def setup(self, reset, dtr):
        GPIO.setup(reset, GPIO.OUT)
        GPIO.setup(dtr, GPIO.OUT)

    def close(self):
        if self.cmd != None:
            self.cmd.close()


class ESPRomAccess:
    def __init__(self, port, resetPin, bootPin, baudrate):
        # inst = [ESP8266ROM, ESP32ROM]
        initial_baud = min(esptool.ESPLoader.ESP_ROM_BAUD, baudrate)
        self.esp = esptool.ESPLoader.detect_chip(port, resetPin, bootPin, initial_baud)
        if baudrate > initial_baud:
            try:
                self.esp.change_baud(baudrate)
            except esptool.NotImplementedInROMError:
                module_logger.warning("WARNING: ROM doesn't support changing baud rate. Keeping initial baud rate %s", initial_baud)

    def get_mac(self):
        def print_mac(label, mac):
            module_logger.info('%s: %s' % (label, ':'.join(map(lambda x: '%02x' % x, mac))))

        mac = self.esp.read_mac()
        print_mac("MAC", mac)

    def chip_id(self):
        chipid = self.esp.chip_id()
        module_logger.info('Chip ID: 0x%08x' % chipid)

    def close(self):
        self.esp.unreset()