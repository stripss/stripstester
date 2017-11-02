from django.db import models

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


class TestType(StrModel):
    name = models.CharField(unique=True, max_length=32, null=False, blank=False)
    description = models.CharField(max_length=128, null=True, blank=True)
    units = models.CharField(max_length=32, null=False, blank=False)


class Test(StrModel):
    value = models.FloatField()
    result = models.CharField(max_length=16, null=False, blank=False)
    datetime = models.DateTimeField(auto_now_add=True)
    test_device_name = models.CharField(max_length=32, null=False, blank=False)
    employee = models.CharField(max_length=32, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)  # if we delete product we have no use for it's tests
    type = models.ForeignKey(TestType, on_delete=models.PROTECT)  # prevent TestType deletion


