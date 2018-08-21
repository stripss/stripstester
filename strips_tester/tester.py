import importlib
import logging
import os
import datetime
import sys
# import wifi
import RPi.GPIO as GPIO
import time
import shutil

sys.path += [os.path.dirname(os.path.dirname(os.path.realpath(__file__))), ]
import strips_tester
from strips_tester import settings,gui_server,current_product


import datetime
import config_loader
from strips_tester import utils


import subprocess

import serial
import struct
#import wifi
import RPi.GPIO as GPIO
import devices
# sys.path.append("/strips_tester_project/garo/")
# from strips_tester import *

from web_project.web_app.models import *
import strips_tester
import datetime
import numpy as np
from strips_tester import utils
from dateutil import tz


# name hardcoded, because program starts here so it would be "main" otherwise
module_logger = logging.getLogger(".".join(("strips_tester", "tester")))

import multiprocessing
import json
from collections import OrderedDict


server = strips_tester.server
queue = strips_tester.queue

class Task:
    def __init__(self,level: int = logging.CRITICAL):
        self.test_level = level
        self.end = []
        self.passed = []
        self.result = None
        # self.logger = logging.getLogger(".".join(("strips_tester", "tester", __name__)))

        self.device = settings.device_list

    def use_device(self,device):
        if settings.is_device_loaded(device):

            return settings.device_list[device]
        else:
            raise Exception("Device {} does not exist!" . format(device))

    # Get definition value from slug
    def get_definition(self,slug):
        for definition in settings.task_execution_order[type(self).__name__]['definition']:
            if slug in definition['slug']:
                return definition['value']

        raise ValueError("Slug {} does not exist in {} definitions!" . format(slug,type(self).__name__))

    def set_up(self):
        """Used for environment initial_setup"""
        pass

    def run(self) -> (bool, str):
        """returns bool for test fail/pass, and result(value) if applicable"""
        return False, "You should override 'run()' function!"

    def tear_down(self):
        """Clean up after task, close_relay connections etc..."""
        pass

    def _execute(self,test_level: int):
        self.set_up()
        module_logger.debug("Task: %s setUp", type(self).__name__)

        # { "db_test_type_name1":{ "data": db_val(float)  , "status": str ->ok/fail/signal , "level": 0-4, "unit": str },
        # "db_test_type_name2":{ "data": db_val(float)  , "status": str ->ok/fail/signal , "level": 0-4, "unit": str }}
        ret = self.run()
        # if len(ret) != 5:
        #     raise "Wrong argument length"


        # Dictionary for individual task measurement data
        strips_tester.current_product.tests['measurements'][type(self).__name__] = ret

        for keys, values in ret.items():
            if keys == "signal":
                if values[1] == "fail" and values[2] > 3:
                    self.end.append(True)
                    self.passed.append(False)
                elif values[1] == "ok":
                    self.passed.append(True)
                else:
                    self.passed.append(False)
                    ###########################################################################
            else:
                strips_tester.current_product.tests[keys] = values # insert test to be written to server.DB

                if values[1] == "fail" and values[2] > 3:
                    self.end.append(True)
                    self.passed.append(False)
                elif values[1] == 'ok':
                    self.passed.append(True)
                else:
                    self.passed.append(False)
                    ##########################################################################
        # normal flow when task is not critical

        result = all(self.passed)
        end = any(self.end)

        if result:
            module_logger.debug("Task: %s run and PASSED with result: %s", type(self).__name__, result)
        else:
            module_logger.debug("Task: %s run and FAILED with result: %s", type(self).__name__, result)

        self.tear_down()  # normal tear down
        return result, end  # to indicate further testing

    def set_level(self, level: int):
        self.test_level = level


def test_device_state(boot):
    i2c = settings.device_list['light_panel']

    if boot:
        # Boot state until someone connects
        boot_freq = 0.1
        while server.num_of_clients == 0:
            for i in range(2):
                i2c.set_led_status(0x05)
                time.sleep(boot_freq)
                i2c.set_led_status(0x00)
                time.sleep(boot_freq)
            time.sleep(2)
    else:
        # Shutdown state
        for i in range(10):
            i2c.set_led_status(0x0A)
            time.sleep(0.1)
            i2c.set_led_status(0x00)
            time.sleep(0.1)

