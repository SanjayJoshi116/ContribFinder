from django.urls import path

from feedback.api import DismissView, FeedbackView, SaveView

from .api import RecommendationDetailView, RecommendationStatusView

# The list is routed as /recommendations (no trailing slash) in config/urls.py.
urlpatterns = [
    path("status", RecommendationStatusView.as_view(), name="recommendations-status"),
    path("<int:pk>", RecommendationDetailView.as_view(), name="recommendation-detail"),
    path("<int:pk>/feedback", FeedbackView.as_view(), name="recommendation-feedback"),
    path("<int:pk>/save", SaveView.as_view(), name="recommendation-save"),
    path("<int:pk>/dismiss", DismissView.as_view(), name="recommendation-dismiss"),
]
