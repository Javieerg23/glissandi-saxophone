"""Administración del catálogo. / Catalogue admin."""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from simple_history.admin import SimpleHistoryAdmin

from .models import Album, AlbumArtist, Artist, BlockedItem, Download, Track, TrackArtist


class AlbumArtistInline(admin.TabularInline):  # type: ignore[type-arg]
    """Artistas de un álbum. / Artists of an album."""

    model = AlbumArtist
    extra = 0


class TrackArtistInline(admin.TabularInline):  # type: ignore[type-arg]
    """Artistas de una canción. / Artists of a track."""

    model = TrackArtist
    extra = 0


@admin.register(Artist)
class ArtistAdmin(SimpleHistoryAdmin):
    """Artistas con historial. / Artists with history."""

    search_fields = ["name"]


@admin.register(Album)
class AlbumAdmin(SimpleHistoryAdmin):
    """Álbumes con historial. / Albums with history."""

    search_fields = ["title"]
    inlines = [AlbumArtistInline]


@admin.register(Track)
class TrackAdmin(SimpleHistoryAdmin):
    """Canciones con historial. / Tracks with history."""

    search_fields = ["title", "isrc"]
    inlines = [TrackArtistInline]


@admin.register(BlockedItem)
class BlockedItemAdmin(SimpleHistoryAdmin):
    """Elementos bloqueados. / Blocked items."""

    list_display = ["kind", "deezer_id", "name"]


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Descargas, solo lectura. / Downloads, read only."""

    list_display = ["file_path", "track", "created_at"]

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Se crean desde las tareas. / Created by tasks."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Solo lectura. / Read only."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """No se borran. / Never deleted."""
        return False
