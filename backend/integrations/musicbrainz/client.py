"""Cliente de MusicBrainz: búsqueda, verificación y resolución.

MusicBrainz client: search, verification and lookup.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

from integrations.http import build_session

API_URL = "https://musicbrainz.org/ws/2"
COVER_ART_URL = "https://coverartarchive.org"
# MusicBrainz pide un máximo de una petición por segundo para uso no comercial.
# MusicBrainz asks for at most one request per second for non-commercial use.
MIN_INTERVAL = 1.0


@dataclass(frozen=True, slots=True)
class Recording:
    """Grabación de MusicBrainz con sus ISRC. / MusicBrainz recording with its ISRCs.

    Attributes:
        mbid: Identificador MusicBrainz. / MusicBrainz identifier.
        title: Título de la grabación. / Recording title.
        artists: Nombres de los artistas acreditados. / Credited artist names.
        isrcs: ISRC asociados, en mayúsculas y sin guiones.
            Associated ISRCs, uppercase and without dashes.
        score: Puntuación de la búsqueda (0 en las búsquedas por identificador).
            Search score (0 for lookups by identifier).
    """

    mbid: str
    title: str
    artists: tuple[str, ...]
    isrcs: tuple[str, ...]
    score: int = 0


@dataclass(frozen=True, slots=True)
class Artist:
    """Artista de MusicBrainz. / MusicBrainz artist.

    Attributes:
        mbid: Identificador MusicBrainz. / MusicBrainz identifier.
        name: Nombre del artista. / Artist name.
        score: Puntuación de la búsqueda. / Search score.
    """

    mbid: str
    name: str
    score: int = 0


class RateLimiter:
    """Separa las llamadas al menos ``interval`` segundos.

    Keeps calls at least ``interval`` seconds apart. The clock and the sleep
    function are injected so tests can run without waiting.
    """

    def __init__(
        self,
        interval: float = MIN_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Guarda el intervalo y las funciones de reloj y espera.

        Stores the interval and the clock and sleep functions.

        Args:
            interval: Segundos mínimos entre llamadas. / Minimum seconds between calls.
            clock: Fuente de tiempo monótona. / Monotonic time source.
            sleep: Función que espera los segundos indicados.
                Function that waits the given number of seconds.
        """
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        """Espera lo necesario antes de la siguiente llamada. / Waits before the next call."""
        if self._last is not None:
            remaining = self._last + self._interval - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


