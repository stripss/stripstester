from django.db import models

# Create your models here.

sql_test_type_table = """CREATE TABLE IF NOT EXISTS test_type(
            id serial primary key,
            name varchar(32) UNIQUE,
            description varchar(128),
            units varchar(32) );"""

class ProductType(models.Model):
    type = models.IntegerField(unique=True, null=False, blank=False)
    name = models.CharField(max_length=32, unique=True, null=False, blank=False)
    variant = models.CharField(max_length=32, null=True, blank=True)
    description = models.TextField(max_length=128, null=True, blank=True)

class Product(models.Model):
    serial = models.BigIntegerField(unique=True, null=False, blank=False)
    production_datetime = models.DateTimeField()
    hw_release = models.CharField(max_length=32, null=True, blank=True)
    notes = models.CharField(max_length=32, null=True, blank=True)
    type = models.ForeignKey(ProductType, on_delete=models.PROTECT)

sql_test_table = """ CREATE TABLE IF NOT EXISTS test(
            id serial primary key,
            value float,
            result varchar(8),
            datetime timestamp,
            test_device_name varchar(32),
            employee varchar(32),
            product_id integer,
            test_type_id integer,
            foreign key (product_id) references product(id),
            foreign key (test_type_id) references test_type(id) );"""

class Test(models.Model):
    value = models.DecimalField(max_digits=10, decimal_places=3)
    result = models.CharField(max_length=16, null=False)


