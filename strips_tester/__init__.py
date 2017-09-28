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
        self.name = '000000'
        self.product = 'NA'
        self.desc = 'NA'
        self.saop = 0000
        self.worker = 'Strips'
        self.host = '10.48.253.129'
    @classmethod
    def load(cls, file_path):
        conf = cls()
        conf_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(conf_path):
            with open(conf_path, 'r') as f:
                data = json.load(f)
            conf.name = data['testna name']
            conf.product = data['product']
            conf.desc = data['desc']
            conf.saop = data['saop']
            conf.worker = data['worker']
            conf.host = data['host']
        return conf

    def save(self, file_path):
        data = {
            'testna name': self.name,
            'product': self.product,
            'desc': self.desc,
            'saop': self.saop,
            'worker': self.worker,
            'host': self.host
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.name is not None and self.product is not None


def getserial():
  # Extract serial from cpuinfo file
  cpuserial = "0000000000000000"
  try:
    f = open('/proc/cpuinfo','r')
    for line in f:
      if line[0:6]=='Serial':
        cpuserial = line[10:26]
    f.close()
  except:
    cpuserial = "ERROR000000000"
  return cpuserial


logger = initialize_logging(logging.DEBUG)
LOGGER = logger
current_product = None

config_file = str(getserial())+ ".json"
testna_desc = TestnaConfig.load(config_file)

db = postgr.TestnaDB(testna_desc.host)
db.insert_product_type(p_name=testna_desc.product, description=testna_desc.desc, saop=testna_desc.saop)

