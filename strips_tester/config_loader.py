import logging
import RPi.GPIO as GPIO
import json
import os
from collections import OrderedDict
import ast
from strips_tester import utils
import strips_tester
import devices

module_logger = logging.getLogger(".".join(("strips_tester", __name__)))

######## DEFAULT CONSTANTS ########
TEST_LEVEL = logging.NOTSET  # test everything above this level. NOTSET (0) is default and covers all levels
LOGGING_LEVEL = logging.INFO  # log everything above this level. NOTSET (0) is default and covers all levels

G_INPUT = GPIO.IN  #1
G_OUTPUT = GPIO.OUT  #0
G_HIGH = R_CLOSED = 1
G_LOW = R_OPEN = 0
G_PUD_DOWN = GPIO.PUD_DOWN  #21
G_PUD_UP = GPIO.PUD_UP  #22
G_PUD_OFF = GPIO.PUD_OFF  #20
# set desired default pull up/down:
DEFAULT_PULL = G_PUD_UP



class Settings:
    def __init__(self):
        self.cpu_serial = utils.get_cpu_serial()
        self.gpios = None
        self.relays = None
        self.config_file = os.path.join(os.path.dirname(__file__), "configs", self.get_setting_file_name(), "config.json")
        self.custom_config_file = os.path.join(os.path.dirname(__file__), "configs", self.get_setting_file_name(), "custom_config.json")
        self.devices_file = os.path.join(os.path.dirname(__file__), "configs", self.get_setting_file_name(), "devices.json")
        self.sync_db = False
        self.local_db_host = "127.0.0.1"
        self.central_db_host = "not defined"
        self.device_list = {}

        self.load(self.config_file,self.custom_config_file)

    def load(self, file_path, custom_file_path):
        if os.path.exists(file_path):

            # Override file_path if custom profile is there
            if os.path.exists(custom_file_path):
                file_path = custom_file_path

            with open(file_path, 'r') as f:
                data = json.load(f,object_pairs_hook=OrderedDict)
                self.gpios_settings = data['gpio_settings']
                self.relays_settings = data['relay_settings']
                self.product_name = data['product_name']
                self.product_type = data['product_type']
                self.product_variant = data['product_variant']
                self.product_hw_release = data['product_hw_release']
                self.product_description = data['product_description']
                self.product_notes = data['product_notes']
                self.test_device_name = data['test_device_name']
                self.test_device_employee = data['test_device_employee']
                self.central_db_host = data['central_db_host']
                self.local_db_host = data['local_db_host']
                self.task_execution_order = data['task_execution_order']
                self.critical_event_tasks = data['critical_event_tasks']
                # GPIO pin finder helper. Example: gpios["START_SWITCH"] -> pin_number:int
                self.gpios = {gpio: self.gpios_settings.get(gpio).get("pin") for gpio in self.gpios_settings}

                # Relay pin finder helper. Example: relays["12V"] -> pin_number:int
                self.relays = {relay: self.relays_settings.get(relay).get("pin") for relay in self.relays_settings}


    def load_devices(self):
        print("DEVICE MANAGER:")
        # Clear device list for new instance
        self.device_list = {}

        if os.path.exists(self.devices_file):
            with open(self.devices_file, 'r') as f:
                data = json.load(f,object_pairs_hook=OrderedDict)

                for device_name in data:
                    #print(device_name)
                    #print(data[device_name])

                    result = [i for i in data[device_name]]
                    #print(data[device_name][result[0]])

                    #print(result[0])
                    #print(data[device_name][result[0]])

                    try:
                        device = getattr(devices, result[0])

                        try:
                            self.device_list[device_name] = device(*data[device_name][result[0]])
                            print("'{}' loaded successfully!" . format(device_name))

                        except Exception as err:
                            print("Device {} not configured properly: {}".format(device_name, err))

                    except Exception as err:
                        print("Device {} not loaded: {}".format(result[0],err))

    def is_device_loaded(self,device):
        if device in self.device_list:
            return True
        return False





    def reload_tasks(self,file_path, custom_file_path):
        if os.path.exists(file_path):
            print("CLASSIC MODE")
            # Override file_path
            if os.path.exists(custom_file_path):
                file_path = custom_file_path
                print("CUSTOM MODE")

            with open(file_path, 'r') as f:
                data = json.load(f,object_pairs_hook=OrderedDict)
                self.task_execution_order = data['task_execution_order']
                self.critical_event_tasks = data['critical_event_tasks']


    def save(self, file_path):
       #  TODO just do it
        with open(file_path, 'w') as f:
            json.dump({}, f, sort_keys=True, indent=4)

    def get_setting_file_name(self):
        configs_dir = os.path.join(os.path.dirname(__file__), "configs")
        files = os.listdir(configs_dir)

        for i, file in enumerate(files):
            if file.startswith(self.cpu_serial):
                return file


