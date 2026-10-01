from django.urls import path

from developers.api import InterestListView, SkillListView
from jobs.api import StartSyncView

from .api import GitHubDataView, GitHubProfileView, RepositoryListView

urlpatterns = [
    path("sync", StartSyncView.as_view(), name="profile-sync"),
    path("github", GitHubProfileView.as_view(), name="profile-github"),
    path("github-data", GitHubDataView.as_view(), name="profile-github-data"),
    path("repositories", RepositoryListView.as_view(), name="profile-repositories"),
    path("skills", SkillListView.as_view(), name="profile-skills"),
    path("interests", InterestListView.as_view(), name="profile-interests"),
]
