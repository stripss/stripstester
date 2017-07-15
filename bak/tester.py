import inspect
import os
import time
import logging
import sys
from strips_tester import config
from strips_tester import CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET
from strips_tester import logger, cursor
from strips_tester.code_reader import CodeReader
try:
    import RPi.GPIO as GPIO
except RuntimeError:
    print("Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")
from strips_tester.config import gpios, TEST_LEVEL



class TestArticle:
    def __init__(self, serial: int=None, type: str=None, hw_release: str=None, variation: str=None, test_status: bool=None, mac_address: int=None):
        self.mac_address = mac_address
        self.test_status = test_status
        self.variation = variation
        self.serial = serial
        self.type = type
        self.hw_release = hw_release


class Task:
    """
    Inherit from this class when creating custom tasks
    accepts level
    """
    def __init__(self, level: int=logging.CRITICAL):
        self.test_level = level
        self.passed = False
        self.result = None

    def set_up(self):
        """Used for environment setup"""
        pass

    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    def tear_down(self):
        """Clean up after task, close connections etc..."""
        pass

    def _execute(self):
        if TEST_LEVEL < self.test_level:
            self.set_up()
            logger.debug("Task: %s setUp", type(self).__name__)
            try:
                self.passed, self.result = self.run()
            except Exception as ex:
                logger.exception("Task crashed with Exception: %s", ex)
                self.passed = False
                self.result = str(ex)
            if self.passed:
                logger.debug("Task: %s run and PASSED with result: %s", type(self).__name__, self.result)
            else:
                logger.debug("Task: %s run and FAILED with result: %s", type(self).__name__, self.result)
            self.tear_down()
            logger.debug("Task: %s tearDown", type(self).__name__)
        else:
            logger.info("Task: %s was NOT executed because test level is too high", type(self).__name__)

    def set_level(self, level:int):
        self.test_level = level


def start_test_device():
    initialize_gpios()
    while True:
        if "START_SWITCH" in gpios:
            wait_for_start_switch()
        else:
            logger.info("START_SWITCH not defined in config.py!")
        success = run_custom_tasks()
        if success:
            GPIO.output(gpios.get("GREEN_LED").get("pin"), True)
            logger.debug("Test SUCCESSFUL!")
            GPIO.wait_for_edge(gpios.get("CONFIRM_SWITCH").get("pin"), GPIO.RISING)
            GPIO.output(gpios.get("GREEN_LED").get("pin"), False)

        else:
            GPIO.output(gpios.get("RED_LED").get("pin"), True)
            logger.debug("Test FAILED!")
            GPIO.output(gpios.get("RED_LED").get("pin"), False)


def initialize_gpios():
    GPIO.setmode(GPIO.BOARD)
    # GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(True)

    for gpio in gpios:
        GPIO.setup(gpio.get("pin"), gpio.get("direction"), initial=gpio.get("initial"))

    # start flashing indication
    for i in range(4):
        led_on()
        time.sleep(0.2)
        led_off()
        time.sleep(0.2)


# blocks until rising edge on START_SWITCH
def wait_for_start_switch():
    if "START_SWITCH" in gpios:
        GPIO.wait_for_edge(gpios.get("START_SWITCH").get("pin"), GPIO.RISING)


def run_custom_tasks():
    test_outcomes = []
    for CustomTask in config.tasks_execution_order:
        custom_task = CustomTask()
        custom_task._execute()
        test_outcomes.append(custom_task.passed)
    return all(test_outcomes)


def wait_for_codereader():
    pass


def led_on():
    if "GREEN_LED" in gpios:
        GPIO.output(gpios.get("GREEN_LED").get("pin"), True)
    else:
        logger.info("GREEN_LED not defined in config.py!")


def led_off():
    if "GREEN_LED" in gpios:
        GPIO.output(gpios.get("GREEN_LED").get("pin"), False)
    else:
        logger.info("GREEN_LED not defined in config.py!")


if __name__ == "__main__":
    parameter = str(sys.argv[1])
    logger.info("Starting tester ...")
    start_test_device()
