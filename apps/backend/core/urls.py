from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny

from .api import HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path(
        "schema/",
        SpectacularAPIView.as_view(authentication_classes=[], permission_classes=[AllowAny]),
        name="schema",
    ),
]
