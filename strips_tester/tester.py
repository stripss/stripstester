#!/venv_strips_tester/bin/python
import importlib
import os
import sys
import RPi.GPIO as GPIO
import time

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]

from strips_tester import settings

import config_loader
import subprocess

import RPi.GPIO as GPIO
import devices
# Import Django models
from web_project.web_app.models import *

import gui_server
import strips_tester
import datetime
from dateutil import parser

import threading
import json
from collections import OrderedDict
import pytz


from django.db.models import F, Prefetch, Q


# Server variable change (change server to self.server)!!!!!
class Task:
    TASK_OK = 0
    TASK_WARNING = 1
    TASK_FAIL = 2

    def __init__(self, test_device_handler):
        self.end = []
        self.passed = []
        self.result = None
        self.state = Task.TASK_OK
        self.test_device = test_device_handler
        self.server = self.test_device.server

        self.device = self.test_device.settings.device_list

    def use_device(self, device):

        # Check if device is loaded from beginning
        if self.test_device.settings.is_device_loaded(device):

            return self.test_device.settings.device_list[device]
        else:
            raise Exception("Device {} does not exist!" . format(device))

    # Get definition value from slug
    def get_definition(self,slug):
        return self.test_device.settings.get_definition(type(self).__name__,slug)

    # Get definition value from slug
    def get_external_definition(self, task_name, slug):
        return self.test_device.settings.get_definition(task_name, slug)

    # Get definition value from slug
    def get_definition_unit(self,slug):
        for definition in self.test_device.settings.task_execution_order[type(self).__name__]['definition']:
            if slug in definition['slug']:
                return definition['unit']

        raise ValueError("Slug {} does not exist in {} definitions!" . format(slug,type(self).__name__))

    def is_unit_percent(self,unit):
        if unit == "%":
            return True
        else:
            return False

    def set_up(self):
        """Used for environment initial_setup"""
        pass

    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    def tear_down(self):
        """Clean up after task, close_relay connections etc..."""
        pass

    def _execute(self):
        ret = Task.TASK_OK

        # Task set_up program
        try:
            self.set_up()

        except Exception as ee:
            # Setup procedure is for test device
            # If error happen, it is critical
            print("[Task set_up]: {}".format(ee))
            self.server.send_broadcast({"command": "text", "text": "Napaka v set_up: {}\n" . format(ee), "tag": "red"})
            ret = Task.TASK_FAIL



        # If set_up succeeded
        if ret != Task.TASK_FAIL:
            try:
                # Task run program (return task name and task_state)
                task_name = self.run()


                # Loop through nests and see if all measurements succeeded
                for current in range(len(strips_tester.product)):
                    if strips_tester.product[current].ok: # If some of products are not ok, inspect at which task
                        #print("Product {} FAIL".format(current))
                        if task_name in strips_tester.product[current].measurements: # Check if current task is in measurements (could have no measurements)
                            #print("Return: {}".format(task_name))
                            #print(len(strips_tester.product[current].measurements[task_ret]))
                            for i in range(len(strips_tester.product[current].measurements[task_name])): # Loop through measurements of this task
                                if strips_tester.product[current].measurements[task_name][i]['ok']: # If any of values are fail, inspect
                                    ret = strips_tester.product[current].measurements[task_name][i]['ok']

                                    break

                            if ret == Task.TASK_FAIL:
                                break

            # Return task name
                # Check all products if exists and fail at that task


            except Exception as ee:
                # Setup procedure is for test device
                # If error happen, it is critical
                print("[Task run]: {}".format(ee))
                self.server.send_broadcast({"command": "text", "text": "Napaka v run: {}\n" . format(ee), "tag": "red"})
                ret = Task.TASK_FAIL


        # Task tear_down program
        self.tear_down()

        return ret

