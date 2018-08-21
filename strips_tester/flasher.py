
import logging

import Flash

import RPi.GPIO as GPIO
import sys

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger("strips_tester.stm32_loader")
logger = logging.getLogger("strips_tester.flashthread")

logging.warning('Watch out!')  # will print a message to the console


GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
module_logger = logging.getLogger(".".join(("strips_tester", __name__)))


flasher = Flash.STM32M0Flasher(18, 22, 3, '/stmConfig.json', 'bin/mcu0')

flasher.flash()
