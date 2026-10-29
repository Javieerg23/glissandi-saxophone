"""Administración de la app ``preferences``. / ``preferences`` app admin."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Preference


@admin.register(Preference)
class PreferenceAdmin(SimpleHistoryAdmin):  # type: ignore[misc]
    """Ajustes con historial. / Settings with history."""

    list_display = ("key", "updated_at")
    search_fields = ("key",)
