"""Importación de artistas de Deezer al catálogo.

Import of Deezer artists into the catalogue.

Idempotent by design: every row is looked up by its Deezer id before being
created and existing rows are never overwritten, so manual edits survive and a
second run changes nothing. Each album is saved in one transaction, which keeps a
stopped or failed run from leaving half an album behind.
"""

from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

import requests
from django.db import transaction
from django.utils.translation import gettext as _

from catalog.models import Album, AlbumArtist, Artist, BlockedItem, Track, TrackArtist
from integrations import deezer as dz
from integrations.deezer import DeezerClient, DeezerError
from integrations.musicbrainz.client import MusicBrainzClient
from jobs import runner
from jobs.models import JobRun, JobRunLine

# Puntuación mínima de MusicBrainz para dar por buena una coincidencia por nombre.
# Minimum MusicBrainz score to accept a match by name.
MIN_ARTIST_SCORE = 95


def _pages[T](fetch: Callable[[int], dz.Page[T]]) -> Iterator[T]:
    """Recorre todas las páginas de un listado de Deezer.

    Walks every page of a Deezer listing.
    """
    index: int | None = 0
    while index is not None:
        page = fetch(index)
        yield from page.items
        index = page.next_index


def _is_blocked(kind: str, deezer_id: int | None) -> bool:
    """Si el elemento de Deezer está bloqueado. / Whether the Deezer item is blocked."""
    return (
        deezer_id is not None
        and BlockedItem.objects.filter(kind=kind, deezer_id=deezer_id).exists()
    )