class MusicBrainzClient:
    """Cliente de la API WS/2 de MusicBrainz. / Client for the MusicBrainz WS/2 API.

    Every request goes through a ``RateLimiter`` and a shared HTTP session with
    timeouts and retries for idempotent methods.
    """

    def __init__(
        self,
        session: requests.Session | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        """Crea el cliente. / Creates the client.

        Args:
            session: Sesión HTTP; por defecto la común del proyecto.
                HTTP session; defaults to the project's shared session.
            limiter: Limitador de ritmo; por defecto una petición por segundo.
                Rate limiter; defaults to one request per second.
        """
        self._session = build_session() if session is None else session
        self._limiter = RateLimiter() if limiter is None else limiter

    def search_recordings_by_isrc(self, isrc: str) -> list[Recording]:
        """Busca grabaciones por ISRC. / Searches recordings by ISRC.

        Args:
            isrc: ISRC con o sin guiones. / ISRC with or without dashes.

        Returns:
            Grabaciones que coinciden, por orden de puntuación.
            Matching recordings, ordered by score.
        """
        data = self._get("recording", {"query": f"isrc:{_quote(_normalize_isrc(isrc))}"})
        return [_recording(item) for item in data.get("recordings", [])]

    def search_recordings(self, title: str, artist: str) -> list[Recording]:
        """Busca grabaciones por título y artista. / Searches recordings by title and artist.

        Args:
            title: Título de la canción. / Song title.
            artist: Nombre del artista principal. / Main artist name.

        Returns:
            Grabaciones que coinciden, por orden de puntuación.
            Matching recordings, ordered by score.
        """
        query = f"recording:{_quote(title)} AND artist:{_quote(artist)}"
        data = self._get("recording", {"query": query})
        return [_recording(item) for item in data.get("recordings", [])]

    def search_artists(self, name: str) -> list[Artist]:
        """Busca artistas por nombre. / Searches artists by name.

        Args:
            name: Nombre del artista. / Artist name.

        Returns:
            Artistas que coinciden, por orden de puntuación.
            Matching artists, ordered by score.
        """
        data = self._get("artist", {"query": f"artist:{_quote(name)}"})
        return [
            Artist(mbid=str(item["id"]), name=str(item["name"]), score=int(item.get("score", 0)))
            for item in data.get("artists", [])
        ]

    def find_recording(self, mbid: str) -> Recording | None:
        """Resuelve una grabación por su identificador. / Resolves a recording by identifier.

        Args:
            mbid: Identificador MusicBrainz de la grabación. / Recording MusicBrainz identifier.

        Returns:
            La grabación, o ``None`` si MusicBrainz no la conoce.
            The recording, or ``None`` if MusicBrainz does not know it.
        """
        data = self._lookup(f"recording/{_check_mbid(mbid)}", {"inc": "artist-credits+isrcs"})
        return None if data is None else _recording(data)

    def verify_isrc(self, mbid: str, isrc: str) -> bool:
        """Comprueba que una grabación tiene ese ISRC. / Checks that a recording has that ISRC.

        Args:
            mbid: Identificador MusicBrainz de la grabación. / Recording MusicBrainz identifier.
            isrc: ISRC a comprobar, con o sin guiones. / ISRC to check, with or without dashes.

        Returns:
            ``True`` si MusicBrainz lista el ISRC para esa grabación.
            ``True`` if MusicBrainz lists the ISRC for that recording.
        """
        recording = self.find_recording(mbid)
        return recording is not None and _normalize_isrc(isrc) in recording.isrcs

    def find_artist_image_url(self, mbid: str) -> str | None:
        """Devuelve la imagen de un artista según sus relaciones de URL.

        Returns the artist image from its URL relationships.

        Args:
            mbid: Identificador MusicBrainz del artista. / Artist MusicBrainz identifier.

        Returns:
            URL de la imagen, o ``None`` si no hay ninguna.
            Image URL, or ``None`` when there is none.
        """
        data = self._lookup(f"artist/{_check_mbid(mbid)}", {"inc": "url-rels"})
        if data is None:
            return None
        for relation in data.get("relations", []):
            if relation.get("type") == "image":
                return str(relation["url"]["resource"])
        return None

    @staticmethod
    def cover_art_url(release_group_mbid: str) -> str:
        """Construye la URL de la portada de un grupo de lanzamientos.

        Builds the cover URL of a release group. The Cover Art Archive redirects
        it to the image, so no request is needed here.

        Args:
            release_group_mbid: Identificador del grupo de lanzamientos.
                Release group identifier.

        Returns:
            URL de la portada frontal. / Front cover URL.
        """
        return f"{COVER_ART_URL}/release-group/{_check_mbid(release_group_mbid)}/front"

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """Hace una petición respetando el ritmo y lanza error en fallos HTTP.

        Makes a rate-limited request and raises on HTTP errors.
        """
        self._limiter.wait()
        response = self._session.get(f"{API_URL}/{path}", params={**params, "fmt": "json"})
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return data

    def _lookup(self, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        """Como ``_get``, pero un 404 devuelve ``None``.

        Like ``_get``, but a 404 returns ``None``.

        Missing entities are a normal answer for lookups, not an error.
        """
        try:
            return self._get(path, params)
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                return None
            raise


def _recording(item: dict[str, Any]) -> Recording:
    """Convierte una grabación de la API en ``Recording``. / Converts an API recording."""
    return Recording(
        mbid=str(item["id"]),
        title=str(item["title"]),
        artists=tuple(str(credit["name"]) for credit in item.get("artist-credit", [])),
        isrcs=tuple(str(isrc) for isrc in item.get("isrcs", [])),
        score=int(item.get("score", 0)),
    )


def _normalize_isrc(isrc: str) -> str:
    """Quita guiones y pasa a mayúsculas el ISRC. / Strips dashes and uppercases the ISRC.

    Deezer and MusicBrainz do not always write the same ISRC format.
    """
    return isrc.replace("-", "").strip().upper()


def _quote(value: str) -> str:
    """Escapa un valor para la sintaxis Lucene de MusicBrainz. / Escapes a Lucene value.

    Escaping backslashes and quotes keeps user text from changing the query.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _check_mbid(mbid: str) -> str:
    """Valida un identificador MusicBrainz (UUID) antes de usarlo en una ruta.

    Validates a MusicBrainz identifier (a UUID) before it goes into a URL path.
    """
    return str(uuid.UUID(mbid))
