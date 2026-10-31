"""Tarea ``folder_import``: enlaza una carpeta de música con el catálogo.

``folder_import`` task: links a folder of music to the catalogue.
"""

from pathlib import Path
from typing import Any

from activity.services import log_activity
from catalog.services.folder_import import FolderImporter
from integrations.deezer import DeezerClient
from jobs import registry
from jobs.models import JobRun
from preferences.models import get_value


@registry.register("folder_import")
def folder_import(run: JobRun, params: dict[str, Any]) -> dict[str, Any]:
    """Importa la subcarpeta ``params["folder"]`` de la carpeta de descargas.

    Imports the ``params["folder"]`` subfolder of the downloads folder.

    Args:
        run: Ejecución en curso. / Current run.
        params: ``folder`` (texto, relativo a ``download.folder``; vacío o ``.`` es
            la carpeta entera). / ``folder`` (text, relative to ``download.folder``;
            empty or ``.`` is the whole folder).

    Returns:
        Contadores, ``unlinked`` con cada fichero no enlazado y su motivo, y
        ``completed``. / Counters, ``unlinked`` with each file not linked and its
        reason, and ``completed``.

    Raises:
        ValueError: Si ``folder`` no es texto o sale de la carpeta de descargas.
            If ``folder`` is not text or leaves the downloads folder.
    """
    folder = params.get("folder", "")
    if not isinstance(folder, str):
        raise ValueError("«folder» debe ser una ruta relativa a la carpeta de descargas.")
    importer = FolderImporter(run, DeezerClient(), Path(get_value("download.folder")))
    completed = importer.import_folder(folder)
    summary: dict[str, Any] = {**importer.counts, "completed": completed}
    log_activity(
        run.user,
        "catalog.folder_import",
        detail={
            "folder": folder,
            "linked": importer.linked,
            "unlinked": len(importer.unlinked),
        },
    )
    return summary
