"""Tests de las utilidades de mantenimiento. / Tests for the maintenance utilities."""

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
import requests
from django.contrib.auth.models import User

import catalog.tasks.maintenance as maintenance_tasks
from activity.models import ActivityLog
from catalog.factories import AlbumFactory, ArtistFactory, DownloadFactory, TrackFactory
from catalog.models import Download, Track
from catalog.services import maintenance as service
from integrations.audio import AudioError, Tags
from integrations.deezer import DeezerError
from integrations.deezer.client import parse_track
from jobs import registry, runner
from jobs.models import JobRun, JobRunLine

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla el registro de las tareas reales. / Isolates the registry from real tasks."""
    monkeypatch.setattr(registry, "_tasks", {})


@pytest.fixture
def maintenance_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registra la tarea en el registro aislado. / Registers the task in the isolated registry."""
    registry.register("maintenance")(maintenance_tasks.maintenance)


@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Path, Tags]]:
    """Sustituye la escritura de etiquetas y la guarda. / Replaces tag writing and records calls."""
    calls: list[tuple[Path, Tags]] = []
    monkeypatch.setattr(service, "write_tags", lambda path, tags: calls.append((path, tags)))
    return calls


def _run() -> JobRun:
    return JobRun.objects.create(kind="maintenance", params={})


def _lines(run: JobRun) -> list[str]:
    return list(run.lines.values_list("message", flat=True))


def _file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(b"audio")
    return path


def _download(tmp_path: Path, name: str = "a.mp3", track: Track | None = None) -> Download:
    """Descarga con un fichero real y, por defecto, una canción sin identificador de Deezer.

    Download with a real file and, by default, a track without a Deezer id so
    nothing reaches the network.
    """
    track = track or TrackFactory(deezer_id=None)
    return cast(Download, DownloadFactory(file_path=str(_file(tmp_path, name)), track=track))


def _no_cover(url: str) -> bytes:
    raise AssertionError(f"no debería descargar {url}")


class FakeResponse:
    """Respuesta HTTP simulada. / Simulated HTTP response."""

    def __init__(self, content: bytes, status: int = 200) -> None:
        """Guarda el cuerpo y el estado. / Stores the body and the status."""
        self.content = content
        self._status = status

    def raise_for_status(self) -> None:
        """Falla como ``requests`` ante un error. / Fails like ``requests`` on error."""
        if self._status >= 400:
            raise requests.HTTPError(f"HTTP {self._status}")


class FakeSession:
    """Sesión simulada que guarda las direcciones. / Simulated session recording URLs."""

    def __init__(self, response: FakeResponse) -> None:
        """Guarda la respuesta a devolver. / Stores the response to return."""
        self.response = response
        self.urls: list[str] = []

    def __enter__(self) -> "FakeSession":
        """Devuelve la propia sesión. / Returns the session itself."""
        return self

    def __exit__(self, *args: object) -> None:
        """No hay recursos que cerrar. / There is nothing to close."""

    def get(self, url: str) -> FakeResponse:
        """Devuelve la respuesta preparada. / Returns the prepared response."""
        self.urls.append(url)
        return self.response


def test_download_cover_returns_the_image_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(FakeResponse(b"jpeg"))
    monkeypatch.setattr(service, "build_session", lambda: session)

    assert service.download_cover("https://img/c") == b"jpeg"
    assert session.urls == ["https://img/c"]


def test_download_cover_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "build_session", lambda: FakeSession(FakeResponse(b"", 404)))

    with pytest.raises(requests.HTTPError):
        service.download_cover("https://img/missing")


def test_retag_writes_full_tags_including_credits_and_cover(
    tmp_path: Path, written: list[tuple[Path, Tags]]
) -> None:
    album = AlbumFactory(title="Disco", release_date=date(2019, 5, 1), cover_url="https://img/c")
    track = TrackFactory(album=album, title="Tema", track_number=3, disc_number=2, isrc="ES1")
    track.credits.all().delete()
    track.credits.create(artist=ArtistFactory(name="Principal"), position=0)
    track.credits.create(artist=ArtistFactory(name="Invitado"), position=1)
    path = _file(tmp_path, "tema.flac")
    DownloadFactory(track=track, file_path=str(path), audio_format="flac")

    summary = service.retag_downloads(_run(), fetch_cover=lambda url: b"\x89PNG\r\n\x1a\nimg")

    assert summary == {"retagged": 1, "failed": 0}
    assert written == [
        (
            path,
            Tags(
                title="Tema",
                artists=("Principal", "Invitado"),
                album="Disco",
                track_number=3,
                disc_number=2,
                year=2019,
                isrc="ES1",
                cover=b"\x89PNG\r\n\x1a\nimg",
            ),
        )
    ]
    assert ActivityLog.objects.filter(action="catalog.download.retagged").exists()


