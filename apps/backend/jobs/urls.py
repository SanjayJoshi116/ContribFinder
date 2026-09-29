from django.urls import path

from .api import SyncStatusView

urlpatterns = [path("status", SyncStatusView.as_view(), name="sync-status")]
