# Register your models here.
from django.contrib import admin
from django.apps import apps

# registration for admin pages. Try/cache because admin may be imported and run more than once.
try:
    app = apps.get_app_config('web_app')
    for model_name, model in app.models.items():
        admin.site.register(model)
except admin.sites.AlreadyRegistered:
    print("AlreadyRegistered Exception")