"""Tests de las comprobaciones de novedades. / Tests for new-release checks."""

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
import requests
from django.contrib.auth.models import User
from django.utils import timezone

from activity.models import ActivityLog
from catalog.factories import ArtistFactory
from catalog.models import Album, BlockedItem, Track
from integrations.deezer.models import Album as RemoteAlbum
from integrations.deezer.models import ArtistRef, Page
from integrations.deezer.models import Track as RemoteTrack
from jobs import registry, runner, scheduler
from jobs.models import JobRun
from watches import services
from watches.models import Watch, WatchArtist, WatchRun
from watches.tasks.check import watch_check

pytestmark = pytest.mark.django_db


class FakeDeezer:
    """Deezer simulado con dos páginas de álbumes. / Fake Deezer with two album pages."""

    def __init__(self, albums: dict[int, list[RemoteAlbum]], fail: bool = False) -> None:
        """Álbumes por artista y si falla. / Albums per artist and whether it fails."""
        self.albums, self.fail = albums, fail

    def artist_albums(self, artist_id: int, index: int = 0) -> Page[RemoteAlbum]:
        """Álbumes del artista, de uno en uno. / The artist's albums, one per page."""
        if self.fail:
            raise requests.ConnectionError("sin red")
        items = self.albums.get(artist_id, [])
        # Una página por álbum, para ejercitar la paginación.
        nxt = index + 1 if index + 1 < len(items) else None
        return Page(tuple(items[index : index + 1]), len(items), nxt)

    def album_tracks(self, album: RemoteAlbum, index: int = 0) -> Page[RemoteTrack]:
        """Dos canciones con un invitado sin id. / Two tracks with an id-less guest."""
        mine = ArtistRef("Guest", None), ArtistRef("Main", album.id)
        tracks = tuple(
            RemoteTrack(album.id * 10 + n, f"T{n}", mine, track_position=n) for n in (1, 2)
        )
        return Page(tracks)


def _album(album_id: int, artist: int) -> RemoteAlbum:
    return RemoteAlbum(album_id, f"A{album_id}", (ArtistRef("Main", artist),), date(2026, 1, 1))


def _watch(*deezer_ids: int, **fields: Any) -> Watch:
    watch = Watch.objects.create(**{"name": "w", **fields})
    for position, deezer_id in enumerate(deezer_ids):
        artist = ArtistFactory.create(deezer_id=deezer_id)
        WatchArtist.objects.create(watch=watch, artist=artist, position=position)
    return watch


def test_check_imports_only_new_unblocked_albums() -> None:
    watch = _watch(1)
    Album.objects.create(deezer_id=10, title="ya está")
    BlockedItem.objects.create(kind="album", deezer_id=11)
    client = FakeDeezer({1: [_album(10, 1), _album(11, 1), _album(12, 1)]})
    run = services.check_watch(watch, client=client)
    assert (run.status, run.found, run.detail) == (WatchRun.Status.SUCCEEDED, 1, "")
    album = Album.objects.get(deezer_id=12)
    assert album.credits.count() == 1 and album.tracks.count() == 2
    # El invitado sin id no se enlaza; el resto de créditos sí.
    assert Track.objects.get(deezer_id=121).credits.count() == 1


def test_check_is_idempotent_and_skips_blocked_tracks() -> None:
    watch = _watch(1)
    BlockedItem.objects.create(kind="track", deezer_id=121)
    client = FakeDeezer({1: [_album(12, 1)]})
    services.check_watch(watch, client=client)
    again = services.check_watch(watch, client=client)
    assert again.found == 0 and Track.objects.count() == 1


def test_track_already_in_catalogue_is_not_duplicated() -> None:
    watch = _watch(1)
    other = Album.objects.create(deezer_id=99, title="otra edición")
    Track.objects.create(album=other, deezer_id=121, title="T1")
    services.check_watch(watch, client=FakeDeezer({1: [_album(12, 1)]}))
    assert Track.objects.filter(deezer_id=121).count() == 1


