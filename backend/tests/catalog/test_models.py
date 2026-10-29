"""Tests de los modelos del catálogo. / Catalogue model tests."""

import uuid
from datetime import date
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from catalog.factories import (
    AlbumFactory,
    ArtistFactory,
    DownloadFactory,
    TrackArtistFactory,
    TrackFactory,
)
from catalog.models import (
    Album,
    AlbumArtist,
    Artist,
    BlockedItem,
    Download,
    ImmutableFieldError,
    Track,
)
from core.models import AppendOnlyError

pytestmark = pytest.mark.django_db


def test_str_representations() -> None:
    track = TrackFactory(title="Song")
    assert str(track) == "Song"
    assert str(track.album) == track.album.title
    assert str(track.artists.get()) in str(track.credits.get())
    assert str(track.album.credits.get()).startswith(track.album.title)
    assert str(BlockedItem(kind="artist", deezer_id=7)) == "artist:7"
    assert str(DownloadFactory(file_path="/m/a.mp3")) == "/m/a.mp3"


# --- Inmutabilidad / Immutability ---


@pytest.mark.parametrize(
    ("factory", "field", "value"),
    [
        (ArtistFactory, "deezer_id", 999_999),
        (ArtistFactory, "musicbrainz_id", uuid.uuid4()),
        (AlbumFactory, "deezer_id", 999_999),
        (AlbumFactory, "musicbrainz_id", uuid.uuid4()),
        (TrackFactory, "deezer_id", 999_999),
        (TrackFactory, "musicbrainz_id", uuid.uuid4()),
        (TrackFactory, "isrc", "ZZ0000000000"),
    ],
)
def test_assigned_external_id_cannot_change(factory: Any, field: str, value: Any) -> None:
    obj = factory()
    # Los UUID no los genera la factoría: se asigna uno antes de intentar cambiarlo.
    # The factory sets no UUID: assign one before trying to change it.
    if field == "musicbrainz_id":
        obj.musicbrainz_id = uuid.uuid4()
        obj.save()
    setattr(obj, field, value)
    with pytest.raises(ImmutableFieldError):
        obj.save()


@pytest.mark.parametrize("field", ["deezer_id", "musicbrainz_id"])
def test_assigned_external_id_cannot_be_cleared(field: str) -> None:
    artist = ArtistFactory(musicbrainz_id=uuid.uuid4())
    setattr(artist, field, None)
    with pytest.raises(ImmutableFieldError):
        artist.save()


def test_isrc_cannot_be_cleared() -> None:
    track = TrackFactory()
    track.isrc = None
    with pytest.raises(ImmutableFieldError):
        track.save()


def test_unassigned_external_id_can_be_filled_once() -> None:
    artist = ArtistFactory()
    assert artist.musicbrainz_id is None
    mbid = uuid.uuid4()
    artist.musicbrainz_id = mbid
    artist.save()
    artist.refresh_from_db()
    assert artist.musicbrainz_id == mbid


def test_resaving_unchanged_ids_and_mutable_fields_is_allowed() -> None:
    artist = ArtistFactory(name="Old")
    artist.name = "New"
    artist.save()
    artist.refresh_from_db()
    assert artist.name == "New"


@pytest.mark.parametrize("field", ["deezer_id", "musicbrainz_id"])
def test_external_ids_are_unique(field: str) -> None:
    value = 5 if field == "deezer_id" else uuid.uuid4()
    ArtistFactory(**{field: value})
    with pytest.raises(IntegrityError), transaction.atomic():
        ArtistFactory(**{field: value})


def test_isrc_is_unique() -> None:
    TrackFactory(isrc="ES0000000001")
    with pytest.raises(IntegrityError), transaction.atomic():
        TrackFactory(isrc="ES0000000001")


# --- Relaciones / Relations ---


def test_credits_keep_position_order() -> None:
    track = TrackFactory(credit=None)
    first, second = ArtistFactory(), ArtistFactory()
    TrackArtistFactory(track=track, artist=second, position=1)
    TrackArtistFactory(track=track, artist=first, position=0)
    assert [c.artist for c in track.credits.all()] == [first, second]


def test_artist_credited_once_per_track_and_album() -> None:
    track = TrackFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        TrackArtistFactory(track=track, artist=track.artists.get())
    album = AlbumFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        AlbumArtist.objects.create(album=album, artist=album.artists.get())


def test_track_has_no_copy_of_album_or_artist_names() -> None:
    names = {f.name for f in Track._meta.get_fields()}
    assert not names & {"album_title", "album_name", "artist_name", "artist"}


def test_track_ordering_follows_the_disc() -> None:
    album = AlbumFactory()
    b = TrackFactory(album=album, disc_number=1, track_number=2)
    a = TrackFactory(album=album, disc_number=1, track_number=1)
    c = TrackFactory(album=album, disc_number=2, track_number=1)
    assert list(album.tracks.all()) == [a, b, c]


def test_album_release_date_is_optional() -> None:
    assert AlbumFactory().release_date is None
    assert AlbumFactory(release_date=date(2020, 1, 1)).release_date == date(2020, 1, 1)


# --- Bloqueos / Blocking ---


def test_blocked_item_is_unique_per_kind_and_id() -> None:
    BlockedItem.objects.create(kind=BlockedItem.Kind.ARTIST, deezer_id=1)
    BlockedItem.objects.create(kind=BlockedItem.Kind.ALBUM, deezer_id=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        BlockedItem.objects.create(kind=BlockedItem.Kind.ARTIST, deezer_id=1)


# --- Descargas / Downloads ---


def test_downloaded_is_derived_from_download() -> None:
    done, pending = TrackFactory(), TrackFactory()
    DownloadFactory(track=done)
    assert done.is_downloaded
    assert not pending.is_downloaded
    flags = {t.pk: t.downloaded for t in Track.objects.with_downloaded()}
    assert flags == {done.pk: True, pending.pk: False}


def test_download_is_append_only() -> None:
    download = DownloadFactory()
    download.file_path = "/other.mp3"
    with pytest.raises(AppendOnlyError):
        download.save()
    with pytest.raises(AppendOnlyError):
        download.delete()
    with pytest.raises(AppendOnlyError):
        Download.objects.update(file_path="x")


def test_downloaded_track_cannot_be_deleted() -> None:
    download = DownloadFactory()
    with pytest.raises(Exception, match="protected"), transaction.atomic():
        download.track.delete()


# --- Historial / History ---


@pytest.mark.parametrize("model", [Artist, Album, Track, BlockedItem])
def test_editable_models_keep_history(model: Any) -> None:
    assert hasattr(model, "history")


def test_history_records_each_change() -> None:
    artist = ArtistFactory(name="A")
    artist.name = "B"
    artist.save()
    assert [h.name for h in artist.history.all()] == ["B", "A"]