# Define testing product information, which stores info through test
class ProductInfo:
    def __init__(self):
        self.exist = False
        self.ok = 0 # Task.TASK_OK
        self.serial = 0
        self.measurements = {}

    def add_measurement(self,task,slug,state,value):
        if not self.exist:
            print("Product does not exist yet!")
            return

        if task not in self.measurements:
            self.measurements[task] = []

        # Append new measurement at current task
        self.measurements[task].append({})

        self.measurements[task][-1]['slug'] = slug
        self.measurements[task][-1]['ok'] = state
        self.measurements[task][-1]['value'] = value

        if state != Task.TASK_OK: # If some measurement fail, make product fail
            self.ok = state

        return

    # Determine if product is ok
    def is_ok(self):
        if self.ok == Task.TASK_OK:
            return True
        else:
            return False

class Device:
    STATUS_NO_CLIENTS = 0
    STATUS_START = 1
    STATUS_IDLE = 2

    def __init__(self):
        # Prepare test device for use
        self.settings = settings
        self.db = strips_tester.check_db_connection()  # Django DB instance

        self.initialize_gpios()

        self.settings.load_devices()

        # Load latest custom tasks from file
        self.custom_tasks = importlib.import_module("configs." + self.settings.get_setting_file_name() + ".custom_tasks")

        # Create test device images folder for storing camera-related test data. Usually we save only the last one.
        if not os.path.exists(self.settings.test_dir + "/images/"):
            try:
                os.makedirs(self.settings.test_dir + "/images/")
            except OSError:
                print("[StripsTester] ERROR: Cannot make 'images' folder.")

        # Check if TN exists in DB
        result = TestDevice.objects.using(self.db).filter(name=self.settings.test_device_name).exists()

        if result:
            self.message("Test device '{}' found in DB. Loading data..." . format(self.settings.test_device_name))

            # Get test device data from DB
            query = TestDevice.objects.using(self.db).get(name=self.settings.test_device_name)
        else:
            date = pytz.utc.localize(datetime.datetime.utcnow())

            # If test device is not found, create one
            query = TestDevice(
                name=self.settings.test_device_name,
                author="Spremeni",
                service=1000,
                manual="",
                countdate=date,
                calibrationdate=date,
                nests=1).save(using=self.db)

            self.message("Device {} added to DB. Change its attributes." . format(self.settings.test_device_name))

        # Store more info about test device into variables for further usage
        self.id = query.id
        self.nests = query.nests
        self.countdate = pytz.utc.localize(parser.parse(query.countdate))
        self.calibrationdate = pytz.utc.localize(parser.parse(query.calibrationdate))
        self.service = query.service
        self.manual = query.manual
        self.author = query.author

        self.maintenance = None
        self.status = self.STATUS_NO_CLIENTS
        self.result = "idle"
        self.test_type = None
        self.test_id = None
        self.master_test_type = None
        self.master_test_id = None
        self.start_test = None
        self.end_test = None

        self.initialize_server()

        # Test device prepared, go to loop
        self.test_device_loop()

    def initialize_gpios(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        for gpio in self.settings.gpios_settings.values():
            if gpio.get("function") == config_loader.G_INPUT:
                GPIO.setup(gpio.get("pin"), gpio.get("function"), pull_up_down=gpio.get("pull"))
            elif gpio.get("function") == config_loader.G_OUTPUT:
                GPIO.setup(gpio.get("pin"), gpio.get("function"))
                GPIO.output(gpio.get("pin"), gpio.get("initial"))

    def initialize_server(self):
        self.server = gui_server.Server(self)

        # Start the server
        server_thread = threading.Thread(target=self.server.start)
        server_thread.setDaemon(True)
        server_thread.start()

    def test_device_state(self, boot):
        found_i2c = False
        period = 0.1

        if self.settings.is_device_loaded("LightBoard"):
            i2c = self.settings.device_list['LightBoard']
            found_i2c = True
        else:
            # Old LightBoard support (GO-HA)
            try:
                i2c = devices.MCP23017(0x20)
                found_i2c = True
            except:
                pass

        if found_i2c:
            if boot:
                # Boot state until someone connects

                while server.num_of_clients == 0:
                    i2c.set_led_status(0x14)
                    time.sleep(period)
                    i2c.set_led_status(0x00)
                    time.sleep(period)
            else:
                # Shutdown state
                for i in range(10):
                    i2c.set_led_status(0x0A)
                    time.sleep(period)
                    i2c.set_led_status(0x00)
                    time.sleep(period)
        else:
            # Searching for LIGHT_GREEN and LIGHT_RED pin definition
            if boot:
                if "LIGHT_GREEN" in strips_tester.settings.gpios:
                    if "LIGHT_RED" in strips_tester.settings.gpios:
                        GPIO.output(strips_tester.settings.gpios["LIGHT_RED"], False)

                    while server.status == server.STATUS_NOCLIENTS:
                        GPIO.output(strips_tester.settings.gpios["LIGHT_GREEN"], True)
                        time.sleep(period)
                        GPIO.output(strips_tester.settings.gpios["LIGHT_GREEN"], False)
                        time.sleep(period)
            else:
                if "LIGHT_RED" in strips_tester.settings.gpios:
                    if "LIGHT_GREEN" in strips_tester.settings.gpios:
                        GPIO.output(strips_tester.settings.gpios["LIGHT_GREEN"], False)

                    # Shutdown state
                    for i in range(10):
                        GPIO.output(strips_tester.settings.gpios["LIGHT_RED"], True)
                        time.sleep(period)
                        GPIO.output(strips_tester.settings.gpios["LIGHT_RED"], False)
                        time.sleep(period)

    def shutdown(self):
        # Perform test device shutdown
        self.test_device_state(False)  # Signal TN shutdown
        subprocess.Popen("/usr/bin/sudo /sbin/shutdown -h now".split(), stdout=subprocess.PIPE)

    def run_custom_tasks(self):
        strips_tester.product = []
        self.task_results = []

        # TASKS
        #################################################################################

        # Initialize ProductInfo object for all nests
        for nest in range(self.nests):
            strips_tester.product.append(ProductInfo())

        # Reload custom tasks (may be updated)
        importlib.reload(self.custom_tasks)

        # Reload config.json file (may be updated)
        settings.reload_tasks(settings.config_file, settings.custom_config_file)

        # Set server status on WORK
        self.result = "work"
        self.start_test = pytz.utc.localize(datetime.datetime.utcnow())
        self.end_test = None

        self.server.send_broadcast({"command": "task_result", "result": self.result})
        self.server.send_broadcast({"command": "test_time", "start_test": self.start_test.isoformat(), "end_test": self.end_test})
        self.server.send_broadcast({"command": "text", "text": "Začetek testa\n", "tag": "purple"})

        # Update GUI - Reset tasks status to idle
        for task_name in self.settings.task_execution_order:
            self.server.send_broadcast({"command": "task_update", "update": {"slug": task_name, "state": "idle"}})

        for task in self.settings.task_execution_order:
            if self.settings.task_execution_order[task]:


                # Check if task is enabled
                if self.settings.task_execution_order[task]['enable']:
                    CustomTask = getattr(self.custom_tasks, task)

                    try:
                        self.server.send_broadcast({"command": "text", "text": "Izvajanje naloge '{}'...\n" . format(self.settings.task_execution_order[task]['name']), "tag": "blue"})
                        self.server.send_broadcast({"command": "task_update", "update": {"slug": task, "state": "work"}})

                        # Make custom_task instance
                        custom_task = CustomTask(self)

                        # Run custom task
                        result = custom_task._execute()

                        # Store task result into list for final decision
                        self.task_results.append(result)

                        if result == Task.TASK_OK:
                            self.server.send_broadcast({"command": "task_update", "update": {"slug": task, "state": "ok"}})
                        else:
                            self.server.send_broadcast({"command": "task_update", "update": {"slug": task, "state": "fail"}})

                            # If task error is fatal
                            if result == Task.TASK_FAIL:
                                # Could be separate function. Here, due to import restrictions.
                                # release all hardware, print sticker, etc...
                                #######################

                                # Execute critical tasks
                                # Can be done only task_name['name']?
                                for task in self.settings.critical_event_tasks:
                                    if self.settings.critical_event_tasks[task]:
                                        CustomTask = getattr(self.custom_tasks, task)

                                        self.server.send_broadcast({"command": "text", "text": "Kritično izvajanje naloge '{}'...\n" . format(self.settings.task_execution_order[task]['name']), "tag": "red"})

                                        try:

                                            custom_task = CustomTask(self)
                                            result = custom_task._execute()

                                            self.task_results.append(result)
                                        except Exception as ee:
                                            raise "CRITICAL EVENT EXCEPTION"
                                break
                                ######################
                    # catch code exception and bugs. It shouldn't be for functional use
                    except Exception as e:
                        self.message("Code error: {}" . format(e))
                else:
                    self.server.send_broadcast({"command": "text", "text": "Preskok naloge '{}'...\n" . format(self.settings.task_execution_order[task]['name']), "tag": "grey"})

        # Broadcast task result to GUI
        if any(self.task_results):
            self.server.send_broadcast({"command": "task_result", "result": "fail"})
        else:
            self.server.send_broadcast({"command": "task_result", "result": "ok"})

        # Set server status on IDLE
        self.result = "idle"
        self.start_test = None
        self.end_test = pytz.utc.localize(datetime.datetime.utcnow())

        self.server.send_broadcast({"command": "test_time", "start_test": self.start_test, "end_test": self.end_test.isoformat()})
        self.server.send_broadcast({"command": "text", "text": "Konec testa\n", "tag": "purple"})
        # Tasks ended

        # Store results in DB
        self.save_to_db()


    def save_to_db(self):
        # Upload to DB
        self.message("Saving results into database...")

        # Save new Test
        test_device_test = TestDevice_Test(
            test_device_id=self.id,
            datetime=self.end_test,
            employee=self.test_id,  # Get user_num from factory
            test_type=self.test_type,
            result=any(self.task_results)
        )

        test_device_test.save(using=self.db)

        # Save every ProductInfo which were tested in this Test
        for current in range(self.nests):
            # Check if product exists
            if strips_tester.product[current].exist:
                self.message("Product {} exist.. Saving into TestDevice_Product" . format(current))

                # Make new ProductInfo query
                TestDevice_Product(
                    test_id=test_device_test.id,    # Store current test ID
                    serial=strips_tester.product[current].serial,
                    ok=strips_tester.product[current].ok,
                    nest=current,
                    measurements=json.dumps(strips_tester.product[current].measurements)
                ).save(using=self.db)

                self.message("Done.")
        # Decrease service counter
        self.service = self.service - 1

        if self.service < 0:
            self.service = 0

        # Update service counter
        TestDevice.objects.using(self.db).filter(id=self.id).update(service=self.service)

        # Update connected clients
        self.server.send_broadcast({"command": "service", "data": self.service})

        count_query = TestDevice_Test.objects.using(self.db).filter(test_device_id=self.id, datetime__gte=self.countdate).values('id')
        count_good = TestDevice_Product.objects.using(self.db).filter(test_id__in=count_query, ok=0).count()
        count_bad = TestDevice_Product.objects.using(self.db).filter(test_id__in=count_query, ok__gt=0).count()

        # Send count info for each client
        for user in self.server.factory.users:
            count_query = TestDevice_Test.objects.using(self.db).filter(test_device_id=self.id, datetime__gte=self.countdate, employee=self.server.factory.users[user].id).values('id')

            user_count_good = TestDevice_Product.objects.using(self.db).filter(test_id__in=count_query, ok=0).count()
            user_count_bad = TestDevice_Product.objects.using(self.db).filter(test_id__in=count_query, ok__gt=0).count()

            try:
                # Send count to each user connected
                self.server.factory.users[user].send({"command": "count", "date": self.countdate.isoformat(), "good": user_count_good, "bad": user_count_bad, "good_global": count_good, "bad_global": count_bad})
            except KeyError:
                pass  # Pass error if client disconnects right here

        time.sleep(1)
        return

    def message(self, message):
        print("[StripsTester] {}" . format(message))

    def test_device_loop(self):
        # Inifinity loop - keep test device alive forever
        while True:
            self.start_message = False

            # Initiate ready state for test device while no clients are connected
            while self.status == self.STATUS_NO_CLIENTS:
                time.sleep(0.5)
                self.message("Waiting for clients...")
                #self.test_device_state(True)

            # Wait until start test is not received (maybe update db meanwhile?)
            while self.status != self.STATUS_START:
                if self.status == self.STATUS_NO_CLIENTS: # If last client disconnects, return to first mode
                    break

                if self.maintenance is None and self.test_id is not None:
                    # Check if START SWITCH exist on test device
                    if "START_SWITCH" in self.settings.gpios:
                        if not self.start_message:
                            self.server.send_broadcast({"command": "text", "text": "Za začetek testa zapri pokrov ali pritisni gumb START.\n", "tag": "black"})
                            self.start_message = True

                        start_switch = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))

                        if start_switch:  # Start test with master client
                            self.test_id = self.master_test_id
                            self.test_type = self.master_test_type

                            self.status = self.STATUS_START
                else:  # Wait for maintenance to drop or new master arrive
                    time.sleep(0.1)

            # This condition must be here, so NO_CLIENTS can pass it
            if self.status == self.STATUS_START:
                # Check maintenance mode

                if self.maintenance is None:
                    if self.test_id is not None:
                        self.run_custom_tasks()

                        self.start_message = False
                    else:
                        # Send only to master num
                        self.server.send_broadcast({"command": "text", "text": "Glavni delavec ni določen. Če začnete testirati in prevzeti testno napravo, kliknite gumb START.\n", "tag": "yellow"})
                else:
                    # Send only to master num
                    self.server.send_broadcast({"command": "text", "text": "Naprava je v vzdrževalnem načinu.\n", "tag": "yellow"})

                # Successfully ended test
                if self.status == self.STATUS_START:
                    self.status = self.STATUS_IDLE

