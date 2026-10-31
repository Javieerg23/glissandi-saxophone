"""Tests de la importación de artistas, con Deezer y MusicBrainz simulados.

Artist import tests, with Deezer and MusicBrainz faked.
"""

from datetime import date
from typing import Any

import pytest
import requests

from activity.models import ActivityLog
from catalog.factories import ArtistFactory
from catalog.models import Album, Artist, BlockedItem, Track
from catalog.services.importing import Importer
from integrations import deezer as dz
from integrations.deezer import DeezerError
from integrations.musicbrainz.client import Artist as MbArtist
from integrations.musicbrainz.client import Recording
from jobs import registry, runner
from jobs.models import JobRun, JobRunLine

pytestmark = pytest.mark.django_db

MBID = "11111111-1111-1111-1111-111111111111"
MBID_2 = "22222222-2222-2222-2222-222222222222"


class FakeDeezer:
    """Cliente de Deezer en memoria. / In-memory Deezer client."""

    def __init__(self) -> None:
        """Datos de ejemplo. / Sample data."""
        self.artists = {1: dz.Artist(1, "Main", "http://img/main.jpg"), 2: dz.Artist(2, "Other")}
        main, guest = dz.ArtistRef("Main", 1), dz.ArtistRef("Guest", 9)
        self.albums = {
            1: [
                dz.Album(10, "First", (main,), date(2020, 1, 1), cover_url="http://img/a.jpg"),
                dz.Album(11, "Second", (main,)),
            ],
            2: [],
        }
        self.tracks = {
            10: [
                dz.Track(
                    100,
                    "One",
                    (main, guest, dz.ArtistRef("Title Guest")),
                    isrc="AA1",
                    track_position=1,
                ),
                dz.Track(
                    101, "Two", (main,), isrc="AA2", track_position=2, disk_number=2, duration=30
                ),
            ],
            11: [dz.Track(102, "Three", (main,), isrc="AA1")],  # mismo ISRC que "One"
        }
        self.calls: list[str] = []

    def get_artist(self, artist_id: int) -> dz.Artist:
        """Artista o error de Deezer. / Artist or Deezer error."""
        if artist_id == 404:
            raise DeezerError("DataException: no data")
        return self.artists[artist_id]

    def artist_albums(self, artist_id: int, index: int = 0, limit: int = 25) -> dz.Page[dz.Album]:
        """Un álbum por página. / One album per page."""
        items = self.albums[artist_id]
        # Una página por álbum, para probar la paginación. / One album per page, to test paging.
        nxt = index + 1 if index + 1 < len(items) else None
        return dz.Page(tuple(items[index : index + 1]), len(items), nxt)

    def album_tracks(self, album: dz.Album, index: int = 0, limit: int = 25) -> dz.Page[dz.Track]:
        """Canciones del álbum. / Album tracks."""
        return dz.Page(tuple(self.tracks[album.id]), len(self.tracks[album.id]), None)

    def get_track(self, track_id: int) -> dz.Track:
        """Detalle de canción. / Track detail."""
        self.calls.append(f"track/{track_id}")
        return next(t for ts in self.tracks.values() for t in ts if t.id == track_id)


class FakeMusicBrainz:
    """Cliente de MusicBrainz en memoria. / In-memory MusicBrainz client."""

    def __init__(self) -> None:
        """Respuestas de ejemplo. / Sample answers."""
        self.artist_hits = [MbArtist(MBID, "Main", 100)]
        self.recordings = [Recording(MBID_2, "One", ("Main",), ("AA1",))]
        self.fail = False
        self.artist_searches = 0

    def search_artists(self, name: str) -> list[MbArtist]:
        """Candidatos de artista. / Artist candidates."""
        self.artist_searches += 1
        if self.fail:
            raise requests.ConnectionError("caído")
        return self.artist_hits

    def find_artist_image_url(self, mbid: str) -> str | None:
        """Imagen fija. / Fixed image."""
        return "http://mb/main.jpg"

    def search_recordings_by_isrc(self, isrc: str) -> list[Recording]:
        """Grabaciones por ISRC. / Recordings by ISRC."""
        if self.fail:
            raise requests.ConnectionError("caído")
        return self.recordings if isrc == "AA1" else []


@pytest.fixture
def run() -> JobRun:
    return JobRun.objects.create(kind="import", status=JobRun.Status.RUNNING)


@pytest.fixture
def deezer() -> FakeDeezer:
    return FakeDeezer()


def _import(run: JobRun, deezer: FakeDeezer, ids: list[int], mb: Any = None) -> Importer:
    importer = Importer(run, deezer, mb)
    importer.import_artists(ids)
    return importer


def _snapshot() -> tuple[list[Any], ...]:
    return (
        list(Artist.objects.values_list("deezer_id", "name", "image_url")),
        list(Album.objects.values_list("deezer_id", "title")),
        list(Track.objects.values_list("deezer_id", "title", "isrc")),
    )


