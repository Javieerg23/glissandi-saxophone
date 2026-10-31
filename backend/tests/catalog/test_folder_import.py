"""Tests de la importación de carpetas, con Deezer simulado y audio generado aquí.

Folder import tests, with Deezer faked and audio generated here.
"""

import math
import shutil
import struct
import wave
from datetime import date
from pathlib import Path
from typing import Any

import mutagen
import pytest
import requests

from activity.models import ActivityLog
from catalog.models import BlockedItem, Download, Track
from catalog.services import folder_import as service
from catalog.services.folder_import import FolderImporter, find_remote, read_tags, resolve_folder
from integrations import deezer as dz
from integrations.audio import Tags, convert, write_tags
from integrations.deezer import DeezerError
from jobs import registry, runner
from jobs.models import JobRun
from preferences.models import Preference

pytestmark = pytest.mark.django_db

MAIN = dz.ArtistRef("Main", 1)
ALBUM = dz.Album(10, "First", (MAIN,), date(2020, 1, 1))
ONE = dz.Track(100, "One", (MAIN,), dz.AlbumRef(10, "First"), isrc="AAA111", track_position=1)
TWO = dz.Track(101, "Two", (MAIN,), dz.AlbumRef(10, "First"), isrc="AAA222", track_position=2)


class FakeDeezer:
    """Cliente de Deezer en memoria con un álbum de dos canciones.

    In-memory Deezer client with one two-track album.
    """

    def __init__(self) -> None:
        """Sin llamadas todavía. / No calls yet."""
        self.calls: list[str] = []
        self.fail_search = False

    def get_track_by_isrc(self, isrc: str) -> dz.Track:
        """Canción por ISRC o el error de Deezer. / Track by ISRC or Deezer's error."""
        self.calls.append(f"isrc:{isrc}")
        for track in (ONE, TWO):
            if track.isrc == isrc:
                return track
        raise DeezerError("DataException: no data")

    def search_tracks(self, query: str, index: int = 0, limit: int = 25) -> dz.Page[dz.Track]:
        """Devuelve siempre las dos canciones; decide la comprobación del título.

        Always returns both tracks, so the title check is what decides.
        """
        self.calls.append(f"search:{query}")
        if self.fail_search:
            raise requests.ConnectionError("sin red")
        hits = (dz.Track(101, "Two", (MAIN,)), dz.Track(100, "One", (MAIN,)))
        return dz.Page(hits, 2, None)

    def get_track(self, track_id: int) -> dz.Track:
        """Detalle de canción. / Track detail."""
        return ONE if track_id == ONE.id else TWO

    def get_album(self, album_id: int) -> dz.Album:
        """Detalle de álbum. / Album detail."""
        self.calls.append(f"album/{album_id}")
        return ALBUM

    def album_tracks(self, album: dz.Album, index: int = 0, limit: int = 25) -> dz.Page[dz.Track]:
        """Canciones del álbum. / Album tracks."""
        return dz.Page((ONE, TWO), 2, None)


