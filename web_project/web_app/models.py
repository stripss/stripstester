from django.db import models

# Create your models here.


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


class TestType(models.Model):
    name = models.CharField(max_length=32, unique=True, null=False, blank=False)
    description = models.CharField(max_length=128, null=True, blank=True)
    units = models.CharField(max_length=32, null=False, blank=False)


class Test(models.Model):
    value = models.FloatField()
    result = models.CharField(max_length=16, null=False, blank=False)
    datetime = models.DateTimeField(auto_now_add=True)
    test_device_name = models.CharField(max_length=32, null=False, blank=False)
    employee = models.CharField(max_length=32, null=True, blank=True)
    product_id = models.ForeignKey(Product, on_delete=models.CASCADE)  # if we delete product we have no use for it's tests
    test_type_id = models.ForeignKey(TestType, on_delete=models.PROTECT)  # prevent TestType deletion