def start_test_device():
    global custom_tasks
    server.start()

    ### one time tasks
    initialize_gpios()
    settings.load_devices()

    # If light panel is accessible, signal test device state
    if settings.is_device_loaded("light_panel"):
        test_device_state(True)

    # Initialize good and bad tests from server.DB

    start_msg = True
    spam = False

    custom_tasks = importlib.import_module("configs." + settings.get_setting_file_name() + ".custom_tasks")




    while True:
        while server.startt == False:
            # Test not initialized, can apply settings here.
            #st_state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))
            if "MANUAL_LOCK" in strips_tester.settings.gpios:
                state = GPIO.input(strips_tester.settings.gpios.get("MANUAL_LOCK"))

                if not state:
                    GPIO.output(strips_tester.settings.gpios.get("LOCK"),False)
                else:
                    GPIO.output(strips_tester.settings.gpios.get("LOCK"),True)

            if "START_SWITCH" in strips_tester.settings.gpios:
                if start_msg:
                    server.send_broadcast({"text": {"text": "Za začetek testa zapri pokrov.\n", "tag": "black"}})
                    start_msg = False

                start = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))





                if not start:
                    if server.master:
                        server.test_user_id = server.master_id
                        server.test_user_type = server.master_test_type

                        if server.maintenance == -1:
                            server.startt = True

                            # Assign which user is making a test
                            server.test_user_id = server.master_id
                            server.test_user_type = server.master_test_type
                        else:
                            if not spam:
                                spam = True

                                server.send(server.get_connection_by_id(server.master_id),{"text": {"text": "Naprava je v vzdrževalnem načinu.\n", "tag": "yellow"}})
                else:
                    spam = False

            if not queue.empty():  # something is in the queue
                msg = queue.get()

                if "shutdown" in msg:  # Update server.DB

                    test_device_state(False) # Signal TN shutdown
                    command = "/usr/bin/sudo /sbin/shutdown -h now"
                    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)

                if "service" in msg:  # Update server.DB
                    TestDevice.objects.filter(name=settings.test_device_name).update(service=msg['service'])

                if "calibration" in msg:  # Update server.DB
                    TestDevice.objects.filter(name=settings.test_device_name).update(calibrationdate=msg['calibration'])

                if "factory_reset" in msg:  # Factory reset of TN


                    if os.path.exists(strips_tester.settings.config_file):
                        # remove config.json file and replace it with new (updated) one.
                        try:
                            os.remove(strips_tester.settings.custom_config_file)
                        except OSError:
                            pass
                        try:
                            # Copy clean config.json to custom_config.json
                            shutil.copy2(strips_tester.settings.config_file,strips_tester.settings.custom_config_file)

                            server.send(msg['factory_reset'], {"factory_reset": True})

                        except Exception as err:
                            print("[StripsError]: {}" . format(err))
                            server.send(msg['factory_reset'], {"factory_reset": False})

                    else:
                        # Missing file!
                        print("Datoteke 'config.json' ni mogoce najti!")

                    settings.reload_tasks(settings.config_file, settings.custom_config_file)

                    for task_name in settings.task_execution_order:
                        server.send_broadcast({"task_update": {"task_slug": task_name, "task_enable": settings.task_execution_order[task_name]['enable']}})


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

                # Client triggers new series
                if "set_count" in msg:
                    # Strip time from string
                    countdate = datetime.datetime.strptime(msg['set_count'], '%Y-%m-%d %H:%M:%S')

                    # Update CountDate to DB
                    TestDevice.objects.filter(name=settings.test_device_name).update(countdate=countdate)

                    # Send statistics information
                    query = TestDevice_Test.objects.using(server.DB).filter(test_device_id=server.test_device_id, datetime__gte=countdate).distinct("id")
                    good1 = query.filter(countgood=1).count()
                    bad1 = query.filter(countbad=1).count()
                    good2 = query.filter(countgood=2).count()
                    bad2 = query.filter(countbad=2).count()

                    good = good1 + good2 * 2
                    bad = bad1 + bad2 * 2

                    # Send count info for each client
                    for client_number in range(server.num_of_clients):
                        if server.clientdata[client_number]['connected']:

                            user_good1 = query.filter(countgood=1,employee=server.clientdata[client_number]['id']).count()
                            user_bad1 = query.filter(countbad=1,employee=server.clientdata[client_number]['id']).count()
                            user_good2 = query.filter(countgood=2,employee=server.clientdata[client_number]['id']).count()
                            user_bad2 = query.filter(countbad=2,employee=server.clientdata[client_number]['id']).count()

                            user_good = user_good1 + user_good2 * 2
                            user_bad = user_bad1 + user_bad2 * 2

                            server.send(client_number, {"count": {"good": user_good, "bad": user_bad, "good_global": good, "bad_global": bad, "countdate": countdate}})

                    # Update counts for all clients!

                    # Send log file to requested client
                    #server.send(msg['make_log']['id'], {"log_file": log})

            time.sleep(0.1)

        try:
            global task_results
            # strips_tester.current_product.task_results = run_custom_tasks()

            run_custom_tasks()

        except Exception as e:
            module_logger.error("CRASH, PLEASE RESTART PROGRAM! %s", e)
            raise e

        finally:
            start_msg = True
            server.startt = False





