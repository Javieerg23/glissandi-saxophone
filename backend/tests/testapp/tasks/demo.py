"""Tarea de prueba para el autodescubrimiento. / Test task for autodiscovery."""

from typing import Any

from jobs import registry
from jobs.models import JobRun


@registry.register("testapp_demo")
def demo(run: JobRun, params: dict[str, Any]) -> None:
    """Tarea vacía. / Empty task."""
