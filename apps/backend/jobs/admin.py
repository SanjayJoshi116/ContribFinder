from django.contrib import admin

from core.admin import ViewOnlyAdmin

from .models import SyncJob


@admin.register(SyncJob)
class SyncJobAdmin(ViewOnlyAdmin[SyncJob]):
    """View only: jobs are written by their workers under a claim, and ``updated_at`` is the
    heartbeat, so a save here would overwrite a worker's update or revive a dead job."""

    list_display = ("id", "user", "job_type", "status", "attempts", "error_code", "created_at")
    list_filter = ("job_type", "status")
    list_select_related = ("user",)
    readonly_fields = [f.name for f in SyncJob._meta.fields]
