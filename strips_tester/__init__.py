import os
import logging
import sys
from logging.handlers import RotatingFileHandler
import sqlite3
import json

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]
from strips_tester import config_loader
import strips_tester.gui_server
from strips_tester.gui_server import Server
settings = config_loader.Settings()

VERSION = '0.0.1'
DB = "default"
import multiprocessing
import time
import datetime

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_project.settings")
django.setup()
import strips_tester.utils as utils
# first time check & create admin user
from django.contrib.auth.models import User, Group
from web_project.web_app.models import *

from strips_tester import presets  # ORM preset
from web_project.web_app.models import *
module_logger = logging.getLogger(".".join(("strips_tester", "tester")))

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
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    lgr.addHandler(stdout_handler)

    # db_handler = logging. # todo database logging handler
    return lgr




def check_db_connection():
    DB = 'default'
    # with open(os.devnull, 'wb') as devnull:
    #     response_fl = subprocess.check_call('fping -c1 -t100 192.168.11.15', shell=True)
    #     response_fc = subprocess.check_call('fping -c1 -t100 192.168.11.200', shell=True)
    response_fl = os.system('timeout 0.2 ping -c 1 '+str(settings.local_db_host)+' > /dev/null 2>&1')
    response_fc = os.system('timeout 0.2 ping -c 1 '+str(settings.central_db_host)+' > /dev/null 2>&1')
    if response_fc == 0:
        DB = 'default'
    elif response_fc != 0:
        settings.sync_db = True
        if DB=='default':
            utils.send_email(subject='DB Error', emailText='{}, {}'.format(datetime.datetime.now(), 'Writing to local database!!!'))
            module_logger.warning('Writing to local database!!!'.format(datetime.datetime.now()))
        DB = 'local'
        if response_fl==0:
            pass
        else:
            utils.send_email(subject='Error', emailText='{}, {}'.format(datetime.datetime.now(), 'No database available!!!'))
            module_logger.error('Could not connect to default of local database!!!'.format(datetime.datetime.now()))
            raise 'Could not connect to default of local database'
    return DB


logger = initialize_logging(logging.DEBUG)
#logger_queue = set_queue_logger()
current_product = None

server = Server()
server.Daemon = True
queue = multiprocessing.Queue(0)