@pytest.fixture(scope="module")
def mp3(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """MP3 diminuto sin etiquetas, generado una vez. / Tiny untagged MP3, generated once."""
    work = tmp_path_factory.mktemp("audio")
    wav = work / "tone.wav"
    with wave.open(str(wav), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(
            b"".join(struct.pack("<h", int(8000 * math.sin(i / 5))) for i in range(800))
        )
    path = convert(wav, work, "mp3")
    mutagen.File(path).delete()
    return path


@pytest.fixture
def deezer() -> FakeDeezer:
    """Cliente de Deezer simulado. / Fake Deezer client."""
    return FakeDeezer()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Carpeta de descargas vacía. / Empty downloads folder."""
    folder = tmp_path / "music"
    folder.mkdir()
    return folder


def _audio(mp3: Path, path: Path, tags: Tags | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(mp3, path)
    if tags:
        write_tags(path, tags)
    return path


def _run() -> JobRun:
    return JobRun.objects.create(kind="folder_import", params={})


def _import(deezer: FakeDeezer, root: Path, folder: str = "") -> FolderImporter:
    importer = FolderImporter(_run(), deezer, root)
    assert importer.import_folder(folder) is True
    return importer


# resolve_folder


def test_resolve_folder_accepts_a_subfolder_and_the_root(root: Path) -> None:
    (root / "a" / "b").mkdir(parents=True)
    assert resolve_folder(root, "a/b") == (root / "a" / "b").resolve()
    assert resolve_folder(root, "") == root.resolve()


@pytest.mark.parametrize("folder", ["..", "a/../..", "/etc", "link"])
def test_resolve_folder_rejects_paths_outside(root: Path, tmp_path: Path, folder: str) -> None:
    (root / "a").mkdir()
    (root / "link").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="fuera"):
        resolve_folder(root, folder)


def test_resolve_folder_rejects_missing_folders(root: Path) -> None:
    (root / "file.mp3").write_bytes(b"")
    for folder in ("missing", "file.mp3"):
        with pytest.raises(ValueError, match="no existe"):
            resolve_folder(root, folder)


# read_tags


def test_read_tags_reads_title_artists_album_number_and_isrc(mp3: Path, tmp_path: Path) -> None:
    tags = Tags("One", ("Main", "Guest"), album="First", track_number=3, isrc="aaa111")
    path = _audio(mp3, tmp_path / "a.mp3", tags)
    assert read_tags(path) == Tags("One", ("Main", "Guest"), "First", 3, isrc="AAA111")


def test_read_tags_handles_track_totals_and_missing_fields(mp3: Path, tmp_path: Path) -> None:
    path = _audio(mp3, tmp_path / "a.mp3", Tags("One", ()))
    audio = mutagen.File(path, easy=True)
    audio["tracknumber"] = "4/12"
    audio.save()
    assert read_tags(path) == Tags("One", (), track_number=4)


def test_read_tags_without_title_or_tags_is_none(mp3: Path, tmp_path: Path) -> None:
    assert read_tags(_audio(mp3, tmp_path / "bare.mp3")) is None
    path = _audio(mp3, tmp_path / "untitled.mp3", Tags("x", ("Main",)))
    audio = mutagen.File(path, easy=True)
    del audio["title"]
    audio.save()
    assert read_tags(path) is None
    (tmp_path / "unknown.ogg").write_bytes(b"not audio at all")
    assert read_tags(tmp_path / "unknown.ogg") is None


def test_read_tags_raises_on_damaged_files(tmp_path: Path) -> None:
    (tmp_path / "broken.mp3").write_bytes(b"\x00" * 64)
    with pytest.raises(mutagen.MutagenError):
        read_tags(tmp_path / "broken.mp3")


# find_remote


def test_find_remote_prefers_the_isrc(deezer: FakeDeezer) -> None:
    assert find_remote(deezer, Tags("whatever", (), isrc="AAA222")) == TWO
    assert deezer.calls == ["isrc:AAA222"]


def test_find_remote_falls_back_to_an_exact_title(deezer: FakeDeezer) -> None:
    found = find_remote(deezer, Tags('Two "live"', ('Ma"in',), isrc="ZZZ"))
    assert found is None
    assert deezer.calls[-1] == 'search:artist:"Main" track:"Two live"'
    assert find_remote(deezer, Tags("two (feat. Other)", ())) == TWO
    assert deezer.calls[-1] == 'search:track:"two (feat. Other)"'


# FolderImporter


def test_import_links_files_imports_albums_and_reports_the_rest(
    mp3: Path, root: Path, tmp_path: Path, deezer: FakeDeezer
) -> None:
    _audio(mp3, root / "Main" / "01 One.mp3", Tags("One", ("Main",), isrc="AAA111"))
    _audio(mp3, root / "Main" / "02 Two.mp3", Tags("Two", ("Main",)))
    _audio(mp3, root / "Main" / "bare.mp3")
    _audio(mp3, root / "Main" / "other.mp3", Tags("Unknown", ("Nobody",)))
    (root / "Main" / "broken.mp3").write_bytes(b"\x00" * 64)
    (root / "Main" / "cover.jpg").write_bytes(b"jpeg")
    (root / "Main" / "outside.mp3").symlink_to(_audio(mp3, tmp_path / "elsewhere.mp3"))

    importer = _import(deezer, root, "Main")

    assert sorted(Track.objects.values_list("title", flat=True)) == ["One", "Two"]
    downloads = dict(Download.objects.values_list("file_path", "track__title"))
    assert downloads == {
        str(root / "Main" / "01 One.mp3"): "One",
        str(root / "Main" / "02 Two.mp3"): "Two",
    }
    assert set(Download.objects.values_list("audio_format", flat=True)) == {"mp3"}
    assert deezer.calls.count("album/10") == 1  # el segundo fichero ya está en el catálogo
    assert importer.counts["linked"] == 2 and importer.counts["albums"] == 1
    assert importer.unlinked == [
        {"file": "Main/bare.mp3", "reason": service.NO_TAGS},
        {"file": "Main/broken.mp3", "reason": service.UNREADABLE},
        {"file": "Main/other.mp3", "reason": service.NOT_FOUND},
        {"file": "Main/outside.mp3", "reason": service.OUTSIDE},
    ]
    run = importer.run
    run.refresh_from_db()
    assert (run.done, run.total) == (6, 6)


def test_import_twice_changes_nothing(mp3: Path, root: Path, deezer: FakeDeezer) -> None:
    _audio(mp3, root / "One.mp3", Tags("One", ("Main",), isrc="AAA111"))
    _import(deezer, root)
    deezer.calls.clear()

    again = _import(deezer, root)

    assert again.counts["already_linked"] == 1 and again.linked == 0
    assert Download.objects.count() == 1 and deezer.calls == []


def test_blocked_tracks_are_reported_not_imported(
    mp3: Path, root: Path, deezer: FakeDeezer
) -> None:
    BlockedItem.objects.create(kind=BlockedItem.Kind.ALBUM, deezer_id=10)
    _audio(mp3, root / "One.mp3", Tags("One", ("Main",), isrc="AAA111"))

    importer = _import(deezer, root)

    assert importer.unlinked == [{"file": "One.mp3", "reason": service.NOT_IN_CATALOG}]
    assert not Download.objects.exists()


def test_a_track_without_album_is_not_in_catalog(
    mp3: Path, root: Path, deezer: FakeDeezer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deezer, "get_track", lambda _id: dz.Track(100, "One", (MAIN,)))
    _audio(mp3, root / "One.mp3", Tags("One", ("Main",)))

    assert _import(deezer, root).unlinked[0]["reason"] == service.NOT_IN_CATALOG


def test_deezer_errors_are_reported_per_file(mp3: Path, root: Path, deezer: FakeDeezer) -> None:
    deezer.fail_search = True
    _audio(mp3, root / "One.mp3", Tags("One", ("Main",)))

    importer = _import(deezer, root)

    assert importer.unlinked == [{"file": "One.mp3", "reason": service.LOOKUP_ERROR}]
    assert "sin red" in importer.run.lines.get().message


def test_stop_is_honoured_between_files(
    mp3: Path, root: Path, deezer: FakeDeezer, monkeypatch: pytest.MonkeyPatch
) -> None:
    _audio(mp3, root / "One.mp3", Tags("One", ("Main",), isrc="AAA111"))
    monkeypatch.setattr(runner, "should_stop", lambda run: True)
    importer = FolderImporter(_run(), deezer, root)

    assert importer.import_folder("") is False
    assert not Download.objects.exists()


# Tarea / Task


def test_task_links_the_folder_and_logs_activity(
    mp3: Path, root: Path, deezer: FakeDeezer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from catalog.tasks import folder_import as task

    monkeypatch.setattr(task, "DeezerClient", lambda: deezer)
    Preference.objects.create(key="download.folder", value=str(root))
    _audio(mp3, root / "A" / "One.mp3", Tags("One", ("Main",), isrc="AAA111"))
    registry.get("folder_import")  # registrada al arrancar / registered at startup

    run = runner.start("folder_import", {"folder": "A"}, None)

    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary["linked"] == 1 and run.summary["completed"] is True
    assert run.summary["unlinked"] == []
    entry = ActivityLog.objects.get(action="catalog.folder_import")
    assert entry.detail == {"folder": "A", "linked": 1, "unlinked": 0}


@pytest.mark.parametrize("params", [{"folder": 1}, {"folder": ".."}, {"folder": "missing"}])
def test_task_rejects_invalid_folders(root: Path, params: dict[str, Any]) -> None:
    Preference.objects.create(key="download.folder", value=str(root))

    run = runner.start("folder_import", params, None)

    assert run.status == JobRun.Status.FAILED
    assert not ActivityLog.objects.filter(action="catalog.folder_import").exists()
