from django.contrib import admin

from accounts.models import StaffProfile,ParentProfile


admin.site.register(StaffProfile)
admin.site.register(ParentProfile)