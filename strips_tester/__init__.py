import os
import logging
import sys
from logging.handlers import RotatingFileHandler
import sqlite3

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
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    lgr.addHandler(file_handler)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.setFormatter(formatter)
    lgr.addHandler(stdout_handler)

    # db_handler = logging. # todo database logging handler
    return lgr


logger = initialize_logging(config.LOGGING_LEVEL)
LOGGER = logger
current_product = None


class CriticalEventException(Exception):
    def __init__(self, msg: str = ""):
        logger.critical("CriticalEventException exception: %s", msg)


db_connecton = sqlite3.connect('tester_db')
cursor = db_connecton.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS products (serial INTEGER NOT NULL, type TEXT, PRIMARY KEY (serial))") #todo add columns
cursor.execute(
    "CREATE TABLE IF NOT EXISTS test_results (serial INTEGER NOT NULL , datetime NUMERIC, passed BOOLEAN, result TEXT, FOREIGN KEY (serial) REFERENCES "
    "products(serial))")
db_connecton.commit()

# c.execute('''CREATE TABLE stocks
#              (date text, trans text, symbol text, qty real, price real)''')
#
# # Insert a row of data
# c.execute("INSERT INTO stocks VALUES ('2006-01-05','BUY','RHAT',100,35.14)")
#
# # Save (commit) the changes
# conn.commit()
