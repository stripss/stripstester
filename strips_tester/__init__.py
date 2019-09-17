import os
import logging
import sys
from logging.handlers import *
import json
from strips_tester import config_loader
import strips_tester.utils as utils
import multiprocessing
import time
import gui_web
import threading
import pymongo
import pymongo.errors
import sqlite3

# Imported for catching SegmentationFault like errors
import faulthandler
faulthandler.enable()

# test levels == logging levels (ints)
CRITICAL = logging.CRITICAL
ERROR = logging.CRITICAL
WARNING = logging.CRITICAL
INFO = logging.INFO
DEBUG = logging.DEBUG
NOTSET = logging.NOTSET

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

    # Stream module_logger to console
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    lgr.addHandler(stdout_handler)

    # Logging to database (works, but the document count will be large soon)
    #db_handler = MongoHandler(host='172.30.129.19', database_name='stripstester', collection='logs')
    #lgr.addHandler(db_handler)
    return lgr


def dict_from_row(row):
    return dict(zip(row.keys(), row))

# Data handles all custom data of current test device (acts like RAM)
data = {}

data['db_local_connection'] = sqlite3.connect("stripstester.db")
data['db_local_connection'].row_factory = sqlite3.Row
data['db_local_cursor'] = data['db_local_connection'].cursor()

# Initiate Remote DB
try:
    data['db_connection'] = pymongo.MongoClient("mongodb://192.168.88.243:27017/", serverSelectionTimeoutMS=1000, connectTimeoutMS=2000)
    data['db_connection'].server_info()
except pymongo.errors.ServerSelectionTimeoutError:
    data['db_connection'] = None

if data['db_connection'] is not None:
    data['db_database'] = data['db_connection']["stripstester"]

    test_devices_col = data['db_database']["test_device"]
    test_info_col = data['db_database']["test_info"]
    test_worker_col = data['db_database']["test_worker"]

logger = initialize_logging(logging.DEBUG)
current_product = None
settings = config_loader.Settings()

websocket = threading.Thread(target=gui_web.start_server)
websocket.daemon = True
websocket.start()
