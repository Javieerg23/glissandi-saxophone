"""Administración de la app ``watches``. / ``watches`` app admin."""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from simple_history.admin import SimpleHistoryAdmin

from .models import Watch, WatchRun


@admin.register(Watch)
class WatchAdmin(SimpleHistoryAdmin):  # type: ignore[misc]
    """Vigilancias editables con historial. / Editable watches with history."""

    list_display = ("name", "enabled", "updated_at")
    search_fields = ("name",)


@admin.register(WatchRun)
class WatchRunAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Consulta de ejecuciones; no se crean ni se cambian a mano.

    Read-only view of runs: they are written by the service, never by hand.
    """

    list_display = ("watch", "status", "found", "finished_at")
    list_filter = ("status",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Las ejecuciones las escribe el servicio. / Runs are written by the service."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Solo de lectura. / Read-only."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Solo de lectura. / Read-only."""
        return False