'''
def start_test_device():


                if "make_log" in msg:
                    test_device_id = TestDevice.objects.using(server.DB).get(name=settings.test_device_name)

                    # Strip time from string
                    st_date = datetime.datetime.strptime(msg['make_log']['st_date'], '%Y.%m.%d')
                    en_date = datetime.datetime.strptime(msg['make_log']['en_date'], '%Y.%m.%d')

                    datadata = TestDevice_Test.objects.using(server.DB).filter(test_device_id=server.test_device_id,datetime__gt=st_date,datetime__lte=en_date)

                    log = []

                    test_type_list = ["Redna proizvodnja", "Kosi iz popravila", "Analiza reklamacije", "Ostalo"]

                    log.append("Zapisnik od {} do {}:" . format(st_date.strftime("%d.%m.%Y"),en_date.strftime("%d.%m.%Y")))

                    for i in range(datadata.count()):
                        log.append(datadata[i].datetime.strftime("%d.%m.%Y;%H:%M:%S") + ";" + str(datadata[i].serial) + ";" + str(datadata[i].employee) + ";" +
                                   test_type_list[int(datadata[i].test_type)] + ";" + str(datadata[i].result) + ";" + str(datadata[i].data))

                    #print("LOG server export {}".format(msg['make_log']['id']))

                    # Send log file to requested client
                    server.send(msg['make_log']['id'], {"log_file": log})
'''

