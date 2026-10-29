"""Factorías de factory_boy para tests. / factory_boy factories for tests."""

from factory.declarations import RelatedFactory, Sequence, SubFactory
from factory.django import DjangoModelFactory

from .models import Album, AlbumArtist, Artist, Download, Track, TrackArtist


class ArtistFactory(DjangoModelFactory[Artist]):
    """Artista con identificador de Deezer. / Artist with a Deezer id."""

    class Meta:
        """Modelo. / Model."""

        model = Artist

    name = Sequence(lambda n: f"Artist {n}")
    deezer_id = Sequence(lambda n: n + 1)


class AlbumFactory(DjangoModelFactory[Album]):
    """Álbum con un artista principal. / Album with one main artist."""

    class Meta:
        """Modelo. / Model."""

        model = Album
        skip_postgeneration_save = True

    title = Sequence(lambda n: f"Album {n}")
    deezer_id = Sequence(lambda n: n + 1)
    credit = RelatedFactory("catalog.factories.AlbumArtistFactory", factory_related_name="album")


class AlbumArtistFactory(DjangoModelFactory[AlbumArtist]):
    """Crédito de álbum. / Album credit."""

    class Meta:
        """Modelo. / Model."""

        model = AlbumArtist

    album = SubFactory(AlbumFactory, credit=None)
    artist = SubFactory(ArtistFactory)


class TrackFactory(DjangoModelFactory[Track]):
    """Canción con un artista principal. / Track with one main artist."""

    class Meta:
        """Modelo. / Model."""

        model = Track
        skip_postgeneration_save = True

    album = SubFactory(AlbumFactory)
    title = Sequence(lambda n: f"Track {n}")
    deezer_id = Sequence(lambda n: n + 1)
    isrc = Sequence(lambda n: f"ES{n:010d}")
    credit = RelatedFactory("catalog.factories.TrackArtistFactory", factory_related_name="track")


class TrackArtistFactory(DjangoModelFactory[TrackArtist]):
    """Crédito de canción. / Track credit."""

    class Meta:
        """Modelo. / Model."""

        model = TrackArtist

    track = SubFactory(TrackFactory, credit=None)
    artist = SubFactory(ArtistFactory)


class DownloadFactory(DjangoModelFactory[Download]):
    """Descarga de una canción. / Download of a track."""

    class Meta:
        """Modelo. / Model."""

        model = Download

    track = SubFactory(TrackFactory)
    file_path = Sequence(lambda n: f"/music/{n}.mp3")
    audio_format = "mp3"
