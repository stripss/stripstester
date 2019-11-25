import importlib
import logging
import os
import datetime
import sys
# import wifi
import RPi.GPIO as GPIO
import Colorer
import time
import json

import pymongo.errors

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

    # Prepare and initialize devices, used for this task
    def set_up(self):
        """Used for environment initial_setup"""
        pass

    # Execute task procedure
    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    # Close all running devices in this task
    def tear_down(self):
        """Clean up after task, close_relay connections etc..."""
        pass

    # Add new measurement to database
    def add_measurement(self, nest_id, measurement_state, measurement_name, measurement_value, measurement_unit = "N/A", end_task = False):
        strips_tester.data['measurement'][nest_id][type(self).__name__][measurement_name] = [measurement_value, measurement_state, measurement_unit]

        if not measurement_state:
            if strips_tester.data['exist'][nest_id]:
                strips_tester.data['status'][nest_id] = False

        #print("[{}] Added values to measurements: {}" . format(type(self).__name__, strips_tester.data['measurement'][nest_id][type(self).__name__]))

        if end_task:
            self.test_data['end'] = True

    # End test procedure as fatal error
    def end_test(self):
        module_logger.error("[StripsTester] Fatal error - force task {} to end." . format(type(self).__name__))
        self.test_data['end'] = True

    # Check whether product exists and have no errors to this point during test
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
                for current_nest in range(strips_tester.settings.test_device_nests):
                    gui_web.send({"command": "error", "value": "Pokrov testne naprave je odprt!", "nest": current_nest})

            return self

    # Definition of in_range function for measurements
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
        if strips_tester.data['db_connection'] is not None:
            # Get current test device ID
            test_device_data = strips_tester.data['db_database']['test_device'].find_one({"name": strips_tester.settings.test_device_name})

            # Find serial, increase by one, otherwise set new count
            try:
                serial_number = test_device_data['serial'] + 1
            except (IndexError, KeyError):
                serial_number = 1

            # Update DB
            strips_tester.test_devices_col.update_one({'_id': test_device_data['_id']}, {"$set": {'serial': serial_number}}, True)
        else:  # Retrieve serial number from Local DB
            result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_device''').fetchone()
            # Update global variable with last remote counters

            serial_number = result['serial'] + 1

        strips_tester.data['db_local_cursor'].execute('''UPDATE test_device SET serial = ?''',(serial_number,))
        strips_tester.data['db_local_connection'].commit()
        # Update serial in Local DB

        return serial_number


    # Initiate test procedure for GUI (start counting time, clear screen)
    def start_test(self, nest):
        strips_tester.data['start_time'][nest] = datetime.datetime.utcnow()  # Get start test date
        gui_web.send({"command": "time", "mode": "start", "nest": nest})  # Start count for test

        # Clear GUI
        gui_web.send({"command": "error", "nest": nest, "value": -1})  # Clear all error messages
        gui_web.send({"command": "info", "nest": nest, "value": -1})  # Clear all info messages

        gui_web.send({"command": "semafor", "nest": nest, "value": (0, 1, 0), "blink": (0, 0, 0)})


    def _execute(self):
        # Prepare measurement variables
        if strips_tester.settings.thread_nests:
            self.nest_id = int((threading.current_thread().name)[-1])
            strips_tester.data['measurement'][self.nest_id][type(self).__name__] = {}
        else:
            for current_nest in range(strips_tester.settings.test_device_nests):
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

# Apply variable to memory so the next time test device turn on, this memory will be applied
def save_variable_to_db(name, value):
    try:
        if strips_tester.data['db_connection'] is not None:
            strips_tester.data['db_database']['test_device'].update_one({'name': strips_tester.settings.test_device_name}, {"$push": {'memory.{}' . format(name): value}}, True)

        else:  # Retrieve serial number from Local DB

            # result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_device''').fetchone()
            # # Update global variable with last remote counters
            #
            # serial_number = result['serial'] + 1
            #
            # strips_tester.data['db_local_cursor'].execute('''UPDATE test_device SET serial = ?''',(serial_number,))
            # strips_tester.data['db_connection'].commit()
            # # Update serial in Local DB
            pass
    except Exception as e:
        print(e)
    return

