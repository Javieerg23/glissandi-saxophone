"""Cliente de la API pública de Deezer.

Client for Deezer's public API.
"""

from datetime import date
from typing import Any

import requests

from integrations.deezer.models import Album, AlbumRef, Artist, ArtistRef, Page, Track
from integrations.deezer.names import artist_refs, merge_artists, split_featured
from integrations.http import build_session

BASE_URL = "https://api.deezer.com"
# Máximo que admite Deezer por página. / Largest page size Deezer accepts.
MAX_PAGE_SIZE = 100


class DeezerError(Exception):
    """Deezer respondió con un error. / Deezer answered with an error."""


def _date(value: str | None) -> date | None:
    """Fecha ISO, o ``None`` si falta o es la fecha nula de Deezer.

    ISO date, or ``None`` when missing or Deezer's null date.
    """
    if not value or value.startswith("0000"):
        return None
    return date.fromisoformat(value)


def _album_ref(raw: dict[str, Any] | None) -> AlbumRef | None:
    if not raw:
        return None
    return AlbumRef(raw["id"], raw["title"], raw.get("cover_xl"))


def parse_artist(raw: dict[str, Any]) -> Artist:
    """Convierte un artista de Deezer. / Converts a Deezer artist."""
    return Artist(
        id=raw["id"],
        name=raw["name"],
        image_url=raw.get("picture_xl"),
        album_count=raw.get("nb_album"),
        fan_count=raw.get("nb_fan"),
    )


def parse_album(raw: dict[str, Any]) -> Album:
    """Convierte un álbum de Deezer. / Converts a Deezer album."""
    return Album(
        id=raw["id"],
        title=raw["title"],
        artists=artist_refs(raw.get("artist"), raw.get("contributors", ())),
        release_date=_date(raw.get("release_date")),
        record_type=raw.get("record_type"),
        cover_url=raw.get("cover_xl"),
        track_count=raw.get("nb_tracks"),
        upc=raw.get("upc") or None,
        explicit=bool(raw.get("explicit_lyrics")),
    )


def parse_track(raw: dict[str, Any], album: AlbumRef | None = None) -> Track:
    """Convierte una canción de Deezer.

    Converts a Deezer track. Guests named only in the title are added after the
    credited artists; the title is returned without its "feat." part.

    Args:
        raw: Objeto ``track`` de Deezer. / Deezer ``track`` object.
        album: Álbum al que pertenece cuando ``raw`` no lo trae (listados de un álbum).
            Album it belongs to when ``raw`` lacks one (album listings).
    """
    title, guests = split_featured(raw["title"])
    credited = artist_refs(raw.get("artist"), raw.get("contributors", ()))
    return Track(
        id=raw["id"],
        title=title,
        artists=merge_artists(credited, (ArtistRef(g) for g in guests)),
        album=_album_ref(raw.get("album")) or album,
        isrc=raw.get("isrc") or None,
        duration=raw.get("duration"),
        track_position=raw.get("track_position"),
        disk_number=raw.get("disk_number"),
        explicit=bool(raw.get("explicit_lyrics")),
    )


class DeezerClient:
    """Consultas de solo lectura a Deezer, sin autenticación.

    Read-only, unauthenticated Deezer queries.

    Args:
        session: Sesión HTTP; por defecto la común de ``integrations.http``.
            HTTP session; defaults to the shared one from ``integrations.http``.
        base_url: Raíz de la API. / API root.
    """

    def __init__(self, session: requests.Session | None = None, base_url: str = BASE_URL) -> None:
        """Prepara el cliente. / Sets the client up."""
        self._session = session or build_session()
        self._base_url = base_url

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self._session.get(f"{self._base_url}/{path}", params=params)
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        # Deezer devuelve los fallos de negocio con HTTP 200 y un objeto "error".
        # Deezer reports application failures with HTTP 200 and an "error" object.
        if "error" in body:
            error = body["error"]
            raise DeezerError(f"{error.get('type', 'Error')}: {error.get('message', '')}")
        return body

    def _page(
        self, path: str, index: int, limit: int, **params: Any
    ) -> tuple[list[Any], Page[Any]]:
        """Pide una página y devuelve sus datos crudos y la paginación.

        Fetches a page, returning its raw data and the pagination envelope.
        """
        body = self._get(path, index=index, limit=min(limit, MAX_PAGE_SIZE), **params)
        data = body.get("data", [])
        next_index = index + len(data) if "next" in body else None
        return data, Page(total=body.get("total", len(data)), next_index=next_index)

    def search_artists(self, query: str, index: int = 0, limit: int = 25) -> Page[Artist]:
        """Busca artistas por nombre. / Searches artists by name."""
        data, page = self._page("search/artist", index, limit, q=query)
        return Page(tuple(parse_artist(a) for a in data), page.total, page.next_index)

    def get_artist(self, artist_id: int) -> Artist:
        """Detalle de un artista. / Artist detail."""
        return parse_artist(self._get(f"artist/{artist_id}"))

    def artist_albums(self, artist_id: int, index: int = 0, limit: int = 25) -> Page[Album]:
        """Álbumes de un artista. / An artist's albums."""
        data, page = self._page(f"artist/{artist_id}/albums", index, limit)
        return Page(tuple(parse_album(a) for a in data), page.total, page.next_index)

    def get_album(self, album_id: int) -> Album:
        """Detalle de un álbum. / Album detail."""
        return parse_album(self._get(f"album/{album_id}"))

    def album_tracks(self, album: Album, index: int = 0, limit: int = 25) -> Page[Track]:
        """Canciones de un álbum. / An album's tracks.

        Deezer's album listing omits the album and ISRC; ``album`` fills the former
        and :meth:`get_track` gives the latter.
        """
        ref = AlbumRef(album.id, album.title, album.cover_url)
        data, page = self._page(f"album/{album.id}/tracks", index, limit)
        return Page(tuple(parse_track(t, ref) for t in data), page.total, page.next_index)

    def get_track(self, track_id: int) -> Track:
        """Detalle de una canción, con ISRC y colaboradores.

        Track detail, with ISRC and contributors.
        """
        return parse_track(self._get(f"track/{track_id}"))

    def get_track_by_isrc(self, isrc: str) -> Track:
        """Canción con ese ISRC. / Track carrying that ISRC.

        Raises:
            DeezerError: Si Deezer no conoce el ISRC. / If Deezer does not know the ISRC.
        """
        return parse_track(self._get(f"track/isrc:{isrc}"))

    def search_tracks(self, query: str, index: int = 0, limit: int = 25) -> Page[Track]:
        """Busca canciones; admite la sintaxis avanzada (``artist:"…" track:"…"``).

        Searches tracks; accepts the advanced syntax (``artist:"…" track:"…"``).
        Results lack the ISRC, which :meth:`get_track` gives.
        """
        data, page = self._page("search/track", index, limit, q=query)
        return Page(tuple(parse_track(t) for t in data), page.total, page.next_index)