def sync_db(from_db: str='local', to_db: str='default', flag: bool=False):
    module_logger.warning('DATABASE SYNCRONIZATION %s', time.time())
    bulk_size = 100
    #products
    existing = Product.objects.using(to_db).all()  # .filter(serial__in=local_product_ids)
    local = Product.objects.using(from_db).all()
    #tests and test sets

    # write products
    existing_product_ids = existing.values_list("serial", flat=True)
    local_products = local.exclude(serial__in=list(existing_product_ids))
    rows = local_products.count()
    bulks = rows // bulk_size
    last_bulk = rows - (rows - (bulks * bulk_size))
    for i in range(bulks):
        local_products_ram = list(local_products[i * bulk_size:(i + 1) * bulk_size])
        for product in local_products_ram:
        #for product in (local_products[i * bulk_size:(i + 1) * bulk_size]):
            product.id = None
        Product.objects.using(to_db).bulk_create(local_products_ram)
    local_products_ram = list(local_products[last_bulk:rows])
    Product.objects.using(to_db).bulk_create(local_products_ram)
    # write products
    # existing_product_ids = existing.values_list("serial", flat=True)
    # local_products = local.exclude(serial__in=list(existing_product_ids))
    # # write products to central base
    # local_products_ram = local_products[0:100]
    # print(str(local_products_ram.query))
    # for product in local_products_ram.all():
    #     product.id = None
    # Product.objects.using(to_db).bulk_create(local_products_ram)  # get all local products
    # local_products_ram.delete()

    #write test_sets
    test_sets = TestSet.objects.using(from_db).all()
    rows = test_sets.count()
    bulks = rows // bulk_size
    last_bulk = rows - (rows - (bulks * bulk_size))
    for i in range(bulks):
        test_sets_ram = list(test_sets[i * bulk_size:(i + 1) * bulk_size])
        for test_set in local_products_ram:
        #for product in (local_products[i * bulk_size:(i + 1) * bulk_size]):
            test_set.id = None
            test_set.product_id = Product.objects.using(to_db).get(serial=test_set.product.serial).id
        TestSet.objects.using(to_db).bulk_create(test_sets_ram)

    test_sets_ram = list(test_sets[last_bulk:rows])
    for test_set in test_sets_ram:
        # for product in (local_products[i * bulk_size:(i + 1) * bulk_size]):
        test_set.id = None
        test_set.product_id = Product.objects.using(to_db).get(serial=test_set.product.serial).id
    TestSet.objects.using(to_db).bulk_create(test_sets_ram)
    # test_sets_ram = list(test_sets[0:100])
    # for test_set in test_sets_ram:
    #     test_set.id = None
    #     test_set.product_id = Product.objects.using(to_db).get(serial=test_set.product.serial).id
    # TestSet.objects.using(to_db).bulk_create(test_sets_ram)

    # write tests
    tests = Test.objects.using(from_db).all()
    rows = tests.count()
    bulks = rows // bulk_size
    last_bulk = rows - (rows - (bulks * bulk_size))
    for i in range(bulks):
        test_ram = list(tests[i * bulk_size:(i + 1) * bulk_size])
        for test in test_ram:
            test.type_id = TestType.objects.using(to_db).get(name=test.type.name).id
            test.test_set_id = TestSet.objects.using(to_db).get(datetime=test.test_set.datetime).id
        Test.objects.using(to_db).bulk_create(test_ram)
    test_ram = list(tests[last_bulk:rows])
    for test in test_ram:
        test.type_id = TestType.objects.using(to_db).get(name=test.type.name).id
        test.test_set_id = TestSet.objects.using(to_db).get(datetime=test.test_set.datetime).id
    Test.objects.using(to_db).bulk_create(test_ram)
    # tests_ram = list(tests[:100])
    # for test in tests_ram:
    #     test.id = None
    #     # print(test.type.name)
    #     # print(test.product.serial)
    #     # print(test.id)
    #     test.type_id = TestType.objects.using(to_db).get(name=test.type.name).id
    #     print(test.test_set.datetime)
    #     test.test_set_id = TestSet.objects.using(to_db).get(datetime=test.test_set.datetime).id
    #     test.save(using=to_db)

    test_sets.using(from_db).delete()
    tests.using(from_db).delete()
    local.using(from_db).delete()
    settings.sync_db = False

if __name__ == "__main__":
    wifi_found = False

    while not wifi_found:
        wifi = subprocess.check_output(['iwgetid']).decode()

        if "StripsTester" in wifi:
            # TN is running in production mode
            print("Production mode (Found StripsTester)")
            wifi_found = True

            # Check if strips tester is running
        elif "LabTest" in wifi:
            # TN is running in debug mode
            print("Debug mode (Found LabTest)")
            wifi_found = True
        else:
            print("Debug mode")
            break
            #time.sleep(5)

    test_device = Device()

    while True:
        time.sleep(1)
