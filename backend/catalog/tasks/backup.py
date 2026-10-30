"""Tarea ``library_restore``: importa una copia subida. / Restores an uploaded backup.

``params["file"]`` es el nombre del fichero que dejó la API en la carpeta temporal;
la tarea lo borra al acabar, salga bien o mal.
``params["file"]`` names the file the API left in the temp folder; the task deletes
it when done, whatever the outcome.
"""

from typing import Any

from django.utils.translation import gettext as _

from accounts.roles import is_administrator
from catalog.backup import parse_backup, restore, upload_path
from jobs import runner
from jobs.models import JobRun, JobRunLine
from jobs.registry import register


@register("library_restore")
def library_restore(run: JobRun, params: dict[str, Any]) -> dict[str, Any]:
    """Añade a la biblioteca lo que falta de la copia. / Adds what the library is missing.

    Raises:
        PermissionError: Si no la lanzó un administrador. La API de tareas deja lanzar
            cualquier tipo a cualquier usuario, así que se comprueba aquí.
            If an administrator did not start it. The jobs API lets any user start any
            kind, so it is checked here.
        BackupError: Si el fichero no es válido. / If the file is not valid.
    """
    if run.user is None or not is_administrator(run.user):
        raise PermissionError(_("Solo un administrador puede importar la biblioteca."))
    path = upload_path(params.get("file"))
    try:
        summary = restore(parse_backup(path.read_bytes()))
    finally:
        path.unlink(missing_ok=True)
    runner.progress(run, 1, 1)
    runner.line(
        run,
        JobRunLine.Level.INFO,
        _("%(created)d elementos añadidos, %(skipped)d ya existían.") % summary,
    )
    return summary
