from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.admin import NoAddDeleteAdmin

from .models import AuditEvent, User

admin.site.register(User, UserAdmin)


@admin.register(AuditEvent)
class AuditEventAdmin(NoAddDeleteAdmin[AuditEvent]):
    """An audit trail: read-only for staff."""

    list_display = ("created_at", "action", "outcome", "user")
    list_filter = ("action", "outcome")
    list_select_related = ("user",)
    readonly_fields = ("user", "action", "outcome", "metadata", "ip_hash", "created_at")
