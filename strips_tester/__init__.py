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
        self.name = 'Testna2'
        self.product = 'MVC basic'
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
            conf.worker = data['worker']
            conf.host = data['host']
        return conf

    def save(self, file_path):
        data = {
            'testna name': self.name,
            'product': self.product,
            'worker': self.worker,
            'host': self.host
        }
        with open(file_path, 'w') as f:
            json.dump(data, f)

    def is_complete(self):
        return self.name is not None and self.product is not None


logger = initialize_logging(logging.DEBUG)
LOGGER = logger
current_product = None
emergency_break_tasks = False

testna_desc = TestnaConfig.load("TestnaConfig.json")
db = postgr.TestnaDB(testna_desc.host)
###db.delete_tables() !!!
db.insert_product_type(p_name=testna_desc.product, description="for garo", saop=2353)


class CriticalEventException(Exception):
    def __init__(self, msg: str = ""):
        logger.critical("CriticalEventException exception: %s", msg)


# db_connecton = sqlite3.connect('tester_db')
# cursor = db_connecton.cursor()
# cursor.execute("CREATE TABLE IF NOT EXISTS products (serial INTEGER NOT NULL, type TEXT, PRIMARY KEY (serial))") #todo add columns
# cursor.execute(
#     "CREATE TABLE IF NOT EXISTS test_results (serial INTEGER NOT NULL , datetime NUMERIC, passed BOOLEAN, result TEXT, FOREIGN KEY (serial) REFERENCES "
#     "products(serial))")
# db_connecton.commit()

# c.execute('''CREATE TABLE stocks
#              (date text, trans text, symbol text, qty real, price real)''')
#
# # Insert a row of data
# c.execute("INSERT INTO stocks VALUES ('2006-01-05','BUY','RHAT',100,35.14)")
#
# # Save (commit) the changes
# conn.commit()
