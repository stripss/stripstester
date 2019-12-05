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
import webbrowser
import subprocess
import queue

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

def connect_to_remote_db():
    # Initiate Remote DB
    try:
        #logger.info("Connecting to RemoteDB: {}...".format(data['db_remote_address']))
        database_instance = pymongo.MongoClient("mongodb://" + data['db_remote_address'], serverSelectionTimeoutMS=1000, connectTimeoutMS=2000)
        database_instance.server_info()
        return database_instance

    except pymongo.errors.ServerSelectionTimeoutError:
        #logger.warning("Connect to RemoteDB failed.")
        pass

    return None

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

    return lgr

# Dictionary factory for SQLite
def dict_from_row(row):
    return dict(zip(row.keys(), row))

def lock_local_db():
    # Wait until local is released
    while data['db_local_lock']:
        pass

    data['db_local_lock'] = True

    return

def release_local_db():
    data['db_local_lock'] = False

    return

# Data handles all custom data of current test device (acts like RAM)
data = {}
logger = initialize_logging(logging.DEBUG)
settings = config_loader.Settings()

# RemoteDB address
data['db_remote_address'] = "172.30.129.19:27017"

# TestDB
#data['db_remote_address'] = "192.168.88.205:82"

# LocalDB initialisation
data['db_local_connection'] = sqlite3.connect("stripstester.db", check_same_thread=False)
data['db_local_connection'].row_factory = sqlite3.Row
data['db_local_cursor'] = data['db_local_connection'].cursor()
data['db_local_lock'] = False  # Global lock for database concurrent writing

# Predefined port
websocket_port = 8000
http_port = 80

# Initiate Remote DB
data['db_connection'] = connect_to_remote_db()

if data['db_connection'] is not None:
    data['db_database'] = data['db_connection']["stripstester"]

    test_devices_col = data['db_database']["test_device"]
    test_info_col = data['db_database']["test_info"]
    test_worker_col = data['db_database']["test_worker"]
    test_calibration_col = data['db_database']["test_calibration"]

else:
    # Set websocket port to 8000 so it will be always the same when accesing trought localhost
    websocket_port = 8000

# Websocket serves as pipeline between GUI and test device
websocket = threading.Thread(target=gui_web.start_server, args=(websocket_port,))
websocket.daemon = True

# HTTPServer serves as backup server if main HTTP Server is not available
httpserver = threading.Thread(target=gui_web.start_http_server, args=(http_port,))
httpserver.daemon = True

# Open webbrowser on RPi
#subprocess.Popen(['chromium-browser','--no-sandbox','http://localhost/index_local.html','--start-fullscreen'])