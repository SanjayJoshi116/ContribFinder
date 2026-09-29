from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

from developers.api import DeveloperProfileView

api_v1: list[URLPattern | URLResolver] = [
    path("", include("core.urls")),
    path("auth/", include("accounts.urls")),
    path("profile", DeveloperProfileView.as_view(), name="profile"),
    path("profile/", include("github.urls")),
    path("sync/", include("jobs.urls")),
    path("discovery/", include("repositories.urls")),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
    path("admin/", admin.site.urls),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
