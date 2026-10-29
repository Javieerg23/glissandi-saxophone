"""Tipos de salida de la integración con Deezer (sin modelos de Django).

Output types of the Deezer integration (no Django models).
"""

from dataclasses import dataclass, field
from datetime import date

# Deezer agrupa los discos recopilatorios bajo este artista.
# Deezer files compilation albums under this artist.
VARIOUS_ARTISTS_ID = 5080


@dataclass(frozen=True)
class ArtistRef:
    """Artista citado desde una canción o un álbum.

    Artist as mentioned by a track or album. ``id`` is ``None`` when the name only
    appeared in a title ("feat. X") and Deezer gave no identifier for it.
    """

    name: str
    id: int | None = None


@dataclass(frozen=True)
class Artist:
    """Artista de Deezer. / Deezer artist."""

    id: int
    name: str
    image_url: str | None = None
    album_count: int | None = None
    fan_count: int | None = None


@dataclass(frozen=True)
class Album:
    """Álbum de Deezer. / Deezer album."""

    id: int
    title: str
    artists: tuple[ArtistRef, ...]
    release_date: date | None = None
    record_type: str | None = None
    cover_url: str | None = None
    track_count: int | None = None
    upc: str | None = None
    explicit: bool = False

    @property
    def is_various_artists(self) -> bool:
        """Indica si es un recopilatorio. / Whether this is a compilation."""
        return any(a.id == VARIOUS_ARTISTS_ID for a in self.artists)


@dataclass(frozen=True)
class AlbumRef:
    """Álbum citado desde una canción. / Album as mentioned by a track."""

    id: int
    title: str
    cover_url: str | None = None


@dataclass(frozen=True)
class Track:
    """Canción de Deezer; ``artists`` va en orden, el principal primero.

    Deezer track; ``artists`` is ordered, main artist first.
    """

    id: int
    title: str
    artists: tuple[ArtistRef, ...]
    album: AlbumRef | None = None
    isrc: str | None = None
    duration: int | None = None
    track_position: int | None = None
    disk_number: int | None = None
    explicit: bool = False


@dataclass(frozen=True)
class Page[T]:
    """Página de resultados. / One page of results.

    Attributes:
        items: Elementos de la página. / Items on this page.
        total: Total de elementos que declara Deezer. / Total reported by Deezer.
        next_index: Índice para pedir la siguiente página, ``None`` si es la última.
            Index to request the next page, ``None`` on the last one.
    """

    items: tuple[T, ...] = field(default_factory=tuple)
    total: int = 0
    next_index: int | None = None
