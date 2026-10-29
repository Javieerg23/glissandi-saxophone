"""Rutas raíz del proyecto. / Project root URLs."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

API_APPS = ["accounts", "catalog", "jobs", "watches", "proxies", "activity", "preferences"]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/", include("core.urls")),
    *(path(f"api/v1/{app}/", include(f"{app}.urls")) for app in API_APPS),
]
