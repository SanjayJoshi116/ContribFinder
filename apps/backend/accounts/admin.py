from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditEvent, User

admin.site.register(User, UserAdmin)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin[AuditEvent]):
    list_display = ("created_at", "action", "outcome", "user")
    list_filter = ("action", "outcome")
    readonly_fields = ("user", "action", "outcome", "metadata", "ip_hash", "created_at")
