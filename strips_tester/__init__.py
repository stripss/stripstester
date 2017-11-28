import os
import logging
import sys
from logging.handlers import RotatingFileHandler
import sqlite3
import json
from strips_tester import config_loader
import strips_tester.db
import strips_tester.utils as utils
import multiprocessing
import time


VERSION = '0.0.1'
DB = "default"
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

'''
# LOGGING
################################################################################
# Logger when creating multiple processes
# All write to logger_queue, than listener gets one by one and write them to all handlers
def set_queue_logger():
    queue = multiprocessing.Queue(-1)
    listener = multiprocessing.Process(target=listener_process,
                                       args=(queue, listener_configurer))
    listener.start()

    worker = multiprocessing.Process(target=worker_process,
                                             args=(queue, worker_configurer))
    worker.start()

    return queue

def listener_process(queue, configurer):
    configurer()
    while True:
        try:
            record = queue.get()
            #print(record)
            if record is None:  # We send this as a sentinel to tell the listener to quit.
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)  # No level or filter logic applied - just do it!
        except Exception:
            import sys, traceback
            print('Whoops! Problem:', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)


def listener_configurer():
    root = logging.getLogger('Process logger')
    # stdout_handler = logging.StreamHandler(stream=sys.stdout)
    # f = logging.Formatter('%(asctime)s %(processName)-10s %(name)s %(levelname)-8s %(message)s')
    # stdout_handler.setFormatter(f)
    # root.addHandler(stdout_handler)
    # root.setLevel(logging.DEBUG)

    root.debug('Staring process for queue logger')



def worker_configurer(queue):
    h = logging.handlers.QueueHandler(queue)  # Just the one handler needed
    root = logging.getLogger()
    root.addHandler(h)
    root.setLevel(logging.DEBUG)
    pass


def worker_process(queue, configurer):
    configurer(queue)
    name = multiprocessing.current_process().name
    print('Worker started: %s' % name)
    for i in range(10):
        time.sleep(1)
        logger = logging.getLogger('Relay logger')
        logger.info('from relays')
        logger.debug('from relays')
    print('Worker finished: %s' % name)

    while True:
        time.sleep(5)
'''

logger = initialize_logging(logging.DEBUG)
#logger_queue = set_queue_logger()
current_product = None
settings = config_loader.Settings()






