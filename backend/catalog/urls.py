"""Rutas de la app ``catalog``. / ``catalog`` app URLs."""

from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from .views import (
    AlbumViewSet,
    ArtistViewSet,
    BlockedItemViewSet,
    DeezerArtistSearchView,
    LibrarySummaryView,
    TrackViewSet,
)

router = SimpleRouter()
router.register("artists", ArtistViewSet, basename="artist")
router.register("albums", AlbumViewSet, basename="album")
router.register("tracks", TrackViewSet, basename="track")
router.register("blocked", BlockedItemViewSet, basename="blocked")

urlpatterns: list[URLPattern | URLResolver] = [
    path("summary/", LibrarySummaryView.as_view(), name="library-summary"),
    path("deezer/artists/", DeezerArtistSearchView.as_view(), name="deezer-artist-search"),
    *router.urls,
]
