"""Tarea ``import``: trae artistas de Deezer al catálogo.

``import`` task: brings Deezer artists into the catalogue.
"""

from typing import Any

from django.utils.translation import gettext as _

from activity.services import log_activity
from catalog.services.importing import Importer
from integrations.deezer import DeezerClient
from integrations.musicbrainz.client import MusicBrainzClient
from jobs import registry
from jobs.models import JobRun


@registry.register("import")
def import_artists(run: JobRun, params: dict[str, Any]) -> dict[str, Any]:
    """Importa los artistas de ``params["artist_ids"]``.

    Imports the artists in ``params["artist_ids"]``.

    Args:
        run: Ejecución en curso. / Current run.
        params: ``artist_ids`` (lista de ids de Deezer, obligatoria) y ``verify``
            (bool, verifica con MusicBrainz; por defecto ``False``).
            ``artist_ids`` (list of Deezer ids, required) and ``verify``
            (bool, verifies against MusicBrainz; defaults to ``False``).

    Returns:
        Resumen con los contadores finales. / Summary with the final counters.

    Raises:
        ValueError: Si ``artist_ids`` falta o no es una lista de enteros.
            If ``artist_ids`` is missing or not a list of integers.
    """
    ids = params.get("artist_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
        raise ValueError(_("artist_ids debe ser una lista de ids de Deezer."))
    importer = Importer(run, DeezerClient(), MusicBrainzClient() if params.get("verify") else None)
    completed = importer.import_artists(ids)
    summary: dict[str, Any] = {**importer.counts, "completed": completed}
    log_activity(run.user, "catalog.import", detail={"artist_ids": ids, **summary})
    return summary
