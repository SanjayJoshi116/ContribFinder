from django.urls import path

from jobs.api import StartSyncView

from .api import GitHubProfileView, RepositoryListView

urlpatterns = [
    path("sync", StartSyncView.as_view(), name="profile-sync"),
    path("github", GitHubProfileView.as_view(), name="profile-github"),
    path("repositories", RepositoryListView.as_view(), name="profile-repositories"),
]
