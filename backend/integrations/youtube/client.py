"""Búsqueda y descarga de audio con yt-dlp (como librería).

Audio search and download with yt-dlp, used as a library.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from integrations.youtube.errors import YoutubeError

# Un identificador de vídeo son 11 caracteres de este alfabeto; validarlo evita
# que un valor arbitrario acabe dentro de una URL o de un iframe.
# A video id is 11 chars of this alphabet; validating it keeps arbitrary values
# out of URLs and iframes.
_VIDEO_ID = re.compile(r"[\w-]{11}")

# Fábrica de YoutubeDL; los tests inyectan un doble para no tocar la red.
# YoutubeDL factory; tests inject a double so nothing hits the network.
YdlFactory = Callable[[Any], Any]


@dataclass(frozen=True)
class VideoMatch:
    """Vídeo candidato para una canción. / Candidate video for a track.

    Attributes:
        video_id: Identificador de YouTube. / YouTube id.
        title: Título del vídeo. / Video title.
        duration: Duración en segundos. / Duration in seconds.
    """

    video_id: str
    title: str
    duration: float


@dataclass(frozen=True)
class DownloadProgress:
    """Avance de una descarga. / Download progress.

    Attributes:
        downloaded_bytes: Bytes descargados. / Bytes downloaded so far.
        total_bytes: Tamaño total, o ``None`` si se desconoce. / Total size, or
            ``None`` when unknown.
        finished: ``True`` cuando el fichero está completo. / ``True`` once the
            file is complete.
    """

    downloaded_bytes: int
    total_bytes: int | None
    finished: bool


def preview_embed_url(video_id: str) -> str:
    """URL de previsualización sin cookies de seguimiento.

    Embed URL on ``youtube-nocookie.com``.

    Args:
        video_id: Identificador de YouTube. / YouTube id.

    Returns:
        URL para un ``iframe``. / URL for an ``iframe``.

    Raises:
        ValueError: Si el identificador no tiene el formato de YouTube.
            If the id does not look like a YouTube id.
    """
    if not _VIDEO_ID.fullmatch(video_id):
        raise ValueError(f"Invalid YouTube video id: {video_id!r}")
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


def find_best_video(
    title: str,
    artists: list[str],
    duration: float,
    *,
    tolerance: float = 10.0,
    candidates: int = 5,
    proxy: str | None = None,
    ydl_factory: YdlFactory = YoutubeDL,
) -> VideoMatch | None:
    """Busca el vídeo que mejor encaja con una canción.

    Finds the video that best matches a track. Among the first results, it takes
    the first whose duration is within ``tolerance`` of the track's: YouTube
    already ranks by relevance, and the duration discards live sets and mixes.

    Args:
        title: Título de la canción. / Track title.
        artists: Artistas, en orden. / Artists, in order.
        duration: Duración esperada en segundos. / Expected duration in seconds.
        tolerance: Diferencia máxima admitida en segundos. / Maximum accepted
            difference in seconds.
        candidates: Resultados a examinar. / Results to inspect.
        proxy: URL del proxy a usar. / Proxy URL to use.
        ydl_factory: Fábrica de ``YoutubeDL``. / ``YoutubeDL`` factory.

    Returns:
        El vídeo elegido, o ``None`` si ninguno encaja. / The chosen video, or
        ``None`` when none fits.

    Raises:
        YoutubeError: Si yt-dlp falla. / If yt-dlp fails.
    """
    query = f"ytsearch{candidates}:{', '.join(artists)} - {title}"
    # extract_flat evita resolver cada vídeo: solo hace falta id, título y duración.
    # extract_flat skips resolving each video: only id, title and duration are needed.
    options: dict[str, Any] = {"quiet": True, "extract_flat": True, "proxy": proxy}
    try:
        with ydl_factory(options) as ydl:
            info = ydl.extract_info(query, download=False)
    except DownloadError as exc:
        raise YoutubeError(str(exc)) from exc
    for entry in info.get("entries") or []:
        entry_duration = entry.get("duration")
        if entry_duration is not None and abs(entry_duration - duration) <= tolerance:
            return VideoMatch(entry["id"], entry["title"], float(entry_duration))
    return None


def download_audio(
    video_id: str,
    dest_dir: Path,
    *,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    proxy: str | None = None,
    ydl_factory: YdlFactory = YoutubeDL,
) -> Path:
    """Descarga la mejor pista de audio, sin convertirla.

    Downloads the best audio stream as-is; conversion and tagging belong to the
    audio integration.

    Args:
        video_id: Identificador de YouTube. / YouTube id.
        dest_dir: Carpeta de destino. / Destination folder.
        on_progress: Se llama con cada avance. / Called on every progress update.
        proxy: URL del proxy a usar. / Proxy URL to use.
        ydl_factory: Fábrica de ``YoutubeDL``. / ``YoutubeDL`` factory.

    Returns:
        Ruta del fichero descargado. / Path of the downloaded file.

    Raises:
        ValueError: Si el identificador no es válido. / If the id is invalid.
        YoutubeError: Si yt-dlp falla. / If yt-dlp fails.
    """
    preview_embed_url(video_id)  # valida el identificador / validates the id

    def hook(data: dict[str, Any]) -> None:
        """Traduce el diccionario de yt-dlp. / Translates yt-dlp's progress dict."""
        if on_progress is None or data["status"] not in ("downloading", "finished"):
            return
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        on_progress(
            DownloadProgress(
                downloaded_bytes=data["downloaded_bytes"],
                total_bytes=total,
                finished=data["status"] == "finished",
            )
        )

    options: dict[str, Any] = {
        "quiet": True,
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "progress_hooks": [hook],
        "proxy": proxy,
    }
    try:
        with ydl_factory(options) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            return Path(ydl.prepare_filename(info))
    except DownloadError as exc:
        raise YoutubeError(str(exc)) from exc
