"""Rutas de la app ``accounts``. / ``accounts`` app URLs."""

from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from . import views
from .user_views import UserViewSet

router = SimpleRouter()
router.register("users", UserViewSet, basename="users")

urlpatterns: list[URLPattern | URLResolver] = [
    path("setup/", views.SetupView.as_view(), name="setup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("password/", views.PasswordChangeView.as_view(), name="password"),
    path("username/", views.UsernameChangeView.as_view(), name="username"),
    *router.urls,
]
