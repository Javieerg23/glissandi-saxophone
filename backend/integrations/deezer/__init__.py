"""Integración con Deezer. / Deezer integration."""

from integrations.deezer.client import DeezerClient, DeezerError
from integrations.deezer.models import Album, AlbumRef, Artist, ArtistRef, Page, Track

__all__ = [
    "Album",
    "AlbumRef",
    "Artist",
    "ArtistRef",
    "DeezerClient",
    "DeezerError",
    "Page",
    "Track",
]
