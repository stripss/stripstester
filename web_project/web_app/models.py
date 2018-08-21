from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.dateformat import format


# Create your models here.

class StrModel(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return ", ".join((key+": "+str(self.__dict__[key]) for key in self.__dict__ if key is not "_state"))

class ProductType(StrModel):
    type = models.IntegerField(unique=True, null=False, blank=False)
    name = models.CharField(max_length=32, unique=True, null=False, blank=False)
    variant = models.CharField(max_length=32, null=True, blank=True)
    description = models.TextField(max_length=128, null=True, blank=True)



class Product(StrModel):
    serial = models.BigIntegerField(unique=True, null=True, blank=True)
    production_datetime = models.DateTimeField(null=True)
    hw_release = models.CharField(max_length=32, null=True, blank=True)
    notes = models.CharField(max_length=32, null=True, blank=True)
    type = models.ForeignKey(ProductType, on_delete=models.PROTECT)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_results = []
        self.tests = {}
        self.raw_scanned_string = None
        self.test_status = False
        self.mac = None



class TestType(StrModel):
    name = models.CharField(unique=True, max_length=32, null=False, blank=False)
    description = models.CharField(max_length=128, null=True, blank=True)
    units = models.CharField(max_length=32, null=False, blank=False)




class TestSet(StrModel):
    datetime = models.DateTimeField(auto_now_add=False)
    status = models.BooleanField(null=False, blank=False)
    test_device_name = models.CharField(max_length=32, null=False, blank=False)
    employee = models.CharField(max_length=32, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # if we delete product we have no use for it's tests



class Test(StrModel):
    value = models.FloatField()
    value_str = models.CharField(max_length=128, null=True, blank=True)
    RESULT_OK = "ok"
    RESULT_FAIL = "fail"
    RESULT_UNTESTED = "untested"
    RESULT_CHOICES = ((RESULT_OK, "ok"), (RESULT_FAIL, "fail"), (RESULT_UNTESTED, "untested"))
    result = models.CharField(max_length=16, null=False, blank=False, choices=RESULT_CHOICES)
    #datetime = models.DateTimeField(auto_now_add=True)
    #test_device_name = models.CharField(max_length=32, null=False, blank=False)
    #employee = models.CharField(max_length=32, null=True, blank=True)
    #product = models.ForeignKey(Product, on_delete=models.CASCADE)  #  if we delete product we have no use for it's tests
    test_set = models.ForeignKey(TestSet, on_delete=models.CASCADE)
    type = models.ForeignKey(TestType, on_delete=models.PROTECT)  # prevent TestType deletion



# Stores data of test devices
class TestDevice(StrModel):
    name = models.TextField(max_length=64, null=True, blank=True)
    author = models.TextField(max_length=64, null=True, blank=True)
    service = models.IntegerField(null=True, blank=True)
    manual = models.TextField(max_length=256, null=True, blank=True)
    countdate = models.TextField(max_length=32, null=True, blank=True)
    calibrationdate = models.TextField(max_length=32, null=True, blank=True)


# Stores log data of test, more detailed data is stored in following TestDevice_Data model
class TestDevice_Test(StrModel):
    datetime = models.DateTimeField(auto_now_add=False)
    serial = models.TextField(max_length=128, null=True, blank=True)
    employee = models.IntegerField(null=True, blank=True)
    test_type = models.TextField(max_length=32, null=True, blank=True)
    result = models.IntegerField(null=True, blank=True)
    countgood = models.IntegerField(null=True, blank=True)
    countbad = models.IntegerField(null=True, blank=True)
    test_device_id = models.IntegerField(null=True, blank=True)

    # Holds all data from test
    data = JSONField(null=True, blank=True)
