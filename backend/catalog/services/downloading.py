"""Descarga de una canción: búsqueda, audio, conversión, etiquetas y registro.

Download of a single track: search, audio, conversion, tags and bookkeeping.
"""

import shutil
import tempfile
import time
from pathlib import Path

from django.db.models import F
from django.utils import timezone

from catalog.models import Download, Track
from integrations.audio import Tags, convert, render_path, write_tags
from integrations.youtube import ProxyPool, YoutubeError, download_audio, find_best_video
from proxies.models import Proxy


class TrackNotDownloadable(Exception):  # noqa: N818
    """La canción no se puede descargar (sin duración o sin vídeo adecuado).

    The track cannot be downloaded (no duration or no matching video).
    """


def build_pool() -> ProxyPool:
    """Crea el grupo con los proxies activos; sin ninguno, conexión directa.

    Builds the pool from the enabled proxies; with none, a direct connection.
    """
    return ProxyPool(list(Proxy.objects.filter(enabled=True).values_list("url", flat=True)))


def _record_proxy(url: str | None, *, ok: bool) -> None:
    """Actualiza los contadores del proxy usado. / Updates the used proxy's counters."""
    if url is None:
        return
    now = timezone.now()
    if ok:
        Proxy.objects.filter(url=url).update(success_count=F("success_count") + 1, last_used_at=now)
    else:
        Proxy.objects.filter(url=url).update(
            failure_count=F("failure_count") + 1, last_used_at=now, last_failed_at=now
        )


def _tags(track: Track) -> Tags:
    """Etiquetas de la canción desde el catálogo. / The track's tags from the catalogue."""
    album = track.album
    return Tags(
        title=track.title,
        artists=tuple(
            track.artists.order_by("track_credits__position").values_list("name", flat=True)
        ),
        album=album.title,
        track_number=track.track_number,
        disc_number=track.disc_number,
        year=album.release_date.year if album.release_date else None,
        isrc=track.isrc,
    )


def download_track(
    track: Track, pool: ProxyPool, *, fmt: str, folder: Path, template: str
) -> Download:
    """Descarga una canción, la convierte, la etiqueta y registra el ``Download``.

    Downloads a track, converts and tags it, and records the ``Download``. The
    work happens in a temporary folder and the final file is moved in only when
    it is complete, so a failure never leaves half-written files in the library.

    Args:
        track: Canción a descargar. / Track to download.
        pool: Grupo de proxies compartido por toda la tarea. / Proxy pool shared by the whole task.
        fmt: Formato de salida (clave de ``FORMATS``). / Output format (``FORMATS`` key).
        folder: Carpeta de la biblioteca. / Library folder.
        template: Plantilla de nombres. / Naming template.

    Returns:
        La descarga creada. / The created download.

    Raises:
        TrackNotDownloadable: Sin duración o sin vídeo que encaje.
            No duration, or no video fits.
        NoProxyAvailable: Si todos los proxies están en espera. / If every proxy is cooling down.
        YoutubeError: Si yt-dlp falla. / If yt-dlp fails.
        AudioError: Si falla la conversión o el etiquetado. / If conversion or tagging fails.
    """
    if not track.duration:
        raise TrackNotDownloadable("la canción no tiene duración")
    tags = _tags(track)
    proxy = pool.acquire(time.monotonic())
    try:
        video = find_best_video(tags.title, list(tags.artists), float(track.duration), proxy=proxy)
        if video is None:
            raise TrackNotDownloadable("ningún vídeo coincide con la canción")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            raw = download_audio(video.video_id, work, proxy=proxy)
            converted = convert(raw, work, fmt)
            write_tags(converted, tags)
            dest = folder / render_path(template, tags, converted.suffix.lstrip("."))
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(converted, dest)
    except YoutubeError:
        # Solo cuenta contra el proxy el fallo de la red; no encontrar vídeo no es culpa suya.
        # Only network failures count against the proxy; finding no video is not its fault.
        if proxy is not None:
            pool.report_failure(proxy, time.monotonic())
        _record_proxy(proxy, ok=False)
        raise
    if proxy is not None:
        pool.report_success(proxy)
    _record_proxy(proxy, ok=True)
    return Download.objects.create(
        track=track,
        file_path=str(dest),
        audio_format=fmt,
        source_url=f"https://www.youtube.com/watch?v={video.video_id}",
    )
