
import RPi.GPIO as GPIO
import sys, os

import logging

from garo import esptool
#import stmtool as STM
import json
# from esptool import ESPLoader
# from esptool import NotImplementedInROMError
from argparse import Namespace
import garo.stm32loader as STM

logger = logging.getLogger("strips_tester.garo.flash")

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




def gpioInit(config):
    # GPIO.setmode(GPIO.BCM)  # TODO disabled, because we use same mode everywhere else (board)
    GPIO.setup(config.resetPin,GPIO.OUT)
    GPIO.setup(config.bootPin, GPIO.OUT)


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



def flash_wifi(configFile='/wifiConfig.json', wifibinFile='wifi.bin'):
    '''
    :param configFile: configuration file for wifi flash
    :param wifibinFile: binary file for wifi
    :return:
    '''

    config = WifiFlashConfig.load(os.path.dirname(__file__) + configFile)
    logger.debug("config: %s, port: %s: ", config, config.port)
    gpioInit(config)

    initial_baud = min(esptool.ESPLoader.ESP_ROM_BAUD, config.baud)
    esp = esptool.ESPLoader.detect_chip(config, initial_baud)
    esp = esp.run_stub()
    if config.baud > initial_baud:
        try:
            esp.change_baud(config.baud)
        except esptool.NotImplementedInROMError:
            logger.warning("WARNING: ROM doesn't support changing baud rate. Keeping initial baud rate %s" , initial_baud)

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

    logger.debug("Hard reseting")
    esp.hard_reset()
    logger.debug("Wifi upload done ")
    return True


def flashUC(configFile='/stmConfig.json', UCbinFile='mcu0'):
    '''
    :param configFile: configuration file for stm flash
    :param UCbinFile:  binary file for stm
    :return:
    '''
    config = UCFlashConfig.load(os.path.dirname(__file__) + configFile)
    gpioInit(config)

    cmd = STM.CommandInterface(config)
    cmd.open(config.port, config.baud)
    logger.debug( "Open port %s, baud %s" , config.port, config.baud)
    logger.debug( "Open port %s" ,  cmd.sp.get_settings())

    try:
        cmd.initChip()
        logger.debug("Init done")
    except Exception as ex:
        logger.debug("Can't init. Ensure that BOOT0 is enabled and reset device, exception: %s", ex)

    bootversion = cmd.cmdGet()
    logger.debug("Bootloader version %s" , bootversion)
    id = cmd.cmdGetID()
    logger.debug("Chip id: 0x%s (%s)", id, chip_ids.get(id, "Unknown"))
    dir = os.path.dirname(__file__) + '/' + UCbinFile
    # data = map(lambda c: ord(c), file(dir, 'relay_board').read())
    data = open(dir, 'rb').read()

    cmd.cmdEraseMemory()
    cmd.writeMemory(0x08000000, data)

    cmd.unreset()
    cmd.close()

'''
    verify = cmd.readMemory(0x08000000, len(data))
    if(data == verify):
        print "Verification OK"
    else:
        print "Verification FAILED"
        print str(len(data)) + ' vs ' + str(len(verify))
        for i in xrange(0, len(data)):
            if data[i] != verify[i]:
                print hex(i) + ': ' + hex(data[i]) + ' vs ' + hex(verify[i])


        if not conf['write'] and conf['read']:
            rdata = cmd.readMemory(conf['address'], conf['len'])
            file(args[0], 'wb').write(''.join(map(chr,rdata)))

        if conf['go_addr'] != -1:
            cmd.cmdGo(conf['go_addr'])

    finally:
        cmd.releaseChip()
'''