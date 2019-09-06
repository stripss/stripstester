import importlib
import logging
import os
import datetime
import sys
# import wifi
import RPi.GPIO as GPIO
import Colorer
import time


# git password stripsstrips1
sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]
import strips_tester
from strips_tester import settings
import datetime
import config_loader
from strips_tester import gui_web
import threading
import signal
import traceback

# name hardcoded, because program starts here so it would be "main" otherwise
module_logger = logging.getLogger(".".join(("strips_tester", "tester")))

class Task:
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
            self.test_data['end'] = True

    def end_test(self):
        module_logger.error("[StripsTester] Fatal error - force task {} to end." . format(type(self).__name__))
        self.test_data['end'] = True

    def is_product_ready(self, nest_id = 0):  # Product is either untested or good
        if strips_tester.data['exist'][nest_id] and strips_tester.data['status'][nest_id] is not False:
            return True
        else:
            return False

    # Lid of TN (or DUT detection switch)
    def lid_closed(self):
        if strips_tester.settings.thread_nests:
            start_switch = strips_tester.settings.gpios_settings["START_SWITCH_" + str(self.nest_id + 1)].get("pin")
        else:
            start_switch = strips_tester.settings.gpios_settings["START_SWITCH"].get("pin")

        if GPIO.input(start_switch):
            return False
        else:
            return True

    def safety_check(self):
        # Check if lid is closed
        if not self.lid_closed():
            self.end_test()

            if strips_tester.settings.thread_nests:
                gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!", "nest": self.nest_id})
            else:
                for current_nest in range(strips_tester.data['test_device_nests']):
                    gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!", "nest": current_nest})

            return self

    def in_range(self, value, expected, tolerance, percent=True):
        if percent:
            tolerance_min = expected - expected * (tolerance / 100.0)
            tolerance_max = expected + expected * (tolerance / 100.0)
        else:
            tolerance_min = expected - tolerance
            tolerance_max = expected + tolerance

        if value > tolerance_min and value < tolerance_max:
            return True
        else:
            return False

    # Retrieve new serial
    def get_new_serial(self):
        # Get current test device ID
        test_device_data = strips_tester.data['db_database']['test_device'].find_one({"name": strips_tester.settings.test_device_name})

        # Find serial, increase by one, otherwise set new count
        try:
            serial_number = test_device_data['serial'] + 1
        except (IndexError, KeyError):
            serial_number = 1

        # Update DB
        strips_tester.data['db_database']['test_device'].update_one({'_id': test_device_data['_id']}, {"$set": {'serial': serial_number}}, True)

        return serial_number


    def _execute(self):
        # Prepare measurement variables
        if strips_tester.settings.thread_nests:
            self.nest_id = int((threading.current_thread().name)[-1])
            strips_tester.data['measurement'][self.nest_id][type(self).__name__] = {}
        else:
            for current_nest in range(strips_tester.data['test_device_nests']):
                strips_tester.data['measurement'][current_nest][type(self).__name__] = {}

        try:
            self.set_up()

            self.run()
        except Exception as e:
            self.test_data['end'] = True  # End current task, execute critical tasks
            module_logger.error("[StripsTester] %s - Error in program: (%s)", type(self).__name__, traceback.format_exc())

        # Tear down must be executed after fail to close all devices
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
                    module_logger.error("Executing critical tasks")
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
    end_time = datetime.datetime.utcnow()

    #########    PYMONGO    ##########
    # Find test device ID in database for relationships
    test_device_id = test_devices_col.find_one({"name": strips_tester.settings.test_device_name})

    if test_device_id is not None:  # Check if test device exists in database
        module_logger.info("[StripsTesterDB] Test device {} found in database." . format(strips_tester.settings.test_device_name))

        try:
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
                        #print("Product {} exists with status {}." . format(current_nest,strips_tester.data['status'][current_nest]))

                        # Each nest test counts as one test individually
                        test_info_data = {"datetime": end_time,
                                          "start_test": strips_tester.data['start_time'][current_nest],
                                          "test_device": test_device_id['_id'],
                                          "worker": strips_tester.data['worker_id'],
                                          "comment": strips_tester.data['worker_comment'],
                                          "type": strips_tester.data['worker_type'],
                                          "result": strips_tester.data['status'][current_nest] * 1,
                                          "nest": current_nest,
                                          "measurements": strips_tester.data['measurement'][current_nest]}

                        test_info_col.insert_one(test_info_data)

                        increase_good = strips_tester.data['status'][current_nest] * 1
                        increase_bad = (not strips_tester.data['status'][current_nest]) * 1

                        # Increase worker custom counter data
                        test_worker_col.update_one({"id": strips_tester.data['worker_id']}, {"$inc": {"good": increase_good, "bad": increase_bad}}, True)
                    else:
                        print("Product {} is not tested, so we skip it." . format(current_nest))
        except KeyError as e:
            module_logger.error("[StripsTesterDB] One of the nests ({}) have not configured start_time!" . format(e))

    # Lets print good tested today
    strips_tester.data['good_count'] = test_info_col.find({"test_device": test_device['_id'], "result": 1}).count()
    strips_tester.data['bad_count'] = test_info_col.find({"test_device": test_device['_id'], "result": 0}).count()

    date_at_midnight = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0))

    strips_tester.data['good_count_today'] = test_info_col.find({"test_device": test_device['_id'], "result": 1, "datetime": {"$gt": date_at_midnight}}).count()
    strips_tester.data['bad_count_today'] = test_info_col.find({"test_device": test_device['_id'], "result": 0, "datetime": {"$gt": date_at_midnight}}).count()

    # Lets print good tested today

    try:
        strips_tester.data['good_count_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
        strips_tester.data['bad_count_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']

        gui_web.send({"command": "count_custom", "good_count_custom": strips_tester.data['good_count_custom'], "bad_count_custom": strips_tester.data['bad_count_custom']})
    except Exception:
        pass

    try:
        # Get date at midnight of last test (might not be this test because no products can be tested)
        strips_tester.data['today_date'] = datetime.datetime.combine(test_info_col.find({"test_device": test_device['_id']}).sort('_id', -1).limit(1)[0]['datetime'], datetime.time(0))
    except IndexError:
        strips_tester.data['today_date'] = date_at_midnight

    gui_web.send({"command": "count", "good_count": strips_tester.data['good_count'], "bad_count": strips_tester.data['bad_count'], "good_count_today": strips_tester.data['good_count_today'],
                   "bad_count_today": strips_tester.data['bad_count_today']})

    # last test -> date of TN last test (also if no products tested)
    # today_date -> date at midnight of last product tested

    # Update counter
    strips_tester.data['db_database']['test_count'].update_one({"test_device": test_device_id['_id']}, {"$set": {"good": strips_tester.data['good_count'],"bad": strips_tester.data['bad_count'],"good_today": strips_tester.data['good_count_today'],
                                                                                                          "bad_today": strips_tester.data['bad_count_today'], "last_test": end_time, "today_date": strips_tester.data['today_date']}}, True)

    # increase worker count by one
    # send custom

    strips_tester.data['lock'].release()


if __name__ == "__main__":
    # parameter = str(sys.argv[1])  # We use that if we want to provide extra parameters

    module_logger.info("Starting StripsTester ...")
    initialize_gpios()

    # Get info about test device based on its name. This happens only once

    test_devices_col = strips_tester.data['db_database']["test_device"]
    test_info_col = strips_tester.data['db_database']["test_info"]
    test_worker_col = strips_tester.data['db_database']["test_worker"]

    # Find test device in StripsTester database based on its name
    test_device = test_devices_col.find_one({'name': strips_tester.settings.test_device_name})

    if test_device is not None:
        module_logger.info("[StripsTesterDB] Test device {} found in database!" . format(test_device['name']))

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
        strips_tester.data['worker_comment'] = test_device['worker_comment']

        try:
            strips_tester.data['good_count_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
            strips_tester.data['bad_count_custom'] = test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']
        except Exception:
            strips_tester.data['good_count_custom'] = 0
            strips_tester.data['bad_count_custom'] = 0
    else:
        module_logger.info("[StripsTesterDB] Test device '{}' not found in database. Please add it manually." . format(strips_tester.settings.test_device_name))

        while True:  # Wait forever
            time.sleep(1)

    try:
        strips_tester.settings.thread_nests
    except KeyError:
        strips_tester.settings.thread_nests = False

    strips_tester.data['lock'] = threading.Lock()

    if strips_tester.settings.thread_nests:
        module_logger.info("[StripsTester] Nests are THREADED. Each nest in seperate thread start.")
        # Multiple instances or threads. Global lock is required so the shared variables are not overwritten

        threads = []

        for thread in range(strips_tester.data['test_device_nests']):
            threads.append(threading.Thread(target=start_test_device, name="tester" + str(thread)))
            threads[-1].daemon = True
            threads[-1].start()

        for thread in range(strips_tester.data['test_device_nests']):
            threads[thread].join()
    else:
        module_logger.info("[StripsTester] Nests are non THREADED. Normal start.")

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
