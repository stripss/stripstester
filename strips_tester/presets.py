import os
import django
import logging
from strips_tester import utils
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_project.settings")
django.setup()
# first time check & create admin user
from django.contrib.auth.models import User, Group
from web_project.web_app.models import *
from strips_tester import DB

# name hardcoded, because program starts here so it would be "main" otherwise
module_logger = logging.getLogger(".".join(("strips_tester", "tester")))
databases = ['default', "local", ]



def preset_tables(database, flag):
    if flag:
        #USERS
        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser('admin', 'admin@admin.com', 'admin')
        # PRODUCT TYPES
        ProductType.objects.using(database).get_or_create(name='MVC', type=1, variant='basic', description='mvc module for Garo')
        for product_type in TestType.objects.all():
            print(product_type.type, product_type.name, product_type.variant, product_type.description)
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
        TestType.objects.using(database).get_or_create(name='relay', description='relay status', units='bool')
        TestType.objects.using(database).get_or_create(name='keyboard', description='bushbutton status', units='bool')
        for test in TestType.objects.all():
            print(test.name, test.description, test.units)
    else:
        module_logger.info('NO table preset')


for db in databases:
    try:
        preset_tables(db, False)
    except Exception as ee:
        module_logger.info("Notification sended")
        utils.send_email(subject='Error', emailText='{}, {}'.format(datetime.datetime.now(),ee))

if __name__ == '__main__':
    preset_tables()
