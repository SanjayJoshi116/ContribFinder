from django.urls import path

from .api import DismissedDetailView, DismissedListView, SavedDetailView, SavedListView

urlpatterns = [
    path("saved", SavedListView.as_view(), name="saved"),
    path("saved/<int:repository_id>", SavedDetailView.as_view(), name="saved-detail"),
    path("dismissed", DismissedListView.as_view(), name="dismissed"),
    path("dismissed/<int:repository_id>", DismissedDetailView.as_view(), name="dismissed-detail"),
]
