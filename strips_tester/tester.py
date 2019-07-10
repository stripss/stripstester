import importlib
import logging
import os
import datetime
import sys
# import wifi
import RPi.GPIO as GPIO
import Colorer
import time

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]
import strips_tester
from strips_tester import settings
import datetime
import config_loader
from strips_tester import gui_web
import threading
import signal

# name hardcoded, because program starts here so it would be "main" otherwise
module_logger = logging.getLogger(".".join(("strips_tester", "tester")))

class Task:
    """
    Inherit from this class when creating custom tasks
    accepts levelr
    """

    def __init__(self):
        self.test_data = {}
        self.test_data['end'] = False

    def set_up(self):
        """Used for environment initial_setup"""
        pass

    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    def tear_down(self):
        """Clean up after task, close_relay connections etc..."""
        pass

    def add_measurement(self, nest_id, measurement_state, measurement_name, measurement_value, measurement_unit = "N/A", end_task = False):
        strips_tester.data['measurement'][nest_id][type(self).__name__][measurement_name] = [measurement_value, measurement_state, measurement_unit]

        if not measurement_state:
            if strips_tester.data['exist'][nest_id]:
                strips_tester.data['status'][nest_id] = False

        #print("[{}] Added values to measurements: {}" . format(type(self).__name__, strips_tester.data['measurement'][nest_id][type(self).__name__]))

        if end_task:
            print("[StripsTester] Fatal error - force task {} to end." . format(type(self).__name__))
            self.test_data['end'] = True

    def end_test(self):
        self.test_data['end'] = True

    def is_product_ready(self, nest_id = 0):
        if strips_tester.data['exist'][nest_id] and strips_tester.data['status'][nest_id] is not False:
            return True
        else:
            return False

    def _execute(self):
        # Prepare measurement variables
        if strips_tester.settings.thread_nests:
            self.nest_id = int((threading.current_thread().name)[-1])
            strips_tester.data['measurement'][self.nest_id][type(self).__name__] = {}
        else:
            for current_nest in range(strips_tester.data['test_device_nests']):
                strips_tester.data['measurement'][current_nest][type(self).__name__] = {}

        try:
            #print("SETUP {}" . format(type(self).__name__))
            self.set_up()

            #print("RUN {}" . format(type(self).__name__))
            self.run()
        except Exception:
            self.test_data['end'] = True
            raise

        #print("TEARDOWN {}" . format(type(self).__name__))
        self.tear_down()

        return self.test_data  # to indicate further testing

def start_test_device():
    while True:
        try:
            run_custom_tasks()

        except Exception as e:
            module_logger.error("CRASH, PLEASE RESTART PROGRAM! %s", e)
            raise e

def initialize_gpios():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)

    for gpio in settings.gpios_settings.values():
        if gpio.get("function") == config_loader.G_INPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"), pull_up_down=gpio.get("pull", GPIO.PUD_OFF))
        elif gpio.get("function") == config_loader.G_OUTPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"), initial=gpio.get("initial", config_loader.DEFAULT_PULL))
        else:
            module_logger.critical("Not implemented gpio function")


def run_custom_tasks():
    reset_data()

    # Run custom tasks with independed timing (because of threads)
    custom_tasks = importlib.import_module("configs." + settings.get_setting_file_name() + ".custom_tasks")
    for task_name in settings.task_execution_order:
        if settings.task_execution_order[task_name]:
            CustomTask = getattr(custom_tasks, task_name)
            try:
                module_logger.debug("Executing: %s ...", CustomTask)
                custom_task = CustomTask()
                test_data = custom_task._execute()

                if test_data['end']:
                    print("EXEUCING CRITICAL TASKS")
                    for task_name in settings.critical_event_tasks:
                        if settings.critical_event_tasks[task_name]:
                            CustomTask = getattr(custom_tasks, task_name)
                            try:
                                module_logger.debug("Executing: %s ...", CustomTask)
                                custom_task = CustomTask()
                                custom_task._execute()
                            except Exception as ee:
                                raise "CRITICAL EVENT EXCEPTION"
                    break

            # catch code exception and bugs. It shouldn't be for functional use
            except Exception as e:
                module_logger.error(str(e))
                module_logger.exception("Code error -> REMOVE THE BUG")
        else:
            module_logger.debug("Task %s ignored", task_name)

    update_database()


def reset_data():
    for current_nest in range(strips_tester.data['test_device_nests']):
        if strips_tester.settings.thread_nests:
            nest_id = threading.current_thread().name
            nest_id = int(nest_id[-1])

            if current_nest != nest_id:
                continue  # Skip current nest if not from this thread

        strips_tester.data['measurement'][current_nest] = {}
        strips_tester.data['exist'][current_nest] = False
        strips_tester.data['status'][current_nest] = -1  # Untested

