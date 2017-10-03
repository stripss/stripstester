import os
import logging
import sys
from logging.handlers import RotatingFileHandler
import sqlite3
import json
import postgr

import config

VERSION = '0.0.1'

# test levels == logging levels (ints)
CRITICAL = logging.CRITICAL
ERROR = logging.CRITICAL
WARNING = logging.CRITICAL
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

# PACKAGE_NAME = __name__


def initialize_logging(level: int = logging.INFO):
    lgr = logging.getLogger(name=__name__)
    lgr.setLevel(level)
    # logging.basicConfig(level=logging.DEBUG)
    # create a logging format
    formatter = logging.Formatter('%(asctime)s %(levelname)s - %(name)s - %(message)s')
    # create handlers
    logs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "logs")

    file_handler = RotatingFileHandler(filename=os.path.join(logs_path, "tester.log"), encoding="utf-8", maxBytes=12345678, backupCount=100)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    lgr.addHandler(file_handler)

    file_handler2 = RotatingFileHandler(filename=os.path.join(logs_path, "tester_debug.log"), encoding="utf-8", maxBytes=12345678, backupCount=100)
    file_handler2.setLevel(level)
    file_handler2.setFormatter(formatter)
    lgr.addHandler(file_handler2)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    lgr.addHandler(stdout_handler)

    # db_handler = logging. # todo database logging handler
    return lgr


class TestnaConfig:
    def __init__(self):
        self.testna_name = '000000'
        self.product = 'NA'
        self.type = 0000
        self.variant = 'NA'
        self.hw_release = 'v0.0'
        self.desc = 'NA'
        self.hw_release = "v0.0"
        self.product_notes = "NA"
        self.employee = 'Strips'
        self.host = '10.48.253.129'
    @classmethod
    def load(cls, file_path):
        conf = cls()
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
            conf.product = data['product']
            conf.type = data['type']
            conf.variant = data['variant']
            conf.hw_release = data['hw_release']
            conf.desc = data['desc']
            conf.product_notes = data['product_notes']
            conf.testna_name = data['testna_name']
            conf.employee = data['employee']
            conf.host = data['host']
        return conf

    def save(self, file_path):
        data = {
            'testna_name': self.testna_name,
            'product': self.product,
            'type': self.type,
            'variant': self.variant,
            'hw_release': self.hw_release,
            'desc': self.desc,
            'product_notes': self.product_notes,
            'employee': self.worker,
            'host': self.host
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.name is not None and self.product is not None


logger = initialize_logging(logging.DEBUG)
LOGGER = logger
current_product = None
CPU_SERIAL = config.getserial()

config_file = os.path.split(os.path.dirname(__file__))[0] + "/config/sw_" + str(CPU_SERIAL) + ".json"
testna_desc = TestnaConfig.load(config_file)

db = postgr.TestnaDB(testna_desc.host)

