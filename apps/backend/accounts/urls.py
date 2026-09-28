from django.urls import path

from . import views

urlpatterns = [
    path("github", views.GitHubLoginView.as_view(), name="auth-github"),
    path("github/callback", views.GitHubCallbackView.as_view(), name="auth-github-callback"),
    path("github/disconnect", views.GitHubDisconnectView.as_view(), name="auth-github-disconnect"),
    path("csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("me", views.MeView.as_view(), name="auth-me"),
    path("logout", views.LogoutView.as_view(), name="auth-logout"),
]
