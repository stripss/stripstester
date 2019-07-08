import logging
import RPi.GPIO as GPIO
import json
import os
from collections import OrderedDict
import ast
from strips_tester import utils

import strips_tester

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
        self.test_pass_count = 0
        self.test_failed_count = 0
        self.config_file = os.path.join(os.path.dirname(__file__), "configs", self.get_setting_file_name(), "config.json")
        self.test_dir = os.path.join(os.path.dirname(__file__), "configs", self.get_setting_file_name())
        self.sync_db = True
        self.load(self.config_file)

    def load(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f,object_pairs_hook=OrderedDict)
                self.gpios_settings = data['gpio_settings']
                self.relays_settings = data['relay_settings']
                self.test_device_name = data['test_device_name']
                self.thread_nests = data['thread_nests']
                self.task_execution_order = data['task_execution_order']
                self.critical_event_tasks = data['critical_event_tasks']
                self.custom_data = data['data']

                # GPIO pin finder helper. Example: gpios["START_SWITCH"] -> pin_number:int
                self.gpios = {gpio: self.gpios_settings.get(gpio).get("pin") for gpio in self.gpios_settings}

                # Relay pin finder helper. Example: relays["12V"] -> pin_number:int
                self.relays = {relay: self.relays_settings.get(relay).get("pin") for relay in self.relays_settings}

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




