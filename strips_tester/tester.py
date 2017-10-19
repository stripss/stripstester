import importlib
import logging
import os
import datetime
import sys
# import wifi
import RPi.GPIO as GPIO

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]
import strips_tester
from strips_tester import settings, current_product
import datetime
import config_loader
import postgr
import random

# name hardcoded, because program starts here so it would be "main" otherwise
module_logger = logging.getLogger(".".join(("strips_tester", "tester")))


# def connect_to_wifi(ssid: str, password: str, interface: str = "wlan0", scheme_name: str = "test_scheme", recreate_scheme: bool = False):
#     cell_dict = {}
#     # os.system("sudo ifdown {}".format(interface))
#     os.system("sudo ifup {}".format(interface))
#     for cell in wifi.Cell.all(interface):
#         cell_dict[cell.ssid] = cell
#     if ssid in cell_dict:
#         cell = cell_dict[ssid]
#         if wifi.Scheme.find(interface, scheme_name):
#             scheme = wifi.Scheme.find(interface, scheme_name)
#             module_logger.debug("found scheme")
#             if recreate_scheme:
#                 scheme.delete()
#                 scheme = wifi.Scheme.for_cell(interface, scheme_name, cell, passkey=password)
#                 scheme.save()
#         else:
#             scheme = wifi.Scheme.for_cell(interface, scheme_name, cell, passkey=password)
#             scheme.save()
#             module_logger.debug("created and saved scheme")
#         for i in range(5):
#             try:
#                 module_logger.debug("connect try number: %s", i + 1)
#                 scheme.activate()
#                 break
#             except Exception as e:
#                 module_logger.error("Wifi connection error: %s", e)
#     else:
#         module_logger.error("Wlan network unreachable!")

# settings = strips_tester.settings

class Product:
    def __init__(self, raw_scanned_string: str = None,
                 serial: int = None,
                 product_name: str = None,
                 product_type: int = None,
                 hw_release: str = None,
                 variant: str = None,
                 test_status: bool = None,
                 mac_address: int = None,
                 production_datetime=datetime):
        self.product_name = product_name
        self.product_type = product_type
        self.raw_scanned_string = raw_scanned_string
        self.mac_address = mac_address
        self.test_status = test_status
        self.variant = variant  # "wifi"/"basic"
        self.serial = serial
        self.hw_release = hw_release
        self.production_datetime = production_datetime
        self.task_results = []
        self.tests = {}


class Task:
    """
    Inherit from this class when creating custom tasks
    accepts levelr
    """

    def __init__(self, level: int = logging.CRITICAL):
        self.test_level = level
        self.end = []
        self.passed = []
        self.result = None
        # self.logger = logging.getLogger(".".join(("strips_tester", "tester", __name__)))

    def set_up(self):
        """Used for environment initial_setup"""
        pass

    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    def tear_down(self):
        """Clean up after task, close_relay connections etc..."""
        pass

    def _execute(self, test_level: int):
        self.set_up()
        module_logger.debug("Task: %s setUp", type(self).__name__)

        # { "db_test_type_name1":{ "data": db_val(float)  , "status": str ->ok/fail/signal , "level": 0-4, "unit": str },
        # "db_test_type_name2":{ "data": db_val(float)  , "status": str ->ok/fail/signal , "level": 0-4, "unit": str }}
        ret = self.run()
        # if len(ret) != 5:
        #     raise "Wrong argument length"
        for keys, values in ret.items():
            if keys == "signal":
                if values[1] == "fail" and self.test_level > strips_tester.ERROR:
                    self.end.append(True)
                    self.passed.append(False)
                elif values[1] == "ok":
                    self.passed.append(True)
                else:
                    self.passed.append(False)
                ###########################################################################
            else:
                strips_tester.current_product.tests[keys] = values  # insert test to be written to DB
                if values[1] == "fail" and self.test_level > strips_tester.ERROR:
                    self.end.append(True)
                    self.passed.append(False)
                elif values[1] == 'ok':
                    self.passed.append(True)
                else:
                    self.passed.append(False)
                ##########################################################################
        # normal flow when task is not critical
        result = all(self.passed)
        end = any(self.end)
        if result:
            module_logger.debug("Task: %s run and PASSED with result: %s", type(self).__name__, result)
        else:
            module_logger.debug("Task: %s run and FAILED with result: %s", type(self).__name__, result)

        module_logger.debug("Task: %s tearDown", type(self).__name__)
        self.tear_down()  # normal tear down
        return result, end  # to indicate further testing

    def set_level(self, level: int):
        self.test_level = level


def start_test_device():
    initialize_gpios()
    while True:
        try:
            global task_results
            # strips_tester.current_product.task_results = run_custom_tasks()
            run_custom_tasks()
        except Exception as e:
            module_logger.error("CRASH, PLEASE RESTART PROGRAM! %s", e)
            raise e


def initialize_gpios():
    # GPIO.cleanup()
    GPIO.setmode(GPIO.BOARD)
    # GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for gpio in settings.gpios_settings.values():
        if gpio.get("function") == config_loader.G_INPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"), pull_up_down=gpio.get("pull", GPIO.PUD_OFF))
        elif gpio.get("function") == config_loader.G_OUTPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"), initial=gpio.get("initial", config_loader.DEFAULT_PULL))
        else:
            module_logger.critical("Not implemented gpio function")

    st_state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))
    module_logger.debug("GPIOs initialized")


def run_custom_tasks():
    strips_tester.current_product = Product(product_name=settings.product_name, # inserted in db according to product_name and variant
                                            product_type=settings.product_type, # used to compose product serial number(prefix)
                                            hw_release=settings.product_hw_release,
                                            variant=settings.product_variant)

    custom_tasks = importlib.import_module("configs."+settings.get_setting_file_name()+".custom_tasks")

    for task_name in settings.task_execution_order:
        if settings.task_execution_order[task_name]:
            CustomTask = getattr(custom_tasks, task_name)
            try:
                module_logger.debug("Executing: %s ...", CustomTask)
                custom_task = CustomTask()
                result, end = custom_task._execute(config_loader.TEST_LEVEL)
                strips_tester.current_product.task_results.append(result)
                if end == True:
                    settings.on_critical_event()  # release all hardware, print sticker, etc...
                    break
            # catch code exception and bugs. It shouldn't be for functional use
            except Exception as e:
                module_logger.error(str(e))
                module_logger.exception("Code error -> REMOVE THE BUG")
        else:
            module_logger.debug("Task %s ignored", task_name)
    ## insert into DB
    if all(strips_tester.current_product.task_results) == True:
        module_logger.info("TEST USPEL :)")
    else:
        module_logger.warning("TEST NI USPEL !!! ")

    # check if WriteToDB task is enabled
    #if settings.task_execution_order["WriteToDB"]:
    strips_tester.db.insert(strips_tester.current_product.tests,
                        serial=strips_tester.current_product.serial,
                        name=strips_tester.current_product.product_name,
                        variant=strips_tester.current_product.variant,
                        hw_release=strips_tester.current_product.hw_release,
                        notes="nothing special",
                        production_datetime=strips_tester.current_product.production_datetime,
                        testna=settings.test_device_name,
                        employee=settings.test_device_employee)



if __name__ == "__main__":
    # parameter = str(sys.argv[1])
    module_logger.info("Starting tester ...")
    start_test_device()
