"""Operaciones de mantenimiento del catálogo. / Catalogue maintenance operations.

Each operation reports what it finds and never deletes anything: retagging only
rewrites the tags of files that exist, and missing files are listed, not removed.

Cada operación informa de lo que encuentra y nunca borra nada: volver a etiquetar
solo reescribe las etiquetas de ficheros existentes, y los que faltan se listan.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import mutagen
import requests

from activity.services import log_activity
from catalog.models import Album, Download, Track
from integrations.audio import AudioError, Tags, write_tags
from integrations.deezer import DeezerClient, DeezerError
from integrations.http import build_session
from jobs import runner
from jobs.models import JobRun, JobRunLine

RETAG = "retag"
CHECK_FILES = "check_files"
REVIEW_ARTISTS = "review_artists"
#: Orden fijo de ejecución. / Fixed execution order.
OPERATIONS = (RETAG, CHECK_FILES, REVIEW_ARTISTS)

CoverFetcher = Callable[[str], bytes]


def download_cover(url: str) -> bytes:
    """Descarga la portada de un álbum. / Downloads an album cover.

    Args:
        url: Dirección de la imagen. / Image address.

    Returns:
        Bytes de la imagen. / The image bytes.

    Raises:
        requests.RequestException: Si la descarga falla. / If the download fails.
    """
    with build_session() as session:
        response = session.get(url)
        response.raise_for_status()
        return response.content


def _tags(track: Track, cover: bytes | None) -> Tags:
    """Etiquetas de una canción a partir de la base de datos. / Tags of a track from the database.

    ``write_tags`` replaces every tag, so the full set is always rebuilt here.
    """
    album = track.album
    artists = track.credits.order_by("position").values_list("artist__name", flat=True)
    return Tags(
        title=track.title,
        artists=tuple(artists),
        album=album.title,
        track_number=track.track_number,
        disc_number=track.disc_number,
        year=album.release_date.year if album.release_date else None,
        isrc=track.isrc,
        cover=cover,
    )


def _cover(album: Album, covers: dict[int, bytes | None], fetch: CoverFetcher) -> bytes | None:
    """Portada del álbum, una sola descarga por ejecución. / Album cover, fetched once per run.

    A failed download raises and is not cached, so the file is skipped instead of
    being written without its cover.
    """
    if album.pk not in covers:
        covers[album.pk] = fetch(album.cover_url) if album.cover_url else None
    return covers[album.pk]


def retag_downloads(run: JobRun, fetch_cover: CoverFetcher = download_cover) -> dict[str, Any]:
    """Vuelve a escribir las etiquetas de cada descarga. / Rewrites the tags of every download.

    Args:
        run: Ejecución que registra el progreso. / Run that records the progress.
        fetch_cover: Descarga de portadas; se sustituye en los tests.
            Cover download; replaced in tests.

    Returns:
        Número de ficheros etiquetados y de fallidos. / Count of retagged and failed files.
    """
    # ``Download.objects`` is typed on the append-only base class; the cast keeps the
    # concrete model for mypy. Query results are always ``Download`` rows.
    downloads = cast(
        list[Download], list(Download.objects.select_related("track__album").order_by("pk"))
    )
    covers: dict[int, bytes | None] = {}
    retagged = failed = 0
    for index, download in enumerate(downloads, start=1):
        if runner.should_stop(run):
            break
        path = Path(download.file_path)
        runner.progress(run, index, len(downloads), path.name)
        if not path.is_file():
            failed += 1
            runner.line(run, JobRunLine.Level.WARNING, f"Falta el fichero: {path}")
            continue
        try:
            cover = _cover(download.track.album, covers, fetch_cover)
            write_tags(path, _tags(download.track, cover))
        except (AudioError, OSError, mutagen.MutagenError, requests.RequestException) as error:
            failed += 1
            runner.line(run, JobRunLine.Level.WARNING, f"No se pudo etiquetar {path}: {error}")
        else:
            retagged += 1
    if retagged:
        log_activity(run.user, "catalog.download.retagged", detail={"count": retagged})
    return {"retagged": retagged, "failed": failed}


def check_download_files(run: JobRun) -> dict[str, Any]:
    """Comprueba que cada descarga sigue en disco; no borra nada. / Checks downloads are on disk.

    Returns:
        Número revisado y identificadores de las descargas cuyo fichero falta.
        Number checked and ids of downloads whose file is missing.
    """
    downloads = cast(list[Download], list(Download.objects.order_by("pk")))
    missing: list[int] = []
    checked = 0
    for download in downloads:
        if runner.should_stop(run):
            break
        checked += 1
        runner.progress(run, checked, len(downloads), Path(download.file_path).name)
        if not Path(download.file_path).is_file():
            missing.append(download.pk)
            runner.line(
                run,
                JobRunLine.Level.WARNING,
                f"Falta el fichero de la descarga #{download.pk}: {download.file_path}",
            )
    return {"checked": checked, "missing": missing}


def review_track_artists(run: JobRun, client: DeezerClient | None = None) -> dict[str, Any]:
    """Compara los créditos de cada canción con Deezer. / Compares each track's credits with Deezer.

    The comparison goes through ``parse_track``, so the collaboration rules (guests
    named in the title, ``feat.`` handling) are applied the same way as on import.
    Differences are reported; the credits are not changed here.

    Args:
        run: Ejecución que registra el progreso. / Run that records the progress.
        client: Cliente de Deezer; se sustituye en los tests.
            Deezer client; replaced in tests.

    Returns:
        Canciones revisadas, con diferencias y con error de consulta.
        Tracks reviewed, with differences and with failed lookups.
    """
    if client is None:
        client = DeezerClient()
    # Pairs each track with its id, so the lookup below never sees an empty id.
    tracks = [
        (track, track.deezer_id)
        for track in Track.objects.filter(deezer_id__isnull=False).prefetch_related(
            "credits__artist"
        )
        if track.deezer_id is not None
    ]
    reviewed = differences = errors = 0
    for index, (track, deezer_id) in enumerate(tracks, start=1):
        if runner.should_stop(run):
            break
        reviewed += 1
        runner.progress(run, index, len(tracks), track.title)
        stored = {
            credit.artist.name.casefold(): credit.artist.name for credit in track.credits.all()
        }
        try:
            remote = client.get_track(deezer_id)
        except (DeezerError, requests.RequestException) as error:
            errors += 1
            runner.line(
                run, JobRunLine.Level.WARNING, f"No se pudo consultar «{track.title}»: {error}"
            )
            continue
        expected = {ref.name.casefold(): ref.name for ref in remote.artists}
        missing = sorted(expected[key] for key in expected.keys() - stored.keys())
        extra = sorted(stored[key] for key in stored.keys() - expected.keys())
        if missing or extra:
            differences += 1
            runner.line(
                run,
                JobRunLine.Level.WARNING,
                f"Créditos distintos en «{track.title}» (Deezer #{deezer_id}): "
                f"faltan {', '.join(missing) or 'ninguno'}; sobran {', '.join(extra) or 'ninguno'}",
            )
    return {"reviewed": reviewed, "differences": differences, "errors": errors}
