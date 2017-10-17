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