from django.urls import path

from .api import IssueDetailView

urlpatterns = [
    path("<int:pk>", IssueDetailView.as_view(), name="issue-detail"),
]
