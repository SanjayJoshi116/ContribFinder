from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest

from .models import AuditEvent, User

admin.site.register(User, UserAdmin)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin[AuditEvent]):
    list_display = ("created_at", "action", "outcome", "user")
    list_filter = ("action", "outcome")
    list_select_related = ("user",)
    readonly_fields = ("user", "action", "outcome", "metadata", "ip_hash", "created_at")

    # An audit trail: read-only for staff, no additions or deletions.
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: AuditEvent | None = None) -> bool:
        return False