def test_artist_without_deezer_id_is_skipped() -> None:
    watch = Watch.objects.create(name="w")
    WatchArtist.objects.create(watch=watch, artist=ArtistFactory.create(deezer_id=None))
    run = services.check_watch(watch, client=FakeDeezer({}))
    assert run.found == 0 and run.status == WatchRun.Status.SUCCEEDED


def test_failed_check_still_writes_run_and_reschedules() -> None:
    watch = _watch(1, interval_hours=2)
    run = services.check_watch(watch, client=FakeDeezer({}, fail=True))
    assert run.status == WatchRun.Status.FAILED and "sin red" in run.detail
    watch.refresh_from_db()
    assert watch.next_run_at > timezone.now() + timedelta(hours=1, minutes=59)


def test_failure_without_message_uses_exception_name(monkeypatch: pytest.MonkeyPatch) -> None:
    watch = _watch(1)
    monkeypatch.setattr(services, "new_albums", lambda *a: (_ for _ in ()).throw(KeyError()))
    assert services.check_watch(watch, client=FakeDeezer({})).detail == "KeyError"


@pytest.fixture
def downloads(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Registra las llamadas a ``runner.start``. / Records ``runner.start`` calls."""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(runner, "start", lambda kind, params, user: calls.append(params))
    return calls


def test_auto_download_starts_download_of_new_tracks(downloads: list[dict[str, Any]]) -> None:
    watch = _watch(1, auto_download=True)
    services.check_watch(watch, client=FakeDeezer({1: [_album(12, 1)]}))
    assert len(downloads) == 1 and len(downloads[0]["track_ids"]) == 2


def test_no_download_without_flag_or_news(downloads: list[dict[str, Any]]) -> None:
    services.check_watch(_watch(1), client=FakeDeezer({1: [_album(12, 1)]}))
    services.check_watch(
        _watch(2, auto_download=True) if False else Watch.objects.get(), client=FakeDeezer({})
    )
    assert downloads == []


@pytest.mark.parametrize("error", [registry.UnknownJobKind, runner.JobAlreadyRunning])
def test_download_that_cannot_start_does_not_fail_the_check(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    def refuse(*args: Any) -> None:
        raise error("download")

    monkeypatch.setattr(runner, "start", refuse)
    watch = _watch(1, auto_download=True)
    run = services.check_watch(watch, client=FakeDeezer({1: [_album(12, 1)]}))
    assert run.status == WatchRun.Status.SUCCEEDED and error.__name__ in run.detail


def test_default_client_is_created_when_none_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "DeezerClient", lambda: FakeDeezer({}))
    assert services.check_watch(_watch(1)).found == 0


def test_due_watches_ignores_disabled_and_future() -> None:
    due = Watch.objects.create(name="due")
    Watch.objects.create(name="off", enabled=False)
    Watch.objects.create(name="later", next_run_at=timezone.now() + timedelta(hours=1))
    assert services.due_watches() == [due]


def test_launch_due_starts_task_only_when_something_is_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[str] = []
    monkeypatch.setattr(runner, "start", lambda kind, params, user: started.append(kind))
    services.launch_due()
    assert started == []
    Watch.objects.create(name="due")
    services.launch_due()
    assert started == ["watch_check"]


def test_launch_due_tolerates_a_running_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def busy(*args: Any) -> None:
        raise runner.JobAlreadyRunning("watch_check")

    monkeypatch.setattr(runner, "start", busy)
    Watch.objects.create(name="due")
    services.launch_due()


def test_task_and_periodic_are_registered() -> None:
    assert registry.get("watch_check") is watch_check
    assert scheduler._periodics["watch_check"].func is services.launch_due


@pytest.fixture
def fake_deezer(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        services, "DeezerClient", lambda: FakeDeezer({1: [_album(12, 1)], 2: []}, fail=False)
    )
    yield


def test_task_checks_due_watches(fake_deezer: None) -> None:
    _watch(1)
    run = runner.start("watch_check", {}, User.objects.create_user("ana"))
    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary == {"checked": 1, "albums": 1, "failed": 0}
    assert run.lines.get().message == "w: 1 álbumes nuevos"
    assert WatchRun.objects.count() == 1


def test_task_with_watch_id_checks_it_even_if_disabled(fake_deezer: None) -> None:
    watch = _watch(1, enabled=False)
    run = runner.start("watch_check", {"watch_id": watch.pk}, None)
    assert run.summary["checked"] == 1


def test_task_reports_failed_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "DeezerClient", lambda: FakeDeezer({}, fail=True))
    _watch(1)
    run = runner.start("watch_check", {}, None)
    assert run.status == JobRun.Status.SUCCEEDED and run.summary["failed"] == 1
    assert run.lines.get().level == "error" and "sin red" in run.lines.get().message


def test_task_stops_between_watches(fake_deezer: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _watch(1)
    monkeypatch.setattr(runner, "should_stop", lambda run: True)
    run = runner.start("watch_check", {}, None)
    assert run.summary["checked"] == 0 and not WatchRun.objects.exists()


class DetailedDeezer(FakeDeezer):
    """Canciones en dos páginas con todos los datos. / Tracks over two pages, every field set."""

    def album_tracks(self, album: RemoteAlbum, index: int = 0) -> Page[RemoteTrack]:
        """Una canción por página. / One track per page."""
        artists = (ArtistRef("Main", 1), ArtistRef("Second", 2))
        tracks = [
            RemoteTrack(501, "Uno", artists, duration=200, track_position=3, disk_number=2),
            RemoteTrack(502, "Dos", artists[:1]),
        ]
        return Page(tuple(tracks[index : index + 1]), 2, 1 if index == 0 else None)


def test_check_copies_album_and_track_data_and_counts_every_album(
    downloads: list[dict[str, Any]],
) -> None:
    watch = _watch(1, 2, auto_download=True)
    user = User.objects.create_user("ana")
    album = RemoteAlbum(
        12, "Nuevo", (ArtistRef("Main", 1), ArtistRef("Second", 2)), date(2026, 3, 4),
        cover_url="https://img/c.jpg",
    )  # fmt: skip
    client = DetailedDeezer({1: [album, _album(13, 1)]})

    run = services.check_watch(watch, user=user, client=client)

    assert run.found == 2 and run.started_at <= run.finished_at
    saved = Album.objects.get(deezer_id=12)
    assert (saved.title, saved.release_date, saved.cover_url) == (
        "Nuevo", date(2026, 3, 4), "https://img/c.jpg",
    )  # fmt: skip
    assert list(saved.credits.values_list("artist__deezer_id", "position")) == [(1, 0), (2, 1)]
    first, second = Track.objects.filter(album=saved).order_by("deezer_id")
    assert (first.title, first.track_number, first.disc_number, first.duration) == (
        "Uno",
        3,
        2,
        200,
    )
    assert (second.track_number, second.disc_number, second.duration) == (1, 1, None)
    assert list(first.credits.values_list("artist__deezer_id", "position")) == [(1, 0), (2, 1)]
    # Solo el primer álbum trae canciones nuevas: el segundo repite los mismos id.
    assert len(downloads[0]["track_ids"]) == 2
    log = ActivityLog.objects.get(action="watches.watch.checked")
    assert (log.username, log.object_id, log.detail) == (
        "ana", str(watch.pk), {"status": "succeeded", "albums": 2},
    )  # fmt: skip


def test_launch_due_ignores_disabled_watches(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[str] = []
    monkeypatch.setattr(runner, "start", lambda kind, params, user: started.append(kind))
    Watch.objects.create(name="off", enabled=False)
    services.launch_due()
    assert started == []
