from django.urls import path

from .api import DataVersionsView, SyncStatusView

urlpatterns = [
    path("status", SyncStatusView.as_view(), name="sync-status"),
    path("versions", DataVersionsView.as_view(), name="sync-versions"),
]