class Importer:
    """Importa artistas con sus álbumes y canciones dentro de una ejecución.

    Imports artists with their albums and tracks inside a job run.

    Args:
        run: Ejecución que recibe el progreso y las líneas de log.
            Run receiving progress and log lines.
        deezer: Cliente de Deezer. / Deezer client.
        musicbrainz: Cliente de MusicBrainz; si se da, verifica artistas y canciones.
            MusicBrainz client; when given, artists and tracks are verified.
    """

    def __init__(
        self,
        run: JobRun,
        deezer: DeezerClient,
        musicbrainz: MusicBrainzClient | None = None,
    ) -> None:
        """Prepara el importador. / Sets the importer up."""
        self.run = run
        self._deezer = deezer
        self._mb = musicbrainz
        self._done = 0
        self._total = 0
        self.counts: Counter[str] = Counter()

    def import_artists(self, deezer_ids: list[int]) -> bool:
        """Importa varios artistas; un fallo en uno no detiene el resto.

        Imports several artists; one failing does not stop the others.

        Returns:
            ``False`` si se pidió parar antes de acabar. / ``False`` if a stop cut it short.
        """
        for deezer_id in deezer_ids:
            if runner.should_stop(self.run):
                return False
            try:
                if not self.import_artist(deezer_id):
                    return False
            except (DeezerError, requests.RequestException) as error:
                self.counts["failed_artists"] += 1
                self._log(
                    JobRunLine.Level.ERROR,
                    _("Artista %(id)s: %(error)s"),
                    id=deezer_id,
                    error=error,
                )
        return True

    def import_artist(self, deezer_id: int) -> bool:
        """Importa un artista y todos sus álbumes.

        Imports one artist and all its albums.

        Returns:
            ``False`` si se pidió parar entre álbumes. / ``False`` if stopped between albums.
        """
        if _is_blocked(BlockedItem.Kind.ARTIST, deezer_id):
            self.counts["blocked"] += 1
            self._log(JobRunLine.Level.INFO, _("Artista %(id)s bloqueado: se omite."), id=deezer_id)
            return True
        remote = self._deezer.get_artist(deezer_id)
        artist, created = Artist.objects.get_or_create(
            deezer_id=remote.id,
            defaults={"name": remote.name, "image_url": remote.image_url or ""},
        )
        if created:
            self.counts["artists"] += 1
        self._log(JobRunLine.Level.INFO, _("Artista «%(name)s»."), name=artist.name)
        self._verify_artist(artist)

        albums = list(_pages(lambda i: self._deezer.artist_albums(remote.id, index=i)))
        self._total += len(albums)
        for album in albums:
            if runner.should_stop(self.run):
                return False
            self.import_album(album)
        return True

    def import_album(self, remote: dz.Album) -> None:
        """Importa un álbum con sus canciones si aún no está en el catálogo.

        Imports an album with its tracks if it is not in the catalogue yet.
        """
        self._done += 1
        runner.progress(self.run, self._done, self._total, remote.title)
        if _is_blocked(BlockedItem.Kind.ALBUM, remote.id):
            self.counts["blocked"] += 1
            self._log(
                JobRunLine.Level.INFO,
                _("Álbum «%(title)s» bloqueado: se omite."),
                title=remote.title,
            )
            return
        if Album.objects.filter(deezer_id=remote.id).exists():
            self.counts["skipped_albums"] += 1
            return
        # Las llamadas a Deezer van antes de la transacción: no se retiene la base de datos.
        # Deezer calls happen before the transaction so the database is not held open.
        tracks = [
            self._deezer.get_track(t.id)
            for t in _pages(lambda i: self._deezer.album_tracks(remote, index=i))
            if not _is_blocked(BlockedItem.Kind.TRACK, t.id)
            and not Track.objects.filter(deezer_id=t.id).exists()
        ]
        with transaction.atomic():
            album = Album.objects.create(
                deezer_id=remote.id,
                title=remote.title,
                release_date=remote.release_date,
                cover_url=remote.cover_url or "",
            )
            self._credit(AlbumArtist, "album", album, remote.artists)
            created = [t for t in (self._create_track(album, track) for track in tracks) if t]
        self.counts["albums"] += 1
        self._log(
            JobRunLine.Level.INFO,
            _("Álbum «%(title)s»: %(count)d canciones."),
            title=album.title,
            count=len(created),
        )
        for track in created:
            self._verify_track(track)

    def _create_track(self, album: Album, remote: dz.Track) -> Track | None:
        """Crea una canción; ``None`` si su ISRC ya está en el catálogo.

        Creates a track; ``None`` if its ISRC is already in the catalogue. The ISRC
        is unique across editions, so the second copy of a song is not added.
        """
        if remote.isrc and Track.objects.filter(isrc=remote.isrc).exists():
            self.counts["duplicate_tracks"] += 1
            return None
        track = Track.objects.create(
            album=album,
            deezer_id=remote.id,
            title=remote.title,
            isrc=remote.isrc,
            duration=remote.duration,
            track_number=remote.track_position or 1,
            disc_number=remote.disk_number or 1,
        )
        self._credit(TrackArtist, "track", track, remote.artists)
        self.counts["tracks"] += 1
        return track

    def _credit(
        self,
        model: type[AlbumArtist] | type[TrackArtist],
        field: str,
        owner: Any,
        refs: tuple[dz.ArtistRef, ...],
    ) -> None:
        """Crea los créditos en orden, saltando artistas bloqueados.

        Creates credits in order, skipping blocked artists.
        """
        position = 0
        for ref in refs:
            artist = self._artist_for(ref)
            if artist is not None:
                model.objects.get_or_create(
                    **{field: owner, "artist": artist}, defaults={"position": position}
                )
                position += 1

    def _artist_for(self, ref: dz.ArtistRef) -> Artist | None:
        """Busca o crea el artista citado; ``None`` si está bloqueado.

        Finds or creates the mentioned artist; ``None`` if blocked. A guest named
        only in a title has no Deezer id, so it is matched by name.
        """
        if ref.id is None:
            existing = Artist.objects.filter(name__iexact=ref.name).first()
            return existing or Artist.objects.create(name=ref.name)
        if _is_blocked(BlockedItem.Kind.ARTIST, ref.id):
            return None
        return Artist.objects.get_or_create(deezer_id=ref.id, defaults={"name": ref.name})[0]

    def _verify_artist(self, artist: Artist) -> None:
        """Asigna el id y la imagen de MusicBrainz si la coincidencia es clara.

        Sets the MusicBrainz id and image when the match is clear.
        """
        if self._mb is None or artist.musicbrainz_id:
            return
        try:
            matches = self._mb.search_artists(artist.name)
            best = matches[0] if matches else None
            if (
                best is None
                or best.score < MIN_ARTIST_SCORE
                or best.name.casefold() != artist.name.casefold()
            ):
                return
            if Artist.objects.filter(musicbrainz_id=best.mbid).exists():
                return
            artist.musicbrainz_id = best.mbid
            if not artist.image_url:
                artist.image_url = self._mb.find_artist_image_url(best.mbid) or ""
            artist.save()
            self.counts["verified"] += 1
        except requests.RequestException as error:
            self._log(JobRunLine.Level.WARNING, _("MusicBrainz: %(error)s"), error=error)

    def _verify_track(self, track: Track) -> None:
        """Asigna el id de MusicBrainz de la grabación que tiene ese ISRC.

        Sets the MusicBrainz id of the recording carrying that ISRC.
        """
        if self._mb is None or not track.isrc:
            return
        try:
            recordings = self._mb.search_recordings_by_isrc(track.isrc)
        except requests.RequestException as error:
            self._log(JobRunLine.Level.WARNING, _("MusicBrainz: %(error)s"), error=error)
            return
        if recordings and not Track.objects.filter(musicbrainz_id=recordings[0].mbid).exists():
            track.musicbrainz_id = recordings[0].mbid
            track.save()
            self.counts["verified"] += 1

    def _log(self, level: str, message: str, **values: Any) -> None:
        """Añade una línea al registro de la ejecución. / Appends a line to the run's log."""
        runner.line(self.run, level, message % values)
