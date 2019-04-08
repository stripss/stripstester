import os
import django
import logging
import utils
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_project.settings")
django.setup()
# first time check & create admin user
from django.contrib.auth.models import User, Group
from web_project.web_app.models import *
from strips_tester import DB

# name hardcoded, because program starts here so it would be "main" otherwise
module_logger = logging.getLogger(".".join(("strips_tester", "presets")))
databases = ['default'] # WRITE ONLY TO CENTRAL DB, local data is than synced from there
#databases = ['local']


def preset_tables(database: str='central', flag: bool=False):
    if flag:
        #USERS
        if not User.objects.using(database).filter(username="admin").exists():
            admin = User.objects.db_manager(database).create_superuser('admin', 'admin@admin.com', 'admin')
        # PRODUCT TYPES
        ProductType.objects.using(database).get_or_create(name='MVC', type=1, variant='basic', description='mvc module for Garo')
        ProductType.objects.using(database).get_or_create(name='GO-C19', type=2, variant='n/a', description='c19 module for Gorenje')
        ProductType.objects.using(database).get_or_create(name='GO-HA', type=3, variant='n/a', description='ha module for Gorenje')
        ProductType.objects.using(database).get_or_create(name='GACS_A2 Bender', type=4, variant='n/a', description='bender module')

        for product_type in ProductType.objects.using(database).all():
            module_logger.debug("%s, %s, %s, %s",product_type.type, product_type.name, product_type.variant, product_type.description)
        # TEST TYPES
        TestType.objects.using(database).get_or_create(name='Vc', description='15V', units='V')
        TestType.objects.using(database).get_or_create(name='12V', description='12V', units='V')
        TestType.objects.using(database).get_or_create(name='3V3', description='3V3', units='V')
        TestType.objects.using(database).get_or_create(name='5V', description='5V', units='V')
        TestType.objects.using(database).get_or_create(name='MCU flash', description='flash success', units='bool')
        TestType.objects.using(database).get_or_create(name='relays', description='relay status', units='bool')
        TestType.objects.using(database).get_or_create(name='keyboard', description='push button status', units='bool')
        TestType.objects.using(database).get_or_create(name='temperature', description='temperature sensor data', units='°C')
        TestType.objects.using(database).get_or_create(name='RTC', description='external RTC status', units='bool')
        TestType.objects.using(database).get_or_create(name='flash test', description='flash status', units='bool')
        TestType.objects.using(database).get_or_create(name='switches', description='switches status', units='bool')
        TestType.objects.using(database).get_or_create(name='board test', description='board type', units='uint8')
        TestType.objects.using(database).get_or_create(name='display', description='display status', units='bool')
        for test in TestType.objects.using(database).all():
            module_logger.debug("%s, %s, %s", test.name, test.description, test.units)
    else:
        module_logger.warning('NO test_type and product_type preset')


def preset_tables_from_db(from_db: str='central', to_db: str='local', flag: bool=False):
    '''
    Creates user admin and copies data from_db to_db ib bulk size defined by N
    :param from_db: central
    :param to_db: local
    :param flag:
    :return:
    '''
    if flag:
        module_logger.warning("Preseting test_db from db : %s to db: %s", from_db, to_db)
        bulk_size = 100
        # create one user -> db_manager
        if not User.objects.using(to_db).filter(username="admin").exists():
            admin = User.objects.db_manager(to_db).create_superuser('admin', 'admin@admin.com', 'admin')

        # get data from db
        central_product_types = ProductType.objects.using(from_db).all()
        central_test_types = TestType.objects.using(from_db).all()
        local_product_types = ProductType.objects.using(to_db).all()
        local_test_types = TestType.objects.using(to_db).all()

        local_product_types_types = local_product_types.values_list("type", flat=True)
        central_product_types = central_product_types.exclude(type__in=list(local_product_types_types))

        local_test_types_names = local_test_types.values_list("name", flat=True)
        central_test_types = central_test_types.exclude(name__in=list(local_test_types_names))

        rows = central_product_types.count()
        bulks = rows//bulk_size
        last_bulk = rows-(rows-(bulks*bulk_size))
        for i in range(bulks):
            existing_product_types_ram = list(central_product_types[i*bulk_size:(i+1)*bulk_size])
            ProductType.objects.using(to_db).bulk_create(existing_product_types_ram)
        existing_product_types_ram = list(central_product_types[last_bulk:rows])
        ProductType.objects.using(to_db).bulk_create(existing_product_types_ram)

        rows = central_test_types.count()
        bulks = rows // bulk_size
        last_bulk = rows - (rows - (bulks * bulk_size))
        for i in range(bulks):
            existing_test_types_ram = list(central_test_types[i*bulk_size:(i+1)*bulk_size])
            TestType.objects.using(to_db).bulk_create(existing_test_types_ram)
        existing_test_types_ram = list(central_test_types[last_bulk:rows])
        TestType.objects.using(to_db).bulk_create(existing_test_types_ram)
        # while central_product_types.exists() or central_test_types.exists():
        #     # write product_types to_db
        #     existing_product_types_ram = list(central_product_types[0:1000])
        #     ProductType.objects.using(to_db).bulk_create(existing_product_types_ram)
        #     existing_test_types_ram = list(central_test_types[0:1000])
        #     TestType.objects.using(to_db).bulk_create(existing_test_types_ram)
        #     central_product_types.using()
        #     #central_test_types
    else:
        module_logger.warning('Not synced with central DB')


for db in databases:
    try:
        preset_tables(db, False)
    except Exception as ee:
        module_logger.info("Notification sended")
        #utils.send_email(subject='Error', emailText='{}, {}'.format(datetime.datetime.now(),ee))
    try:
        preset_tables_from_db('default', 'local', True)
    except Exception as ee:
        utils.send_email(subject='Error', emailText='{}, {}'.format(datetime.datetime.now(), ee))
        module_logger.warning("Central database not available, changes have not been made to local database")



if __name__ == '__main__':
    preset_tables()
