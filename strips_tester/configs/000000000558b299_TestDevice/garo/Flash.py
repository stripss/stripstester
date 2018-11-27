import RPi.GPIO as GPIO
import sys, os
import logging

import glob

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

# ---------------------------------------------------------------------------
class WifiFlashConfig:
    def __init__(self):
        self.baud = 115200
        self.erase_before_flash = False
        self.mode = "qio"
        self.firmware_path = None
        self.port = "/dev/ttyAMA0"
        self.resetPin =6
        self.bootPin = 13
    @classmethod
    def load(cls, file_path):
        conf = cls()
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            conf.port = data['port']
            conf.baud = data['baud']
            conf.mode = data['mode']
            conf.erase_before_flash = data['erase']
            conf.resetPin = data['reset_pin']
            conf.bootPin = data['boot_pin']
        return conf

    def save(self, file_path):
        data = {
            'port': self.port,
            'baud': self.baud,
            'mode': self.mode,
            'erase': self.erase_before_flash,
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.firmware_path is not None and self.port is not None

# ---------------------------------------------------------------------------
# DTO between GUI and flashing thread
class UCFlashConfig:
    def __init__(self):
        self.baud = 115200
        self.erase_before_flash = False
        self.mode = "qio"
        self.firmware_path = None
        self.port = "/dev/ttyAMA0"
        self.resetPin =6
        self.bootPin = 13
    @classmethod
    def load(cls, file_path):
        conf = cls()
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            conf.port = data['port']
            conf.baud = data['baud']
            conf.mode = data['mode']
            conf.erase_before_flash = data['erase']
            conf.resetPin = data['reset_pin']
            conf.bootPin = data['boot_pin']
        return conf

    def save(self, file_path):
        data = {
            'port': self.port,
            'baud': self.baud,
            'mode': self.mode,
            'erase': self.erase_before_flash,
            'reset_pin': self.resetPin,
            'boot_pin': self.bootPin,
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.firmware_path is not None and self.port is not None



def flash_wifi(configFile='/wifiConfig.json', wifibinFile='bin/wifi.bin'):
    '''
    :param configFile: configuration file for wifi flash
    :param wifibinFile: binary file for wifi
    :return:
    '''

    config = WifiFlashConfig.load(os.path.dirname(__file__) + configFile)
    module_logger.debug("config: %s, port: %s: ", config, config.port)

    GPIO.setup(config.resetPin,GPIO.OUT)
    GPIO.setup(config.bootPin, GPIO.OUT)

    initial_baud = min(esptool.ESPLoader.ESP_ROM_BAUD, config.baud)
    esp = esptool.ESPLoader.detect_chip(config, initial_baud)
    esp = esp.run_stub()
    if config.baud > initial_baud:
        try:
            esp.change_baud(config.baud)
        except esptool.NotImplementedInROMError:
            module_logger.warning("WARNING: ROM doesn't support changing baud rate. Keeping initial baud rate %s" , initial_baud)

    dir1 = os.path.join(os.path.dirname(__file__), wifibinFile)
    args = Namespace()
    args.flash_size = "detect"
    args.flash_mode = config.mode
    args.flash_freq = "40m"
    args.no_progress = False
    args.no_stub = False
    args.verify = False  # TRUE is deprecated
    args.compress = True
    args.addr_filename = [[int("0x00000", 0), open(dir1, 'relay_board')]]

    if config.erase_before_flash:
        esptool.erase_flash(esp, args)
    esptool.write_flash(esp, args)

    module_logger.debug("Hard reseting")
    esp.hard_reset()
    module_logger.debug("Wifi upload done ")
    return True

# MCU FLASHER
#################################################################
def get_latest_file(path_to_search):
    list_of_files = glob.glob(path_to_search)  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)
    return latest_file


class STM32M0Flasher(AbstractFlasher):
    '''
    :param configFile: configuration file for stm flash
    :param UCbinFile:  binary file for stm
    :return:
    '''
    def __init__(self,reset, dtr, retries, configFile='/stmConfig.json', UCbinFile='bin/mcu0'):
        super().__init__(reset, dtr, retries)
        self.cmd = None
        #self.UCbinFile = get_latest_file('/strips_tester_project/strips_tester/configs/000000005e16aa11_MVC2/garo/bin/mcu*')
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
        self.cmd.close()