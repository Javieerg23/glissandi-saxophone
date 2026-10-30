"""Administración de la app ``jobs``, solo lectura. / ``jobs`` app admin, read only."""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from .models import JobRun, JobRunLine


class ReadOnlyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Base sin altas, cambios ni borrados. / Base with no adds, changes or deletes."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Se crean desde el motor. / Created by the engine."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Solo lectura. / Read only."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """No se borran. / Never deleted."""
        return False


@admin.register(JobRun)
class JobRunAdmin(ReadOnlyAdmin):
    """Ejecuciones de tareas. / Task runs."""

    list_display = ("kind", "status", "user", "started_at", "finished_at", "done", "total")
    list_filter = ("kind", "status")


@admin.register(JobRunLine)
class JobRunLineAdmin(ReadOnlyAdmin):
    """Líneas de registro de las ejecuciones. / Run log lines."""

    list_display = ("run", "position", "level", "message", "created_at")
    list_filter = ("level",)