def test_imports_artist_albums_tracks_and_credits(run: JobRun, deezer: FakeDeezer) -> None:
    importer = _import(run, deezer, [1])

    main = Artist.objects.get(deezer_id=1)
    assert (main.name, main.image_url) == ("Main", "http://img/main.jpg")
    first = Album.objects.get(deezer_id=10)
    assert (first.title, first.release_date, first.cover_url) == (
        "First",
        date(2020, 1, 1),
        "http://img/a.jpg",
    )
    assert list(first.credits.values_list("artist__name", flat=True)) == ["Main"]
    one = Track.objects.get(deezer_id=100)
    # El invitado del título no tiene id de Deezer y se crea por nombre.
    assert list(one.credits.values_list("artist__name", "position")) == [
        ("Main", 0),
        ("Guest", 1),
        ("Title Guest", 2),
    ]
    assert Artist.objects.get(name="Title Guest").deezer_id is None
    two = Track.objects.get(deezer_id=101)
    assert (two.track_number, two.disc_number, two.duration) == (2, 2, 30)
    assert (one.track_number, one.disc_number) == (1, 1)
    # "Three" repite el ISRC de "One": no se duplica la canción.
    assert not Track.objects.filter(deezer_id=102).exists()
    assert dict(importer.counts) == {
        "artists": 1,
        "albums": 2,
        "tracks": 2,
        "duplicate_tracks": 1,
    }


def test_progress_and_log_lines(run: JobRun, deezer: FakeDeezer) -> None:
    _import(run, deezer, [1])
    run.refresh_from_db()
    assert (run.done, run.total) == (2, 2)
    messages = list(run.lines.values_list("message", flat=True))
    assert messages[0] == "Artista «Main»."
    assert "Álbum «First»: 2 canciones." in messages


def test_second_import_changes_nothing(run: JobRun, deezer: FakeDeezer) -> None:
    _import(run, deezer, [1])
    before = _snapshot()
    deezer.calls.clear()

    importer = _import(run, deezer, [1])

    assert _snapshot() == before
    assert deezer.calls == []  # los álbumes ya importados no vuelven a pedir canciones
    assert dict(importer.counts) == {"skipped_albums": 2}


def test_existing_rows_are_not_overwritten(run: JobRun, deezer: FakeDeezer) -> None:
    ArtistFactory(deezer_id=1, name="Edited by hand", image_url="")
    _import(run, deezer, [1])
    artist = Artist.objects.get(deezer_id=1)
    assert (artist.name, artist.image_url) == ("Edited by hand", "")
    assert Album.objects.count() == 2


def test_existing_track_is_skipped(run: JobRun, deezer: FakeDeezer) -> None:
    album_track = deezer.tracks[10][0]
    other = Album.objects.create(deezer_id=77, title="Elsewhere")
    Track.objects.create(album=other, deezer_id=album_track.id, title="One", isrc="ZZ")
    _import(run, deezer, [1])
    assert Track.objects.filter(deezer_id=100).count() == 1
    assert Track.objects.get(deezer_id=100).album == other


def test_blocked_artist_is_skipped(run: JobRun, deezer: FakeDeezer) -> None:
    BlockedItem.objects.create(kind="artist", deezer_id=1)
    importer = _import(run, deezer, [1])
    assert not Artist.objects.exists() and importer.counts["blocked"] == 1


def test_blocked_album_is_skipped(run: JobRun, deezer: FakeDeezer) -> None:
    BlockedItem.objects.create(kind="album", deezer_id=10)
    _import(run, deezer, [1])
    assert list(Album.objects.values_list("deezer_id", flat=True)) == [11]


def test_blocked_track_is_skipped(run: JobRun, deezer: FakeDeezer) -> None:
    BlockedItem.objects.create(kind="track", deezer_id=101)
    _import(run, deezer, [1])
    assert list(Track.objects.values_list("deezer_id", flat=True)) == [100]


def test_blocked_credited_artist_gets_no_credit(run: JobRun, deezer: FakeDeezer) -> None:
    BlockedItem.objects.create(kind="artist", deezer_id=9)
    _import(run, deezer, [1])
    assert not Artist.objects.filter(deezer_id=9).exists()
    one = Track.objects.get(deezer_id=100)
    assert list(one.credits.values_list("artist__name", "position")) == [
        ("Main", 0),
        ("Title Guest", 1),
    ]


def test_title_guest_reuses_artist_with_same_name(run: JobRun, deezer: FakeDeezer) -> None:
    existing = Artist.objects.create(name="title guest")
    _import(run, deezer, [1])
    assert Artist.objects.filter(name__iexact="title guest").count() == 1
    assert Track.objects.get(deezer_id=100).artists.filter(pk=existing.pk).exists()


def test_failing_artist_does_not_stop_the_others(run: JobRun, deezer: FakeDeezer) -> None:
    importer = _import(run, deezer, [404, 1])
    assert importer.counts["failed_artists"] == 1
    assert Album.objects.count() == 2
    error = run.lines.get(level=JobRunLine.Level.ERROR)
    assert error.message == "Artista 404: DataException: no data"


