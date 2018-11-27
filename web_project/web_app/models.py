from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.dateformat import format


# Create your models here.

class StrModel(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return ", ".join((key+": "+str(self.__dict__[key]) for key in self.__dict__ if key is not "_state"))

# Stores data of test devices
class TestDevice(StrModel):
    name = models.TextField(max_length=64, null=True, blank=True)
    author = models.TextField(max_length=64, null=True, blank=True)
    service = models.IntegerField(null=True, blank=True)
    manual = models.TextField(max_length=256, null=True, blank=True)
    countdate = models.DateTimeField(auto_now_add=False)
    calibrationdate = models.DateTimeField(auto_now_add=False)
    nests = models.IntegerField(null=True, blank=True)


# Stores log data of individual test
class TestDevice_Test(StrModel):
    test_device_id = models.IntegerField(null=True, blank=True)  # Which TN
    datetime = models.DateTimeField(auto_now_add=False)
    employee = models.IntegerField(null=True, blank=True)
    test_type = models.TextField(max_length=32, null=True, blank=True)
    result = models.IntegerField(null=True, blank=True)


# Stores data of individual Product
class TestDevice_Product(StrModel):
    test_id = models.IntegerField(null=True, blank=True) # Which invidual test
    serial = models.TextField(max_length=128, null=True, blank=True)
    ok = models.IntegerField(null=True, blank=True) # Which invidual test
    nest = models.IntegerField(null=True, blank=True) # Which nest

    # Holds all data from test
    measurements = JSONField(null=True, blank=True)
