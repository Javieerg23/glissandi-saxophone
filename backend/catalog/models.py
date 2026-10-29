"""Modelos del catálogo musical. / Music catalogue models.

El esquema no duplica datos: el nombre de un álbum o de un artista vive solo en su
fila, y ``Track`` llega a ellos por relaciones. Que una canción esté descargada se
deduce de ``Download``, no se guarda como casilla.

The schema holds no duplicated data: an album or artist name lives only in its own
row and ``Track`` reaches it through relations. Whether a track is downloaded is
derived from ``Download``, never stored as a flag.
"""

from typing import Any, ClassVar

from django.db import models
from django.db.models import Exists, OuterRef
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from core.models import AppendOnlyModel


class ImmutableFieldError(Exception):
    """Se intentó cambiar un identificador externo ya asignado.

    An already assigned external identifier was changed.
    """


class ExternalIdModel(models.Model):
    """Base abstracta con identificadores externos únicos e inmutables.

    Abstract base for models carrying unique, immutable external identifiers.

    Un identificador puede asignarse una sola vez: pasar de ``None`` a un valor es
    legal (p. ej. cuando MusicBrainz verifica más tarde un elemento de Deezer),
    pero cambiar uno ya asignado, o borrarlo, no. Se comprueba en ``save()`` y no
    con triggers para comportarse igual en SQLite y PostgreSQL.

    An identifier can be assigned only once: going from ``None`` to a value is
    allowed (e.g. MusicBrainz verifies a Deezer item later), but changing or
    clearing an assigned one is not. It is checked in ``save()`` rather than with
    triggers so it behaves the same on SQLite and PostgreSQL.
    """

    immutable_fields: ClassVar[tuple[str, ...]] = ("deezer_id", "musicbrainz_id")

    deezer_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)
    musicbrainz_id = models.UUIDField(null=True, blank=True, unique=True)

    class Meta:
        """Sin tabla propia. / No table of its own."""

        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Guarda rechazando el cambio de identificadores ya asignados.

        Saves, rejecting changes to identifiers that were already assigned.

        Raises:
            ImmutableFieldError: Si un identificador asignado cambia o se borra.
        """
        if not self._state.adding:
            stored = (
                type(self)
                ._default_manager.filter(pk=self.pk)
                .values_list(*self.immutable_fields)
                .first()
            )
            for name, old in zip(self.immutable_fields, stored or (), strict=True):
                if old is not None and old != getattr(self, name):
                    raise ImmutableFieldError(
                        _("El campo %(field)s no se puede modificar.") % {"field": name}
                    )
        super().save(*args, **kwargs)


class Artist(ExternalIdModel):
    """Artista. / Artist."""

    name = models.CharField(max_length=255, db_index=True)
    image_url = models.URLField(max_length=500, blank=True)
    history = HistoricalRecords()

    def __str__(self) -> str:
        """Nombre del artista. / Artist name."""
        return self.name


class Album(ExternalIdModel):
    """Álbum; sus artistas van en ``AlbumArtist``. / Album; its artists go in ``AlbumArtist``."""

    title = models.CharField(max_length=255, db_index=True)
    release_date = models.DateField(null=True, blank=True)
    cover_url = models.URLField(max_length=500, blank=True)
    artists = models.ManyToManyField(Artist, through="AlbumArtist", related_name="albums")
    history = HistoricalRecords()

    def __str__(self) -> str:
        """Título del álbum. / Album title."""
        return self.title


class AlbumArtist(models.Model):
    """Artista de un álbum con su posición en los créditos.

    Artist of an album with its position in the credits.
    """

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="credits")
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="album_credits")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        """Un artista figura una vez por álbum. / An artist appears once per album."""

        ordering = ["album", "position"]
        constraints = [
            models.UniqueConstraint(fields=["album", "artist"], name="unique_album_artist")
        ]

    def __str__(self) -> str:
        """Álbum y artista. / Album and artist."""
        return f"{self.album} / {self.artist}"


class TrackQuerySet(models.QuerySet["Track"]):
    """Consultas de canciones. / Track queries."""

    def with_downloaded(self) -> "TrackQuerySet":
        """Anota ``downloaded`` (bool) a partir de ``Download``.

        Annotates ``downloaded`` (bool) from ``Download``.
        """
        return self.annotate(downloaded=Exists(Download.objects.filter(track=OuterRef("pk"))))


class Track(ExternalIdModel):
    """Canción de un álbum; el ISRC la identifica entre ediciones.

    Track of an album; the ISRC identifies it across editions.
    """

    immutable_fields = ("deezer_id", "musicbrainz_id", "isrc")

    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name="tracks")
    title = models.CharField(max_length=255, db_index=True)
    track_number = models.PositiveSmallIntegerField(default=1)
    disc_number = models.PositiveSmallIntegerField(default=1)
    duration = models.PositiveIntegerField(null=True, blank=True, help_text=_("Segundos."))
    isrc = models.CharField(max_length=12, null=True, blank=True, unique=True)
    artists = models.ManyToManyField(Artist, through="TrackArtist", related_name="tracks")
    history = HistoricalRecords()

    objects = TrackQuerySet.as_manager()

    class Meta:
        """Orden del disco. / Disc order."""

        ordering = ["album", "disc_number", "track_number"]

    def __str__(self) -> str:
        """Título de la canción. / Track title."""
        return self.title

    @property
    def is_downloaded(self) -> bool:
        """Si existe alguna descarga de la canción. / Whether any download exists."""
        return Download.objects.filter(track=self).exists()


class TrackArtist(models.Model):
    """Artista de una canción con su posición (principal, colaboradores).

    Artist of a track with its position (main artist, featured artists).
    """

    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="credits")
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="track_credits")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        """Un artista figura una vez por canción. / An artist appears once per track."""

        ordering = ["track", "position"]
        constraints = [
            models.UniqueConstraint(fields=["track", "artist"], name="unique_track_artist")
        ]

    def __str__(self) -> str:
        """Canción y artista. / Track and artist."""
        return f"{self.track} / {self.artist}"


class BlockedItem(models.Model):
    """Elemento de Deezer que no debe importarse.

    Deezer item that must not be imported. It refers to the external id, not to a
    catalogue row, so an item can be blocked before it was ever imported.
    """

    class Kind(models.TextChoices):
        """Tipo de elemento bloqueado. / Kind of blocked item."""

        ARTIST = "artist", _("Artista")
        ALBUM = "album", _("Álbum")
        TRACK = "track", _("Canción")

    kind = models.CharField(max_length=10, choices=Kind.choices)
    deezer_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        """Un bloqueo por elemento. / One block per item."""

        constraints = [
            models.UniqueConstraint(fields=["kind", "deezer_id"], name="unique_blocked_item")
        ]

    def __str__(self) -> str:
        """Tipo e identificador. / Kind and identifier."""
        return f"{self.kind}:{self.deezer_id}"


class Download(AppendOnlyModel):
    """Descarga realizada de una canción; registro de solo añadir.

    Completed download of a track; an append-only record. ``PROTECT`` keeps a
    downloaded track from being deleted and orphaning its history.
    """

    track = models.ForeignKey(Track, on_delete=models.PROTECT)
    file_path = models.CharField(max_length=1000)
    audio_format = models.CharField(max_length=10)
    source_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        """Ruta del fichero. / File path."""
        return self.file_path