def update_database():
    strips_tester.data['lock'].acquire()
    end_time = datetime.datetime.now()

    #########    PYMONGO    ##########
    # Find test device ID in database for relationships
    test_device_id = test_devices_col.find_one({"name": strips_tester.settings.test_device_name})

    if test_device_id is not None:  # Check if test device exists in database
        print("[StripsTesterDB] Test device {} found in database." . format(strips_tester.settings.test_device_name))

        #try:
        # Insert new test info because new test has been made
        for current_nest in range(strips_tester.data['test_device_nests']):
            if strips_tester.settings.thread_nests:  # If nests are threaded, update only current nest
                nest_id = int((threading.current_thread().name)[-1])

                if current_nest != nest_id:
                    #print("Nest '{}' is threaded, skip it to '{}'".format(current_nest,nest_id))
                    continue  # Skip current nest if not from this thread

            duration = (end_time - strips_tester.data['start_time'][current_nest]).total_seconds()  # Get start test date
            gui_web.send({"command": "time", "mode": "duration", "nest": current_nest, "value": duration})

            if strips_tester.data['exist'][current_nest]:  # Make test info only if product existed
                if strips_tester.data['status'][current_nest] != -1:
                    print("Product {} exists with status {}." . format(current_nest,strips_tester.data['status'][current_nest]))

                    # Each nest test counts as one test individually
                    test_info_data = {"datetime": end_time,
                                      "start_test": strips_tester.data['start_time'][current_nest],
                                      "test_device": test_device_id['_id'],
                                      "worker": strips_tester.data['worker_id'],
                                      "type": strips_tester.data['worker_type'],
                                      "result": strips_tester.data['status'][current_nest] * 1,
                                      "nest": current_nest,
                                      "measurements": strips_tester.data['measurement'][current_nest]}

                    test_info_data_id = test_info_col.insert_one(test_info_data)

                    #test_data_col = strips_tester.data['db_database']["test_data"]
                    # Insert test data into database by tasks
                    #test_data_data = {"test_info": test_info_data_id.inserted_id,
                    #                  "data": strips_tester.data['measurement'][current_nest]}
                    #test_data_col.insert_one(test_data_data)
                else:
                    print("Product {} is not tested, so we skip it." . format(current_nest))
            #except ExceptioKeyError as e:
            #    raise
            #    #print("[StripsTesterDB] Error -> KeyError ({})" . format(e))

    # Lets print good tested today
    strips_tester.data['good_count'] = test_info_col.find({"test_device": test_device['_id'], "result": 1}).count()
    strips_tester.data['bad_count'] = test_info_col.find({"test_device": test_device['_id'], "result": 0}).count()

    date_at_midnight = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0))

    strips_tester.data['good_count_today'] = test_info_col.find({"test_device": test_device['_id'], "result": 1, "datetime": {"$gt": date_at_midnight}}).count()
    strips_tester.data['bad_count_today'] = test_info_col.find({"test_device": test_device['_id'], "result": 0, "datetime": {"$gt": date_at_midnight}}).count()

    gui_web.send({"command": "count", "good_count": strips_tester.data['good_count'], "bad_count": strips_tester.data['bad_count'], "good_count_today": strips_tester.data['good_count_today'],
                   "bad_count_today": strips_tester.data['bad_count_today']})
    strips_tester.data['lock'].release()


if __name__ == "__main__":
    # parameter = str(sys.argv[1])  # We use that if we want to provide extra parameters

    module_logger.info("Starting StripsTester ...")
    initialize_gpios()

    # Get info about test device based on its name. This happens only once

    test_devices_col = strips_tester.data['db_database']["test_device"]
    test_info_col = strips_tester.data['db_database']["test_info"]

    # Find test device in StripsTester database based on its name
    test_device = test_devices_col.find_one({'name': strips_tester.settings.test_device_name})

    if test_device is not None:
        print("[StripsTesterDB] Test device {} found in database!" . format(test_device['name']))

        strips_tester.data['new_db'] = True
        strips_tester.data['test_device_nests'] = test_device['nests']
        strips_tester.data['exist'] = {}
        strips_tester.data['status'] = {}

        # Prepare data dictionary structure and reset to default values
        strips_tester.data['measurement'] = {}
        strips_tester.data['start_time'] = {}

        # Load counts from DB
        strips_tester.data['good_count'] = test_info_col.find({"test_device": test_device['_id'], "result": 1}).count()
        strips_tester.data['bad_count'] = test_info_col.find({"test_device": test_device['_id'], "result": 0}).count()

        date_at_midnight = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0))

        strips_tester.data['good_count_today'] = test_info_col.find({"test_device": test_device['_id'], "result": 1, "datetime": {"$gt": date_at_midnight}}).count()
        strips_tester.data['bad_count_today'] = test_info_col.find({"test_device": test_device['_id'], "result": 0, "datetime": {"$gt": date_at_midnight}}).count()

        # Retrieve last settings
        strips_tester.data['worker_id'] = test_device['worker_id']
        strips_tester.data['worker_type'] = test_device['worker_type']
    else:
        print("[StripsTesterDB] Test device '{}' not found in database. Please add it manually." . format(strips_tester.settings.test_device_name))
        strips_tester.data['new_db'] = False

        while True:  # Wait forever
            time.sleep(1)

    try:
        strips_tester.settings.thread_nests
    except KeyError:
        strips_tester.settings.thread_nests = False

    strips_tester.data['lock'] = threading.Lock()

    if strips_tester.settings.thread_nests:
        print("[StripsTester] Nests are THREADED. Each nest in seperate thread start.")
        # Multiple instances or threads. Global lock is required so the shared variables are not overwritten

        threads = []

        for thread in range(strips_tester.data['test_device_nests']):
            threads.append(threading.Thread(target=start_test_device, name="tester" + str(thread)))
            threads[-1].daemon = True
            threads[-1].start()

        for thread in range(strips_tester.data['test_device_nests']):
            threads[thread].join()
    else:
        print("[StripsTester] Nests are non THREADED. Normal start.")

        start_test_device()


class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)