def test_retag_fetches_each_album_cover_once_and_skips_albums_without_one(
    tmp_path: Path, written: list[tuple[Path, Tags]]
) -> None:
    album = AlbumFactory(cover_url="https://img/c")
    for name in ("1.mp3", "2.mp3"):
        DownloadFactory(file_path=str(_file(tmp_path, name)), track=TrackFactory(album=album))
    DownloadFactory(
        file_path=str(_file(tmp_path, "lone.mp3")),
        track=TrackFactory(album=AlbumFactory(cover_url="")),
    )
    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return b"jpeg"

    summary = service.retag_downloads(_run(), fetch_cover=fetch)

    assert summary == {"retagged": 3, "failed": 0}
    assert fetched == ["https://img/c"]
    assert [tags.cover for _, tags in written] == [b"jpeg", b"jpeg", None]


def test_retag_failures_are_logged_and_do_not_stop_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _download(tmp_path, "bad.wav")
    _download(tmp_path, "good.mp3")
    DownloadFactory(file_path=str(tmp_path / "missing.mp3"), track=TrackFactory(deezer_id=None))

    def write(path: Path, tags: Tags) -> None:
        if path.suffix == ".wav":
            raise AudioError("cannot tag .wav")

    monkeypatch.setattr(service, "write_tags", write)
    run = _run()

    summary = service.retag_downloads(run, fetch_cover=_no_cover)

    assert summary == {"retagged": 1, "failed": 2}
    messages = _lines(run)
    assert any("bad.wav" in message for message in messages)
    assert any("Falta el fichero" in message and "missing.mp3" in message for message in messages)


def test_retag_cover_download_error_skips_the_file_instead_of_dropping_its_cover(
    tmp_path: Path, written: list[tuple[Path, Tags]]
) -> None:
    _download(tmp_path, track=TrackFactory(album=AlbumFactory(cover_url="https://img/c")))

    def fail(url: str) -> bytes:
        raise requests.ConnectionError("sin red")

    summary = service.retag_downloads(_run(), fetch_cover=fail)

    assert summary == {"retagged": 0, "failed": 1}
    assert written == []


def test_retag_stops_between_files(tmp_path: Path, written: list[tuple[Path, Tags]]) -> None:
    _download(tmp_path, "a.mp3")
    _download(tmp_path, "b.mp3")
    run = _run()
    JobRun.objects.filter(pk=run.pk).update(status=JobRun.Status.STOPPING)

    summary = service.retag_downloads(run, fetch_cover=_no_cover)

    assert summary == {"retagged": 0, "failed": 0}
    assert written == []


def test_check_files_reports_missing_and_deletes_nothing(tmp_path: Path) -> None:
    present = _download(tmp_path, "here.mp3")
    missing = DownloadFactory(file_path=str(tmp_path / "gone.mp3"), track=TrackFactory())
    run = _run()

    summary = service.check_download_files(run)

    assert summary == {"checked": 2, "missing": [missing.pk]}
    assert Download.objects.filter(pk=present.pk).exists()
    assert Download.objects.filter(pk=missing.pk).exists()
    assert (tmp_path / "here.mp3").exists()
    assert len(_lines(run)) == 1 and "gone.mp3" in _lines(run)[0]


def test_check_files_without_downloads() -> None:
    assert service.check_download_files(_run()) == {"checked": 0, "missing": []}


def test_check_files_stops_between_files(tmp_path: Path) -> None:
    _download(tmp_path, "a.mp3")
    run = _run()
    JobRun.objects.filter(pk=run.pk).update(status=JobRun.Status.STOPPING)

    assert service.check_download_files(run) == {"checked": 0, "missing": []}


class FakeDeezer:
    """Cliente de Deezer simulado. / Simulated Deezer client."""

    def __init__(self, raw: dict[int, dict[str, Any]], failing: set[int] | None = None) -> None:
        """Guarda las canciones y las que fallan. / Stores the tracks and the failing ids."""
        self._raw = raw
        self._failing = failing or set()

    def get_track(self, track_id: int) -> Any:
        """Devuelve la canción parseada o falla. / Returns the parsed track or fails."""
        if track_id in self._failing:
            raise DeezerError("fuera de servicio")
        return parse_track(self._raw[track_id])


