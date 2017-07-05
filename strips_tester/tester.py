import logging
import os

import datetime
import wifi
import config
import RPi.GPIO as GPIO
import strips_tester

module_logger = logging.getLogger(".".join((strips_tester.PACKAGE_NAME, "tester")))


def connect_to_wifi(ssid: str, password: str, interface: str = "wlan0", scheme_name: str = "test_scheme", recreate_scheme: bool = False):
    cell_dict = {}
    # os.system("sudo ifdown {}".format(interface))
    os.system("sudo ifup {}".format(interface))
    for cell in wifi.Cell.all(interface):
        cell_dict[cell.ssid] = cell
    if ssid in cell_dict:
        cell = cell_dict[ssid]
        if wifi.Scheme.find(interface, scheme_name):
            scheme = wifi.Scheme.find(interface, scheme_name)
            module_logger.debug("found scheme")
            if recreate_scheme:
                scheme.delete()
                scheme = wifi.Scheme.for_cell(interface, scheme_name, cell, passkey=password)
                scheme.save()
        else:
            scheme = wifi.Scheme.for_cell(interface, scheme_name, cell, passkey=password)
            scheme.save()
            module_logger.debug("created and saved scheme")
        for i in range(5):
            try:
                module_logger.debug("connect try number: %s", i + 1)
                scheme.activate()
                break
            except Exception as e:
                module_logger.error("Wifi connection error: %s", e)
    else:
        module_logger.error("Wlan network unreachable!")


class Product:
    def __init__(self, raw_scanned_string: str=None,
                 serial: int=None,
                 product_type: str=None,
                 hw_release: str=None,
                 variant: str=None,
                 test_status: bool=None,
                 mac_address: int=None,
                 production_datetime=datetime):
        self.raw_scanned_string = raw_scanned_string
        self.mac_address = mac_address
        self.test_status = test_status
        self.variant = variant  # "wifi"/"basic"
        self.serial = serial
        self.product_type = product_type  # SAOP code
        self.hw_release = hw_release
        self.production_datetime = production_datetime
        self.task_results = []

    def parse_2017_raw_scanned_string(self, raw_scanned_string):
        """ example:
        M 170607 00875 000 04 S 2401877
        M = oznaka za material
        170607 = datum: leto, mesec, dan
        00875 = pet mestna serijska številka – števec, ki se za vsako tiskanino povečuje za 1
        000 = trimestna oznaka, ki se bo v prihodnosti uporabljala za nastavljanje stroja za valno spajkanje, po potrebi pa tudi kaj drugega
        04 = število tiskanin v enem panelu – podatek potrebuje iWare
        S = oznako potrebuje iWare za označevanje SAOP kode
        2401877 =  SAOP koda tiskanine"""
        if not raw_scanned_string:
            logging.error("Not scanned yet!")
        else:
            ss = raw_scanned_string
            self.production_datetime = datetime.datetime.now()
            self.production_datetime = self.production_datetime.replace(year=2000+int(ss[1:3]), month=int(ss[3:5]), day=int(ss[5:7]))
            self.serial = int(ss[7:11])
            self.product_type = ss[-7:]
            # print(self.product_type, self.serial, self.production_datetime)

class Task:
    """
    Inherit from this class when creating custom tasks
    accepts level
    """
    def __init__(self, level: int=logging.CRITICAL):
        self.test_level = level
        self.passed = False
        self.result = None
        self.logger = logging.getLogger(__name__)

    def set_up(self):
        """Used for environment setup"""
        pass

    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    def tear_down(self):
        """Clean up after task, close_relay connections etc..."""
        pass

    def _execute(self, test_level: int):
        if test_level < self.test_level:
            self.set_up()
            self.logger.debug("Task: %s setUp", type(self).__name__)
            try:
                ret = self.run()
                if ret is None or len(ret) != 2:
                    self.logger.error("Implement proper two part return for the Task! %s", type(self).__name__)
                self.passed, self.result = ret
            except strips_tester.CriticalEventException as cee:
                self.tear_down()
                raise strips_tester.CriticalEventException("Re raise exception")

            except Exception as ex:
                self.tear_down()
                self.logger.exception("Task crashed with Exception: %s", ex)
                self.passed = False
                self.result = str(ex)
            if self.passed:
                self.logger.debug("Task: %s run and PASSED with result: %s", type(self).__name__, self.result)
            else:
                self.logger.debug("Task: %s run and FAILED with result: %s", type(self).__name__, self.result)
            self.tear_down()
            self.logger.debug("Task: %s tearDown", type(self).__name__)
        else:
            self.logger.info("Task: %s was NOT executed because test level is too high", type(self).__name__)

    def set_level(self, level: int):
        self.test_level = level


def start_test_device():
    initialize_gpios()
    while True:
        try:
            global task_results
            #strips_tester.current_product.task_results = run_custom_tasks()
            run_custom_tasks()
        except Exception as e:
            module_logger.error("CRASH, PLEASE RESTART PROGRAM! %s", e)
            raise e

def initialize_gpios():
    # GPIO.cleanup()
    GPIO.setmode(GPIO.BOARD)
    # GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(True)
    for gpio in config.gpios_config.values():
        if gpio.get("function") == config.G_INPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"), pull_up_down=gpio.get("pull", GPIO.PUD_OFF))
        elif gpio.get("function") == config.G_OUTPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"), initial=gpio.get("initial", config.DEFAULT_PULL))
        else:
            module_logger.critical("Not implemented gpio function")
    module_logger.debug("GPIOs initialized")


def run_custom_tasks():
    strips_tester.current_product = Product()
    for CustomTask in config.tasks_execution_order:
        try:
            module_logger.debug("Executing: %s ...", CustomTask)
            custom_task = CustomTask()
            custom_task._execute(config.TEST_LEVEL)
            strips_tester.current_product.task_results.append(custom_task.passed)
        except strips_tester.CriticalEventException as cee:
            config.on_critical_event(str(cee))
            strips_tester.current_product.task_results.append(False)
            break
        except Exception as e:
            strips_tester.current_product.task_results.append(False)
            module_logger.error(str(e))


if __name__ == "__main__":
    #parameter = str(sys.argv[1])
    module_logger.info("Starting tester ...")
    start_test_device()
