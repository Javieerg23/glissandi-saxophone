"""Servicios de novedades. / New-release services."""

import logging
from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Protocol

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from activity.services import log_activity
from catalog.models import (
    Album,
    AlbumArtist,
    Artist,
    BlockedItem,
    Track,
    TrackArtist,
)
from integrations.deezer.client import DeezerClient
from integrations.deezer.models import Album as DeezerAlbum
from integrations.deezer.models import ArtistRef, Page
from integrations.deezer.models import Track as RemoteTrack
from jobs import runner
from jobs.registry import UnknownJobKind
from watches.models import Watch, WatchRun

logger = logging.getLogger(__name__)


class DeezerSource(Protocol):
    """Lo que la comprobación necesita de Deezer; ``DeezerClient`` lo cumple.

    What the check needs from Deezer; ``DeezerClient`` satisfies it.
    """

    def artist_albums(self, artist_id: int, index: int = 0) -> Page[DeezerAlbum]:
        """Página de álbumes de un artista. / A page of an artist's albums."""

    def album_tracks(self, album: DeezerAlbum, index: int = 0) -> Page[RemoteTrack]:
        """Página de canciones de un álbum. / A page of an album's tracks."""


DOWNLOAD_KIND = "download"


def _pages[T](fetch: Callable[[int], Page[T]]) -> Iterator[T]:
    """Recorre todas las páginas de un listado de Deezer.

    Walks every page of a Deezer listing.
    """
    index: int | None = 0
    while index is not None:
        page = fetch(index)
        yield from page.items
        index = page.next_index


def _artist_for(ref: ArtistRef) -> Artist | None:
    """Artista del catálogo para una referencia de Deezer; sin id no hay forma de enlazarlo.

    Catalogue artist for a Deezer reference; without an id it cannot be linked.
    """
    if ref.id is None:
        return None
    return Artist.objects.get_or_create(deezer_id=ref.id, defaults={"name": ref.name})[0]


def _credits(refs: tuple[ArtistRef, ...]) -> list[Artist]:
    """Artistas enlazables de una lista de créditos, en orden. / Linkable artists, in order."""
    return [artist for ref in refs if (artist := _artist_for(ref)) is not None]


def _import_album(client: DeezerSource, remote: DeezerAlbum) -> list[Track]:
    """Importa un álbum nuevo con sus canciones y créditos.

    Imports a new album with its tracks and credits.

    shortcut: minimal import (no MusicBrainz verification, no ISRC) until the catalog import
    service replaces it; it only creates, never updates, so a re-run changes nothing.
    """
    with transaction.atomic():
        album = Album.objects.create(
            deezer_id=remote.id,
            title=remote.title,
            release_date=remote.release_date,
            cover_url=remote.cover_url or "",
        )
        for position, artist in enumerate(_credits(remote.artists)):
            AlbumArtist.objects.create(album=album, artist=artist, position=position)
        created: list[Track] = []
        blocked = set(
            BlockedItem.objects.filter(kind=BlockedItem.Kind.TRACK).values_list(
                "deezer_id", flat=True
            )
        )
        for remote_track in _pages(lambda i: client.album_tracks(remote, index=i)):
            if (
                remote_track.id in blocked
                or Track.objects.filter(deezer_id=remote_track.id).exists()
            ):
                continue
            track = Track.objects.create(
                album=album,
                deezer_id=remote_track.id,
                title=remote_track.title,
                track_number=remote_track.track_position or 1,
                disc_number=remote_track.disk_number or 1,
                duration=remote_track.duration,
            )
            for position, artist in enumerate(_credits(remote_track.artists)):
                TrackArtist.objects.create(track=track, artist=artist, position=position)
            created.append(track)
    return created


def new_albums(client: DeezerSource, artist: Artist) -> Iterator[DeezerAlbum]:
    """Álbumes de Deezer del artista que aún no están en el catálogo ni bloqueados.

    The artist's Deezer albums that are neither in the catalogue nor blocked.
    """
    if artist.deezer_id is None:
        return
    known = set(Album.objects.filter(deezer_id__isnull=False).values_list("deezer_id", flat=True))
    known |= set(
        BlockedItem.objects.filter(kind=BlockedItem.Kind.ALBUM).values_list("deezer_id", flat=True)
    )
    for remote in _pages(lambda i: client.artist_albums(artist.deezer_id, index=i)):  # type: ignore[arg-type]
        if remote.id not in known:
            yield remote


def _start_download(tracks: list[Track], user: User | None) -> str:
    """Lanza la descarga de lo nuevo; devuelve una nota para el detalle del resultado.

    Starts the download of the new tracks; returns a note for the run's detail. The check
    itself succeeded, so a download that cannot start is reported, not raised.
    """
    try:
        runner.start(DOWNLOAD_KIND, {"track_ids": [t.pk for t in tracks]}, user)
    except (UnknownJobKind, runner.JobAlreadyRunning) as error:
        return f"Descarga no iniciada / Download not started: {type(error).__name__}"
    return ""


def check_watch(
    watch: Watch, user: User | None = None, client: DeezerSource | None = None
) -> WatchRun:
    """Comprueba las novedades de una vigilancia y deja constancia en un ``WatchRun``.

    Checks a watch for new releases and records the outcome in a ``WatchRun``. The run is
    written also when the check fails, and the next check is always rescheduled so a broken
    watch is retried at its own pace instead of on every pass.

    Returns:
        La ejecución creada. / The created run.
    """
    client = client or DeezerClient()
    started = timezone.now()
    albums = 0
    tracks: list[Track] = []
    detail = ""
    status = WatchRun.Status.SUCCEEDED
    try:
        for artist in watch.artists.order_by("watch_entries__position"):
            for remote in new_albums(client, artist):
                tracks += _import_album(client, remote)
                albums += 1
        if watch.auto_download and tracks:
            detail = _start_download(tracks, user)
    except Exception as error:
        logger.exception("Falló la comprobación de la vigilancia %s", watch.pk)
        status, detail = WatchRun.Status.FAILED, str(error) or type(error).__name__
    run = WatchRun.objects.create(
        watch=watch,
        started_at=started,
        finished_at=timezone.now(),
        status=status,
        found=albums,
        detail=detail,
    )
    # ``update`` y no ``save``: no pisa lo que el usuario edite mientras se comprueba.
    # ``update`` rather than ``save``: does not overwrite edits made during the check.
    Watch.objects.filter(pk=watch.pk).update(
        next_run_at=timezone.now() + timedelta(hours=watch.interval_hours)
    )
    log_activity(user, "watches.watch.checked", watch, {"status": status, "albums": albums})
    return run


def due_watches() -> list[Watch]:
    """Vigilancias activas cuya próxima ejecución ya ha pasado.

    Enabled watches whose next run has passed.
    """
    return list(Watch.objects.filter(enabled=True, next_run_at__lte=timezone.now()))


def launch_due() -> None:
    """Lanza ``watch_check`` si hay vigilancias pendientes; la llama el planificador.

    Starts ``watch_check`` when some watch is due; called by the scheduler. A check that is
    still running will pick the due ones up, so an active run is not an error.
    """
    if not Watch.objects.filter(enabled=True, next_run_at__lte=timezone.now()).exists():
        return
    try:
        runner.start("watch_check", {}, None)
    except runner.JobAlreadyRunning:
        pass
