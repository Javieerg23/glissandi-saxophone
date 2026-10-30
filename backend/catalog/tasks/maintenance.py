"""Tarea ``maintenance``: utilidades del catálogo. / ``maintenance`` task: catalogue utilities.

El usuario elige las operaciones en ``params["operations"]``; por defecto, todas.
Users pick the operations in ``params["operations"]``; all of them by default.
"""

from collections.abc import Callable
from typing import Any

from catalog.services.maintenance import (
    CHECK_FILES,
    OPERATIONS,
    RETAG,
    REVIEW_ARTISTS,
    check_download_files,
    retag_downloads,
    review_track_artists,
)
from jobs import runner
from jobs.models import JobRun
from jobs.registry import register

_STEPS: dict[str, Callable[[JobRun], dict[str, Any]]] = {
    RETAG: retag_downloads,
    CHECK_FILES: check_download_files,
    REVIEW_ARTISTS: review_track_artists,
}


@register("maintenance")
def maintenance(run: JobRun, params: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta las operaciones pedidas, en orden fijo. / Runs the requested operations in order.

    Raises:
        ValueError: Si ``operations`` no es una lista de operaciones conocidas.
            If ``operations`` is not a list of known operations.
    """
    operations = params.get("operations", list(OPERATIONS))
    if not isinstance(operations, list) or not all(op in OPERATIONS for op in operations):
        raise ValueError("Operación de mantenimiento desconocida.")
    summary: dict[str, Any] = {}
    for name in OPERATIONS:
        if name in operations and not runner.should_stop(run):
            summary[name] = _STEPS[name](run)
    return summary
