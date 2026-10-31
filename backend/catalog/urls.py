"""Rutas de la app ``catalog``. / ``catalog`` app URLs."""

from django.urls import URLPattern, URLResolver, path
from rest_framework.routers import SimpleRouter

from .backup import LibraryBackupPreviewView, LibraryExportView, LibraryRestoreView
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
    path("backup/", LibraryExportView.as_view(), name="library-export"),
    path("backup/preview/", LibraryBackupPreviewView.as_view(), name="library-backup-preview"),
    path("backup/restore/", LibraryRestoreView.as_view(), name="library-restore"),
    *router.urls,
]