def initialize_gpios():
    # GPIO.cleanup()
    GPIO.setmode(GPIO.BOARD)
    # GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for gpio in settings.gpios_settings.values():
        if gpio.get("function") == config_loader.G_INPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"),pull_up_down=gpio.get("pull"))
        elif gpio.get("function") == config_loader.G_OUTPUT:
            GPIO.setup(gpio.get("pin"), gpio.get("function"))
            GPIO.output(gpio.get("pin"), gpio.get("initial"))
        else:
            module_logger.critical("Not implemented gpio function")

    st_state = GPIO.input(strips_tester.settings.gpios.get("START_SWITCH"))
    module_logger.debug("GPIOs initialized")


def run_custom_tasks():
    global custom_tasks
    test_set_status = None

    #if server.DB == 'default' and settings.sync_db == True:
    #    pass
    #    sync_db(from_db='local', to_db='default')

    #get type from local or central
    product_type = ProductType.objects.using(server.DB).get(name=settings.product_name, type=settings.product_type)
    # TASKS
    #################################################################################
    strips_tester.current_product = Product(serial=None,
                                            production_datetime=None,
                                            hw_release=settings.product_hw_release,
                                           notes=settings.product_notes,
                                           type=product_type)

    importlib.reload(custom_tasks)

    settings.reload_tasks(settings.config_file,settings.custom_config_file)

    server.result = "work"

    server.send_broadcast({"task_result": server.result})
    server.send_broadcast({"text": {"text": "Začetek testa\n", "tag": "purple"}})

    # Reset tasks status to idle
    for task_name in settings.task_execution_order:
        server.send_broadcast({"task_update": {"task_slug": task_name, "task_state": "idle", "task_info": ""}})

    strips_tester.current_product.tests['measurements'] = {}
    strips_tester.current_product.countgood = 0
    strips_tester.current_product.countbad = 0

    for task_name in settings.task_execution_order:
        if settings.task_execution_order[task_name]:

            # is task enabled?
            if settings.task_execution_order[task_name]['enable']:
                CustomTask = getattr(custom_tasks, task_name)

                try:
                    module_logger.debug("Executing: %s ...", CustomTask)
                    server.send_broadcast({"text": {"text": "Izvajanje naloge '{}'...\n" . format(settings.task_execution_order[task_name]['name']), "tag": "blue"}})
                    server.send_broadcast({"task_update": {"task_slug": task_name, "task_state": "work"}})
                    custom_task = CustomTask()

                    result, end = custom_task._execute(config_loader.TEST_LEVEL)
                    strips_tester.current_product.task_results.append(result)

                    if result:
                        server.send_broadcast({"task_update": {"task_slug": task_name, "task_state": "ok"}})
                    else:
                        server.send_broadcast({"task_update": {"task_slug": task_name, "task_state": "fail"}})

                    if end == True:
                        # Could be separate function. Here, due to import restrictions.
                        # release all hardware, print sticker, etc...
                        #######################
                        for task_name in settings.critical_event_tasks:
                            if settings.critical_event_tasks[task_name]:
                                CustomTask = getattr(custom_tasks, task_name)
                                try:
                                    server.send_broadcast({"text": {"text": "Kritično izvajanje {}...\n" . format(settings.critical_event_tasks[task_name]['name']), "tag": "red"}})
                                    module_logger.debug("Executing: %s ...", CustomTask)
                                    custom_task = CustomTask()
                                    result, end = custom_task._execute(config_loader.TEST_LEVEL)

                                    strips_tester.current_product.task_results.append(result)
                                except Exception as ee:
                                    raise "CRITICAL EVENT EXCEPTION"
                        break
                        ######################
                # catch code exception and bugs. It shouldn't be for functional use
                except Exception as e:
                    module_logger.error(str(e))
                    module_logger.exception("Code error -> REMOVE THE BUG")
            else:
                server.send_broadcast({"text": {"text": "Preskok naloge '{}'...\n" . format(settings.task_execution_order[task_name]['name']), "tag": "grey"}})
                module_logger.debug("Task %s ignored", task_name)

    server.send_broadcast({"text": {"text": "Konec testa\n\n", "tag": "purple"}})
    ## insert into DB

    # Are all task results True?
    if all(strips_tester.current_product.task_results):
        test_set_status = True
    else:
        test_set_status = False

    if test_set_status:
        server.result = "ok"
        module_logger.info('TEST USPEL\n\n')
    else:
        server.result = "fail"

        module_logger.error('TEST NI USPEL\n\n')

    server.send_broadcast({"task_result": server.result})
    server.result = "idle"
    # TASKS ENDS


    # UPLOAD TO DATABASE

    # Get current date and time with right UTC timezone
    dateandtime = datetime.datetime.now() + datetime.timedelta(hours=2)

    result = TestDevice.objects.using(server.DB).filter(name=settings.test_device_name).exists()

    if result:
        test_device_id = TestDevice.objects.using(server.DB).get(name=settings.test_device_name)
    else:
        test_device_id = TestDevice(name=settings.test_device_name,author="Spremeni",service=1000)
        test_device_id.save()

    # Make new Test query
    test_device_test = TestDevice_Test(datetime=dateandtime,
                                       serial=strips_tester.current_product.serial,
                                       employee=server.test_user_id,
                                       test_type=server.test_user_type,
                                       result=test_set_status,
                                       countgood=strips_tester.current_product.countgood,
                                       countbad=strips_tester.current_product.countbad,
                                       test_device_id=test_device_id.id,
                                       data=json.dumps(strips_tester.current_product.tests['measurements'])
                                       )
    test_device_test.save(using=server.DB)

    # Lower service counter by one
    service = TestDevice.objects.using(server.DB).get(name=settings.test_device_name).service - 1

    if service < 0:
        service = 0

    TestDevice.objects.using(server.DB).filter(name=settings.test_device_name).update(service=service)

    # Get CountDate from DB
    countdate = TestDevice.objects.using(server.DB).get(name=settings.test_device_name).countdate

    # Send statistics information
    query = TestDevice_Test.objects.using(server.DB).filter(test_device_id=server.test_device_id, datetime__gte=countdate).distinct("id")
    good1 = query.filter(countgood=1).count()
    bad1 = query.filter(countbad=1).count()
    good2 = query.filter(countgood=2).count()
    bad2 = query.filter(countbad=2).count()

    good = good1 + good2 * 2
    bad = bad1 + bad2 * 2

    # Send count info for each client
    for client_number in range(server.num_of_clients):
        if server.clientdata[client_number]['connected']:
            user_good1 = query.filter(countgood=1,employee=server.clientdata[client_number]['id']).count()
            user_bad1 = query.filter(countbad=1,employee=server.clientdata[client_number]['id']).count()
            user_good2 = query.filter(countgood=2,employee=server.clientdata[client_number]['id']).count()
            user_bad2 = query.filter(countbad=2,employee=server.clientdata[client_number]['id']).count()

            user_good = user_good1 + user_good2 * 2
            user_bad = user_bad1 + user_bad2 * 2

            server.send(client_number, {"count": {"good": user_good, "bad": user_bad, "good_global": good, "bad_global": bad}})

    # update clients
    server.send_broadcast({"service": service})

    if server.afterlock:
        if "LOCK" in settings.gpios: # Disable lock if it exists
            GPIO.output(strips_tester.settings.gpios.get("LOCK"),False)

            time.sleep(server.afterlock)

            GPIO.output(strips_tester.settings.gpios.get("LOCK"),True)

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
    module_logger.info('DATABASE SYNCRONIZATION DONE %s', time.time())





if __name__ == "__main__":
    # parameter = str(sys.argv[1])
    module_logger.info("Starting tester ...")


    start_test_device()
    module_logger.error('ZNOVA ZAŽENI PROGRAM!!!')
    while True:
        time.sleep(1)
