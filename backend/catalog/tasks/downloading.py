"""Tarea ``download``: descarga las canciones pendientes del catálogo.

``download`` task: downloads the catalogue's pending tracks.
"""

from pathlib import Path
from typing import Any

from activity.services import log_activity
from catalog.models import Track
from catalog.services.downloading import build_pool, download_track
from integrations.audio import FORMATS
from jobs import registry, runner
from jobs.models import JobRun, JobRunLine
from preferences.models import get_value


def _pending(params: dict[str, Any]) -> list[Track]:
    """Canciones a descargar según los parámetros, sin las ya descargadas.

    Tracks to download per the params, leaving out the already downloaded ones.

    Raises:
        ValueError: Si no indica ni ``track_ids`` ni ``all_pending``.
    """
    tracks = Track.objects.filter(download__isnull=True)
    if params.get("all_pending"):
        return list(tracks.select_related("album"))
    if params.get("track_ids"):
        return list(tracks.filter(pk__in=params["track_ids"]).select_related("album"))
    raise ValueError("Indica «track_ids» o «all_pending».")


@registry.register("download")
def download(run: JobRun, params: dict[str, Any]) -> dict[str, Any]:
    """Descarga canciones una a una; el fallo de una no detiene las demás.

    Downloads tracks one by one; one failing does not stop the rest. Stopping is
    cooperative and only checked between tracks.

    Args:
        run: Ejecución en curso. / Current run.
        params: ``{"track_ids": [...]}`` o ``{"all_pending": true}``.

    Returns:
        Resumen con ``downloaded``, ``failed`` y ``skipped``.
        Summary with ``downloaded``, ``failed`` and ``skipped``.
    """
    fmt = get_value("download.format")
    if fmt not in FORMATS:
        raise ValueError(f"Formato de descarga no soportado: {fmt}")
    folder = Path(get_value("download.folder"))
    template = get_value("download.name_template")
    tracks = _pending(params)
    requested = len(params.get("track_ids") or [])
    skipped = max(requested - len(tracks), 0)
    pool = build_pool()
    downloaded = failed = 0
    for index, track in enumerate(tracks):
        if runner.should_stop(run):
            runner.line(run, JobRunLine.Level.WARNING, "Parada solicitada.")
            break
        runner.progress(run, index, len(tracks), track.title)
        try:
            result = download_track(track, pool, fmt=fmt, folder=folder, template=template)
        except Exception as error:  # noqa: BLE001  # una canción rota no debe parar el resto / one bad track must not stop the rest
            failed += 1
            runner.line(run, JobRunLine.Level.ERROR, f"{track.title}: {error}")
        else:
            downloaded += 1
            runner.line(run, JobRunLine.Level.INFO, f"{track.title} → {result.file_path}")
    else:
        runner.progress(run, len(tracks), len(tracks))
    summary = {"downloaded": downloaded, "failed": failed, "skipped": skipped}
    log_activity(run.user, "catalog.download.finished", detail=summary)
    return summary
