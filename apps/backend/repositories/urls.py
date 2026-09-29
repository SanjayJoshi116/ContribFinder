from django.urls import path

from .api import CandidateListView, DiscoveryStatusView

urlpatterns = [
    path("status", DiscoveryStatusView.as_view(), name="discovery-status"),
    path("candidates", CandidateListView.as_view(), name="discovery-candidates"),
]
