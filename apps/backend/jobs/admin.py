from django.contrib import admin

from .models import SyncJob


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin[SyncJob]):
    list_display = ("id", "user", "job_type", "status", "attempts", "error_code", "created_at")
    list_filter = ("job_type", "status")
    readonly_fields = [f.name for f in SyncJob._meta.fields]
