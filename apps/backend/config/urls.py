from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("core.urls")),
    path("auth/", include("accounts.urls")),
    path("profile/", include("github.urls")),
    path("sync/", include("jobs.urls")),
]

urlpatterns = [
    path("api/v1/", include(api_v1)),
    path("admin/", admin.site.urls),
]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