def _remote(track_id: int, main: str, guests: tuple[str, ...] = ()) -> dict[str, Any]:
    """Objeto ``track`` de Deezer con invitados en el título. / Deezer track with guests."""
    title = "Tema" + "".join(f" (feat. {guest})" for guest in guests)
    return {
        "id": track_id,
        "title": title,
        "artist": {"name": main, "id": 1000 + track_id},
        "contributors": [],
    }


def test_review_reports_credit_differences_without_changing_them() -> None:
    track = TrackFactory(deezer_id=7, title="Tema")
    track.credits.all().delete()
    track.credits.create(artist=ArtistFactory(name="Principal"), position=0)
    track.credits.create(artist=ArtistFactory(name="Sobra"), position=1)
    run = _run()
    client = FakeDeezer({7: _remote(7, "Principal", ("Invitado",))})

    summary = service.review_track_artists(run, client=client)

    assert summary == {"reviewed": 1, "differences": 1, "errors": 0}
    assert len(_lines(run)) == 1
    assert "faltan Invitado" in _lines(run)[0] and "sobran Sobra" in _lines(run)[0]
    assert sorted(track.credits.values_list("artist__name", flat=True)) == ["Principal", "Sobra"]


def test_review_matching_credits_are_silent_and_case_insensitive() -> None:
    track = TrackFactory(deezer_id=8)
    track.credits.all().delete()
    track.credits.create(artist=ArtistFactory(name="ana"), position=0)
    run = _run()

    summary = service.review_track_artists(run, client=FakeDeezer({8: _remote(8, "ANA")}))

    assert summary == {"reviewed": 1, "differences": 0, "errors": 0}
    assert _lines(run) == []


def test_review_counts_lookup_errors_and_continues() -> None:
    TrackFactory(deezer_id=9, title="Caída")
    ok = TrackFactory(deezer_id=10, title="Bien")
    ok.credits.all().delete()
    ok.credits.create(artist=ArtistFactory(name="Artist"), position=0)
    TrackFactory(deezer_id=None)
    run = _run()
    client = FakeDeezer({10: _remote(10, "Artist")}, failing={9})

    summary = service.review_track_artists(run, client=client)

    assert summary == {"reviewed": 2, "differences": 0, "errors": 1}
    assert any("Caída" in message for message in _lines(run))


def test_review_builds_a_default_client_when_none_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[bool] = []

    def fake_client() -> FakeDeezer:
        built.append(True)
        return FakeDeezer({})

    monkeypatch.setattr(service, "DeezerClient", fake_client)

    assert service.review_track_artists(_run()) == {"reviewed": 0, "differences": 0, "errors": 0}
    assert built == [True]


def test_review_stops_between_tracks() -> None:
    TrackFactory(deezer_id=11)
    run = _run()
    JobRun.objects.filter(pk=run.pk).update(status=JobRun.Status.STOPPING)

    summary = service.review_track_artists(run, client=FakeDeezer({}))

    assert summary == {"reviewed": 0, "differences": 0, "errors": 0}


@pytest.mark.usefixtures("maintenance_registered", "written")
def test_task_runs_every_operation_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "DeezerClient", lambda: FakeDeezer({}))
    _download(tmp_path)

    run = runner.start("maintenance", None, User.objects.create_user("ana"))

    assert run.status == JobRun.Status.SUCCEEDED
    assert set(run.summary) == {"retag", "check_files", "review_artists"}


@pytest.mark.usefixtures("maintenance_registered")
def test_task_runs_only_the_requested_operations(
    tmp_path: Path, written: list[tuple[Path, Tags]]
) -> None:
    _download(tmp_path)

    run = runner.start("maintenance", {"operations": ["check_files"]}, None)

    assert run.summary == {"check_files": {"checked": 1, "missing": []}}
    assert written == []


@pytest.mark.usefixtures("maintenance_registered")
@pytest.mark.parametrize("operations", [["borrar_todo"], "retag", [1]])
def test_task_rejects_invalid_operations(operations: Any) -> None:
    run = runner.start("maintenance", {"operations": operations}, None)

    assert run.status == JobRun.Status.FAILED
    assert run.lines.get(level=JobRunLine.Level.ERROR).message


@pytest.mark.usefixtures("maintenance_registered")
def test_task_does_nothing_after_a_stop_request() -> None:
    run = _run()
    JobRun.objects.filter(pk=run.pk).update(status=JobRun.Status.STOPPING)

    assert maintenance_tasks.maintenance(run, {}) == {}
