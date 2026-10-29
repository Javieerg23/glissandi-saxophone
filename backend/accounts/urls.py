"""Rutas de la app ``accounts``. / ``accounts`` app URLs."""

from django.urls import path

from . import views

urlpatterns = [
    path("setup/", views.SetupView.as_view(), name="setup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("password/", views.PasswordChangeView.as_view(), name="password"),
    path("username/", views.UsernameChangeView.as_view(), name="username"),
]