def start_test_device():
    while True:
        try:
            run_custom_tasks()

        except Exception as e:
            module_logger.error("CRASH, PLEASE RESTART PROGRAM! %s", e)
            raise e


# Prepare Raspberry Pi GPIOs to operate as INPUT or OUTPUT
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
    # Reset all data containing measurements to prepare for new test
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

    strips_tester.data['lock'].acquire()
    strips_tester.data['end_time'] = datetime.datetime.utcnow()
    update_database()
    strips_tester.data['lock'].release()


# Reset measurement data and product statuses for next test
def reset_data():
    for current_nest in range(strips_tester.settings.test_device_nests):
        if strips_tester.settings.thread_nests:
            nest_id = threading.current_thread().name
            nest_id = int(nest_id[-1])

            if current_nest != nest_id:
                continue  # Skip current nest if not from this thread

        strips_tester.data['measurement'][current_nest] = {}
        strips_tester.data['exist'][current_nest] = False
        strips_tester.data['status'][current_nest] = -1  # Untested


def update_database():
    try:
        try:
            # Insert new test info because new test has been made
            for current_nest in range(strips_tester.settings.test_device_nests):
                if strips_tester.settings.thread_nests:  # If nests are threaded, update only current nest
                    nest_id = int((threading.current_thread().name)[-1])

                    if current_nest != nest_id:
                        continue  # Skip current nest if not from this thread

                duration = (strips_tester.data['end_time'] - strips_tester.data['start_time'][current_nest]).total_seconds()  # Get start test date
                gui_web.send({"command": "time", "mode": "duration", "nest": current_nest, "value": duration})

                if strips_tester.data['exist'][current_nest]:  # Make test info only if product existed
                    if strips_tester.data['status'][current_nest] != -1:
                        # print("Product {} exists with status {}." . format(current_nest,strips_tester.data['status'][current_nest]))

                        # Increase worker custom counter data (applied to LocalDB)
                        increase_good = strips_tester.data['status'][current_nest] * 1
                        increase_bad = (not strips_tester.data['status'][current_nest]) * 1

                        strips_tester.data['good_custom'] += increase_good
                        strips_tester.data['bad_custom'] += increase_bad

                        # Update Remote DB if available
                        if strips_tester.data['db_connection'] is not None:
                            module_logger.info("[StripsTesterDB] Saving to RemoteDB")
                            # Find test device ID in database for relationships
                            test_device_id = strips_tester.test_devices_col.find_one({"name": strips_tester.settings.test_device_name})['_id']

                            # Each nest test counts as one test individually
                            test_info_data = {"datetime": strips_tester.data['end_time'],
                                              "start_test": strips_tester.data['start_time'][current_nest],
                                              "test_device": test_device_id,
                                              "worker": strips_tester.data['worker_id'],
                                              "comment": strips_tester.data['worker_comment'],
                                              "type": strips_tester.data['worker_type'],
                                              "result": strips_tester.data['status'][current_nest] * 1,
                                              "nest": current_nest,
                                              "measurements": strips_tester.data['measurement'][current_nest]}

                            strips_tester.test_info_col.insert_one(test_info_data)

                            strips_tester.test_worker_col.update_one({"id": strips_tester.data['worker_id']}, {"$inc": {"good": increase_good, "bad": increase_bad}}, True)
                        else:  # Saving to Local DB
                            module_logger.info("[StripsTesterDB] Saving to LocalDB")

                            # Update Local DB test_info
                            strips_tester.data['db_local_cursor'].execute(
                                '''INSERT INTO test_info(datetime, start_test, worker, comment, type, result, nest, measurements) VALUES(?,?,?,?,?,?,?,?)''', (
                                strips_tester.data['end_time'], strips_tester.data['start_time'][current_nest], strips_tester.data['worker_id'],
                                strips_tester.data['worker_comment'], strips_tester.data['worker_type'], strips_tester.data['status'][current_nest] * 1,
                                current_nest, str(json.dumps(strips_tester.data['measurement'][current_nest]))))
                            strips_tester.data['db_local_connection'].commit()
                    else:
                        print("Product {} is not tested, so we skip it.".format(current_nest))
        except KeyError as e:
            module_logger.error("[StripsTesterDB] One of the nests ({}) have not configured start_time!".format(e))

        # last test -> date of TN last test (also if no products tested)
        # today_date -> date at midnight of last product tested
        date_at_midnight = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0))

        if strips_tester.data['db_connection'] is not None:  # RemoteDB is accessible
            test_device_id = strips_tester.test_devices_col.find_one({"name": strips_tester.settings.test_device_name})['_id']

            # Lets print good tested today
            strips_tester.data['good_count'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 1}).count()
            strips_tester.data['bad_count'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 0}).count()

            strips_tester.data['good_count_today'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 1, "datetime": {"$gt": date_at_midnight}}).count()
            strips_tester.data['bad_count_today'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 0, "datetime": {"$gt": date_at_midnight}}).count()

            strips_tester.data['good_custom'] = strips_tester.test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
            strips_tester.data['bad_custom'] = strips_tester.test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']

            try:
                # Get date at midnight of last test (might not be this test because no products can be tested)
                strips_tester.data['today_date'] = datetime.datetime.combine(strips_tester.test_info_col.find({"test_device": test_device['_id']}).sort('_id', -1).limit(1)[0]['datetime'], datetime.time(0))
            except IndexError:
                strips_tester.data['today_date'] = date_at_midnight

            # Update counter
            strips_tester.data['db_database']['test_count'].update_one({"test_device": test_device_id}, {
                "$set": {"good": strips_tester.data['good_count'], "bad": strips_tester.data['bad_count'], "good_today": strips_tester.data['good_count_today'],
                         "bad_today": strips_tester.data['bad_count_today'], "last_test": strips_tester.data['end_time'], "today_date": strips_tester.data['today_date']}}, True)

            # Update Local DB counters, so if connection is lost, count from this number onwards
            strips_tester.data['db_local_cursor'].execute('''UPDATE test_device SET good_count = ?, bad_count = ?, good_count_today = ?, bad_count_today = ? WHERE name = ?''', (
                strips_tester.data['good_count'], strips_tester.data['bad_count'], strips_tester.data['good_count_today'], strips_tester.data['bad_count_today'], strips_tester.settings.test_device_name))
            strips_tester.data['db_local_connection'].commit()
        else:  # Get stats from Local DB
            # How counters work? Get number from test_device table and add rows of test_info of Local DB

            # Get existing data from local DB
            result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_device''').fetchone()
            # Update global variable with last remote counters
            if result:
                strips_tester.data.update(result)

            # Add Local DB counters to last remote counters
            strips_tester.data['good_count'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 1;''').fetchall())
            strips_tester.data['bad_count'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 0;''').fetchall())

            strips_tester.data['good_count_today'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 1 AND datetime(?) < datetime;''', (str(date_at_midnight),)).fetchall())
            strips_tester.data['bad_count_today'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 0 AND datetime(?) < datetime;''', (str(date_at_midnight),)).fetchall())

        # Update GUI with new counters
        gui_web.send({"command": "count", "good_count": strips_tester.data['good_count'], "bad_count": strips_tester.data['bad_count'], "good_count_today": strips_tester.data['good_count_today'],
                      "bad_count_today": strips_tester.data['bad_count_today']})

        gui_web.send({"command": "count_custom", "good_custom": strips_tester.data['good_custom'], "bad_custom": strips_tester.data['bad_custom'], "comment_custom": strips_tester.data['comment_custom']})

    except (pymongo.errors.NetworkTimeout, pymongo.errors.ServerSelectionTimeoutError):
        module_logger.error("Lost connection to DB, switching to Local DB")

        # Send notification that TN is working OFFLINE!
        gui_web.send({"command": "offline"})

        strips_tester.data['db_connection'] = None

        update_database()  # Update database, now to Local DB


# This function is used to synchronize Local DB to Remote DB when Remote DB is available.
def synchronize_remote_db():
    test_device_id = strips_tester.test_devices_col.find_one({"name": strips_tester.settings.test_device_name})['_id']

    result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info;''').fetchall()

    if result:  # If results found, that means that LocalDB is newer than RemoteDB. Update RemoteDB worker to local and serial
        module_logger.info("[StripsTesterDB] Updating RemoteDB (older) values from LocalDB (newer)...")

        result2 = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_device;''').fetchone()

        strips_tester.test_devices_col.update_one({'_id': test_device_id}, {"$set": {'serial': result2['serial'],
        'worker_id': result2['worker_id'], 'worker_type': result2['worker_type'], 'worker_comment': result2['worker_comment'],
        'memory': json.loads(result2['memory'])}}, True)

        module_logger.info("[StripsTesterDB] Synchronizing {} measurements..." . format(len(result)))

        for record in result:
            # Each nest test counts as one test individually
            test_info_data = {"datetime": datetime.datetime.strptime(record['datetime'], "%Y-%m-%d %H:%M:%S.%f"),
                              "start_test": datetime.datetime.strptime(record['start_test'], "%Y-%m-%d %H:%M:%S.%f"),
                              "test_device": test_device_id,
                              "worker": record['worker'],
                              "comment": record['comment'],
                              "type": record['type'],
                              "result": record['result'],
                              "nest": record['nest'],
                              "measurements": json.loads(record['measurements'])}

            strips_tester.test_info_col.insert_one(test_info_data)
            module_logger.info("[StripsTesterDB] Transferring measurement #{} into Remote DB..." .format(record['id']))

            # Increase worker custom counter data (applied to LocalDB)
            increase_good = record['result'] * 1
            increase_bad = (not record['result']) * 1

            strips_tester.test_worker_col.update_one({"id": record['worker']}, {"$inc": {"good": increase_good, "bad": increase_bad}}, True)

            # Delete measurement from local DB, which was transferred to Remote DB
            strips_tester.data['db_local_cursor'].execute('''DELETE FROM test_info WHERE id = ?;''', (record['id'],))
            strips_tester.data['db_local_connection'].commit()
    else:
        module_logger.info("[StripsTesterDB] Local DB is the same as Remote DB - No synchronization needed.")

    return


if __name__ == "__main__":
    # parameter = str(sys.argv[1])  # We use that if we want to provide extra parameters

    module_logger.info("Starting StripsTester ...")
    initialize_gpios()

    # Prepare data dictionary structure and reset to default values
    strips_tester.data['exist'] = {}
    strips_tester.data['status'] = {}

    strips_tester.data['measurement'] = {}
    strips_tester.data['start_time'] = {}

    strips_tester.data['good_count'] = 0
    strips_tester.data['bad_count'] = 0
    strips_tester.data['good_count_today'] = 0
    strips_tester.data['bad_count_today'] = 0
    strips_tester.data['worker_id'] = 1
    strips_tester.data['worker_type'] = 0
    strips_tester.data['worker_comment'] = ""
    strips_tester.data['serial'] = 0
    strips_tester.data['memory'] = {}

    strips_tester.data['good_custom'] = 0
    strips_tester.data['bad_custom'] = 0
    strips_tester.data['comment_custom'] = ""

    strips_tester.data['last_calibration'] = None

    # Create skeletons for local DB and load data if available. Count, stored in test_device are from remote DB. Extra counts are counted by rows in local DB.
    strips_tester.data['db_local_cursor'].execute(
        '''CREATE TABLE IF NOT EXISTS test_device(name TEXT, good_count INT, bad_count INT, good_count_today INT, bad_count_today INT, worker_id INT, worker_type INT, worker_comment TEXT, serial INT, memory TEXT)''')
    strips_tester.data['db_local_connection'].commit()

    strips_tester.data['db_local_cursor'].execute(
        '''CREATE TABLE IF NOT EXISTS test_info(id INTEGER PRIMARY KEY, worker INT, type INT, nest INT, result INT, measurements TEXT, comment TEXT, start_test TEXT, datetime TEXT)''')
    strips_tester.data['db_local_connection'].commit()

    strips_tester.data['db_local_cursor'].execute('''CREATE TABLE IF NOT EXISTS test_worker(id INTEGER PRIMARY KEY, good INT, bad INT, comment TEXT)''')
    strips_tester.data['db_local_connection'].commit()

    date_at_midnight = datetime.datetime.combine(datetime.datetime.today().date(), datetime.time(0))

    if strips_tester.data['db_connection'] is not None:
        module_logger.info("[StripsTesterDB] RemoteDB is available.")

        # Find test device in StripsTester database based on its name
        test_device = strips_tester.test_devices_col.find_one({'name': strips_tester.settings.test_device_name})

        # Check if test device exists in RemoteDB
        if test_device is None:
            module_logger.warning("[StripsTesterDB] Test device {name} not found in database. Creating skeletons for {name}...".format(name=strips_tester.settings.test_device_name))

            # Create new reference in test_device
            data = {'name': strips_tester.settings.test_device_name,
                    'nests': strips_tester.settings.test_device_nests,
                    'address': '127.0.0.1',  # Will be changed immediately on ping update
                    'description': 'Unknown',
                    'author': 'Itself',
                    'date_of_creation': datetime.datetime.utcnow(),
                    'worker_id': strips_tester.data['worker_id'],
                    'worker_type': strips_tester.data['worker_type'],
                    'worker_comment': strips_tester.data['worker_comment'],
                    'status': datetime.datetime.utcnow(),
                    'client': 'strips.gif',
                    'serial': strips_tester.data['serial'],
                    'memory': strips_tester.data['memory']}

            result = strips_tester.data['db_database']['test_device'].insert_one(data)
            test_device_id = result.inserted_id  # Get inserted ID as test device ID

            # Create test_count reference
            data = {
                'test_device': test_device_id,
                'good': 0,
                'bad': 0,
                'good_today': 0,
                'bad_today': 0,
                'last_test': datetime.datetime.utcnow(),
                'today_date': date_at_midnight
            }

            strips_tester.data['db_database']['test_count'].insert_one(data)
            test_device = strips_tester.test_devices_col.find_one({'name': strips_tester.settings.test_device_name})

        module_logger.warning("[StripsTesterDB] Loading {name} skeletons...".format(name=strips_tester.settings.test_device_name))

        # Synchronize LocalDB with RemoteDB
        synchronize_remote_db()

        # Retrieve last test device settings
        strips_tester.data['worker_id'] = int(test_device['worker_id'])
        strips_tester.data['worker_type'] = int(test_device['worker_type'])
        strips_tester.data['worker_comment'] = test_device['worker_comment']

        # Retrieve last test device serial
        strips_tester.data['serial'] = int(test_device['serial'])

        # Get all memory data from DB and apply them to global variable
        strips_tester.data['memory'] = test_device['memory']

        try:  # Load counters from DB
            strips_tester.data['good_count'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 1}).count()
            strips_tester.data['bad_count'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 0}).count()

            strips_tester.data['good_count_today'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 1, "datetime": {"$gt": date_at_midnight}}).count()
            strips_tester.data['bad_count_today'] = strips_tester.test_info_col.find({"test_device": test_device['_id'], "result": 0, "datetime": {"$gt": date_at_midnight}}).count()
        except TypeError:  # No tests were made -> keep count as zero
            pass

        try:
            strips_tester.data['good_custom'] = strips_tester.test_worker_col.find_one({"id": strips_tester.data['worker_id']})['good']
            strips_tester.data['bad_custom'] = strips_tester.test_worker_col.find_one({"id": strips_tester.data['worker_id']})['bad']
            strips_tester.data['comment_custom'] = strips_tester.test_worker_col.find_one({"id": strips_tester.data['worker_id']})['comment']
        except(TypeError, KeyError):  # Create custom counter skeleton in MongoDB
            strips_tester.test_worker_col.update_one({"id": strips_tester.data['worker_id']}, {"$set": {"good": 0, "bad": 0, "comment": ""}}, True)


        try:
            strips_tester.data['last_calibration'] = strips_tester.test_calibration_col.find({"test_device": test_device['_id']}).sort('date', -1).limit(1)[0]['date']
        except(TypeError, KeyError, IndexError) as e:
            strips_tester.data['last_calibration'] = None

        # Truncate local DB test_device
        strips_tester.data['db_local_cursor'].execute('''DELETE FROM test_device''')
        strips_tester.data['db_local_connection'].commit()

        # Truncate local DB test_worker
        strips_tester.data['db_local_cursor'].execute('''DELETE FROM test_worker''')
        strips_tester.data['db_local_connection'].commit()

        try:
            strips_tester.data['db_local_cursor'].execute('''ALTER TABLE test_device ADD COLUMN memory TEXT''')
            strips_tester.data['db_local_connection'].commit()
        except Exception as e: # Pass if duplicated column
            pass

        # Update local DB counters
        strips_tester.data['db_local_cursor'].execute('''INSERT INTO test_device(name, good_count, bad_count, good_count_today, bad_count_today, worker_id, worker_type, worker_comment, serial, memory) VALUES(?,?,?,?,?,?,?,?,?,?)''', (
            strips_tester.settings.test_device_name, strips_tester.data['good_count'], strips_tester.data['bad_count'], strips_tester.data['good_count_today'], strips_tester.data['bad_count_today'],
            strips_tester.data['worker_id'], strips_tester.data['worker_type'], strips_tester.data['worker_comment'], strips_tester.data['serial'], str(json.dumps(strips_tester.data['memory']))))
        strips_tester.data['db_local_connection'].commit()


        # Update local DB custom counters
        strips_tester.data['db_local_cursor'].execute('''INSERT INTO test_worker(id, good, bad, comment) VALUES(?, ?,?,?)''', (
            strips_tester.data['worker_id'],strips_tester.data['good_custom'], strips_tester.data['bad_custom'],strips_tester.data['comment_custom']))
        strips_tester.data['db_local_connection'].commit()

    else:  # Remote DB is not accessible
        module_logger.warning("[StripsTesterDB] RemoteDB is not available. Switching to LocalDB.")

        # Get existing data from local DB
        result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_device''').fetchone()
        result = strips_tester.dict_from_row(result)
        # Update global variable with last counters
        if result:
            if result['memory']:
                result['memory'] = json.loads(result['memory'])  # Convert string to valid JSON
                print("Memory: {mem}" . format(mem=result['memory']))

            # Update global variable with DB variables
            strips_tester.data.update(result)

        # Add Local DB counters to last remote counters
        strips_tester.data['good_count'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 1;''').fetchall())
        strips_tester.data['bad_count'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 0;''').fetchall())

        strips_tester.data['good_count_today'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 1 AND datetime(?) < datetime;''',(str(date_at_midnight),)).fetchall())
        strips_tester.data['bad_count_today'] += len(strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_info WHERE result = 0 AND datetime(?) < datetime;''',(str(date_at_midnight),)).fetchall())

        result = strips_tester.data['db_local_cursor'].execute('''SELECT * FROM test_worker WHERE id = ?''', (strips_tester.data['worker_id'],)).fetchone()

        if result:
            strips_tester.data['good_custom'] = result['good']
            strips_tester.data['bad_custom'] = result['bad']
            strips_tester.data['comment_custom'] = result['comment']

    if strips_tester.data['memory']:
        print(strips_tester.data['memory'])
        strips_tester.data.update(strips_tester.data['memory'])  # Append memory to global variable
        strips_tester.data.pop("memory", None)  # Pop memory from global variable

    # Start servers
    strips_tester.websocket.start()
    strips_tester.httpserver.start()

    # Initialize global lock to avoid racing
    strips_tester.data['lock'] = threading.Lock()

    if strips_tester.settings.thread_nests:
        module_logger.info("[StripsTester] Nests are THREADED. Each nest in seperate thread start.")
        # Multiple instances or threads. Global lock is required so the shared variables are not overwritten

        threads = []

        for thread in range(strips_tester.settings.test_device_nests):
            threads.append(threading.Thread(target=start_test_device, name="tester" + str(thread)))
            threads[-1].daemon = True
            threads[-1].start()

        for thread in range(strips_tester.settings.test_device_nests):
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