def test_stop_between_albums(
    run: JobRun, deezer: FakeDeezer, monkeypatch: pytest.MonkeyPatch
) -> None:
    stops = iter([False, False, True])  # artista, primer álbum, segundo álbum
    monkeypatch.setattr(runner, "should_stop", lambda _run: next(stops))
    importer = Importer(run, deezer)
    assert importer.import_artists([1, 2]) is False
    assert list(Album.objects.values_list("deezer_id", flat=True)) == [10]


def test_stop_before_next_artist(
    run: JobRun, deezer: FakeDeezer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runner, "should_stop", lambda _run: True)
    assert Importer(run, deezer).import_artists([1]) is False
    assert not Artist.objects.exists()


def test_verification_sets_musicbrainz_ids_and_image(run: JobRun, deezer: FakeDeezer) -> None:
    deezer.artists[1] = dz.Artist(1, "Main")  # sin imagen de Deezer
    mb = FakeMusicBrainz()
    importer = _import(run, deezer, [1], mb)
    artist = Artist.objects.get(deezer_id=1)
    assert (str(artist.musicbrainz_id), artist.image_url) == (MBID, "http://mb/main.jpg")
    assert str(Track.objects.get(deezer_id=100).musicbrainz_id) == MBID_2
    assert Track.objects.get(deezer_id=101).musicbrainz_id is None
    assert importer.counts["verified"] == 2

    before = _snapshot()
    _import(run, deezer, [1], mb)
    assert _snapshot() == before


@pytest.mark.parametrize(
    "hit",
    [MbArtist(MBID, "Main", 80), MbArtist(MBID, "Someone Else", 100)],
    ids=["low-score", "other-name"],
)
def test_unclear_artist_match_is_ignored(run: JobRun, deezer: FakeDeezer, hit: MbArtist) -> None:
    mb = FakeMusicBrainz()
    mb.artist_hits = [hit]
    _import(run, deezer, [1], mb)
    assert Artist.objects.get(deezer_id=1).musicbrainz_id is None


def test_no_artist_match_and_already_used_ids_are_ignored(run: JobRun, deezer: FakeDeezer) -> None:
    mb = FakeMusicBrainz()
    mb.artist_hits = []
    _import(run, deezer, [1], mb)
    assert Artist.objects.get(deezer_id=1).musicbrainz_id is None

    mb.artist_hits = [MbArtist(MBID, "Main", 100)]
    Artist.objects.create(name="Taken", musicbrainz_id=MBID)
    ArtistFactory(deezer_id=2, name="Other")
    Track.objects.all().delete()
    Album.objects.all().delete()
    _import(run, deezer, [1], mb)
    assert Artist.objects.get(deezer_id=1).musicbrainz_id is None


def test_already_verified_artist_is_not_searched_again(run: JobRun, deezer: FakeDeezer) -> None:
    ArtistFactory(deezer_id=1, name="Main", musicbrainz_id=MBID_2)
    mb = FakeMusicBrainz()
    _import(run, deezer, [1], mb)
    assert mb.artist_searches == 0


def test_musicbrainz_outage_only_warns(run: JobRun, deezer: FakeDeezer) -> None:
    mb = FakeMusicBrainz()
    mb.fail = True
    importer = _import(run, deezer, [1], mb)
    assert Track.objects.count() == 2 and importer.counts["verified"] == 0
    assert (
        run.lines.filter(level=JobRunLine.Level.WARNING).count() == 3
    )  # el artista y las dos canciones con ISRC


def test_musicbrainz_id_used_by_another_track_is_not_assigned(
    run: JobRun, deezer: FakeDeezer
) -> None:
    other = Album.objects.create(deezer_id=88, title="X")
    Track.objects.create(album=other, title="Y", musicbrainz_id=MBID_2)
    _import(run, deezer, [1], FakeMusicBrainz())
    assert Track.objects.get(deezer_id=100).musicbrainz_id is None


def test_task_imports_logs_activity_and_reports_summary(
    deezer: FakeDeezer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from catalog.tasks import importing

    monkeypatch.setattr(importing, "DeezerClient", lambda: deezer)
    monkeypatch.setattr(importing, "MusicBrainzClient", FakeMusicBrainz)
    registry.get("import")  # registrada al arrancar / registered at startup

    run = runner.start("import", {"artist_ids": [1], "verify": True}, None)

    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary["albums"] == 2 and run.summary["completed"] is True
    entry = ActivityLog.objects.get(action="catalog.import")
    assert entry.detail["artist_ids"] == [1]


@pytest.mark.parametrize(
    "params", [{}, {"artist_ids": []}, {"artist_ids": "1"}, {"artist_ids": [1, "2"]}]
)
def test_task_rejects_invalid_params(params: dict[str, Any]) -> None:
    run = runner.start("import", params, None)
    assert run.status == JobRun.Status.FAILED


def test_block_applies_only_to_its_own_kind(run: JobRun, deezer: FakeDeezer) -> None:
    """Un id bloqueado de un tipo no bloquea a otro tipo con el mismo id."""
    BlockedItem.objects.create(kind="track", deezer_id=1)
    BlockedItem.objects.create(kind="artist", deezer_id=10)
    _import(run, deezer, [1])
    assert Artist.objects.filter(deezer_id=1).exists()
    assert Album.objects.filter(deezer_id=10).exists()
