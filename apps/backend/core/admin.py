from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest


class NoAddDeleteAdmin[M: Model](admin.ModelAdmin[M]):
    """Staff may look, never add or delete: the rows are written and removed only by the app's
    own flows (an audit trail; GitHub connections and data, which disconnect and delete-data
    remove together with what depends on them)."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False


class ViewOnlyAdmin[M: Model](NoAddDeleteAdmin[M]):
    """Staff may look, never add, change or delete: rows written by background work (jobs,
    analysis, discovery) under its own claims and locks. A save would bypass them (and
    ``auto_now`` fields would move); a delete would cascade outside the deletion routine."""

    def has_change_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return False
