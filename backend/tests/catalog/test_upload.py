"""Tests de la subida manual de audio, con ffmpeg simulado. / Manual audio upload tests."""

import math
import struct
import wave
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP
from activity.models import ActivityLog
from catalog import upload
from catalog.factories import TrackFactory
from catalog.models import Download
from integrations.audio import ConversionError
from preferences.models import Preference
from tests.accounts.conftest import make_user

pytestmark = pytest.mark.django_db


def _wav() -> bytes:
    """WAV de 0,3 s con un tono. / 0.3 s WAV with a tone."""
    buffer = BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(
            b"".join(struct.pack("<h", int(8000 * math.sin(i / 5))) for i in range(2400))
        )
    return buffer.getvalue()


def _file(name: str = "grabación.wav", content: bytes | None = None) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, _wav() if content is None else content, "audio/wav")


@pytest.fixture(autouse=True)
def fake_media(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Sustituye ffmpeg y mutagen al escribir; devuelve lo que se les pidió.

    Replaces ffmpeg and tag writing; returns what they were asked.
    """
    calls: dict[str, Any] = {"converted": [], "tagged": []}
    Preference.objects.create(key="download.folder", value=str(tmp_path / "library"))

    def to_format(source: Path, dest_dir: Path, fmt: str, *, stem: str | None = None) -> Path:
        calls["converted"].append(source.read_bytes())
        out = dest_dir / f"{stem or source.stem}.{fmt}"
        out.write_bytes(b"audio")
        return out

    monkeypatch.setattr(upload, "convert", to_format)
    monkeypatch.setattr(upload, "write_tags", lambda path, tags: calls["tagged"].append(tags))
    return calls


@pytest.fixture
def admin(db: None) -> APIClient:
    """Cliente con sesión de administrador. / Administrator client."""
    client = APIClient()
    client.force_login(make_user("admin", ADMIN_GROUP))
    return client


def _url(pk: int) -> str:
    return f"/api/v1/catalog/tracks/{pk}/upload/"


def test_converts_tags_stores_and_records(
    admin: APIClient, fake_media: dict[str, Any], tmp_path: Path
) -> None:
    track = TrackFactory(title="Song")
    response = admin.post(_url(track.pk), {"file": _file()}, format="multipart")

    assert response.status_code == 201
    assert response.data["id"] == track.pk
    assert response.data["downloaded"] is True
    download = Download.objects.get(track=track)
    assert Path(download.file_path).read_bytes() == b"audio"
    assert Path(download.file_path).is_relative_to(tmp_path / "library")
    assert Path(download.file_path).name.endswith("Song.mp3")
    assert download.audio_format == "mp3"
    # Sin URL de origen: así se distingue una subida de una descarga de YouTube.
    assert download.source_url == ""
    assert fake_media["converted"] == [_wav()]
    assert fake_media["tagged"][0].title == "Song"
    log = ActivityLog.objects.get(action="catalog.track.uploaded")
    assert log.detail == {"file_path": download.file_path, "audio_format": "mp3"}


def test_respects_format_and_template_preferences(admin: APIClient) -> None:
    Preference.objects.create(key="download.format", value="flac")
    Preference.objects.create(key="download.name_template", value="{title}")
    track = TrackFactory(title="Song")
    admin.post(_url(track.pk), {"file": _file()}, format="multipart")
    download = Download.objects.get(track=track)
    assert download.audio_format == "flac"
    assert Path(download.file_path).name == "Song.flac"


@pytest.mark.parametrize(
    "file",
    [
        pytest.param(lambda: _file("notas.txt", b"hola"), id="extension"),
        pytest.param(lambda: _file("falso.mp3", b"no soy audio"), id="not-audio"),
    ],
)
def test_rejects_invalid_file(admin: APIClient, file: Any, fake_media: dict[str, Any]) -> None:
    track = TrackFactory()
    response = admin.post(_url(track.pk), {"file": file()}, format="multipart")
    assert response.status_code == 400
    assert "file" in response.data
    assert not Download.objects.exists()
    assert fake_media["converted"] == []


def test_rejects_too_large_file(admin: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(upload, "MAX_BYTES", 100)
    response = admin.post(_url(TrackFactory().pk), {"file": _file()}, format="multipart")
    assert response.status_code == 400
    assert "file" in response.data


def test_rejects_missing_file(admin: APIClient) -> None:
    response = admin.post(_url(TrackFactory().pk), {}, format="multipart")
    assert response.status_code == 400
    assert "file" in response.data


def test_conversion_failure_leaves_nothing(
    admin: APIClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Path:
        raise ConversionError("boom")

    monkeypatch.setattr(upload, "convert", broken)
    response = admin.post(_url(TrackFactory().pk), {"file": _file()}, format="multipart")
    assert response.status_code == 422
    assert "detail" in response.data
    assert not Download.objects.exists()
    assert not (tmp_path / "library").exists()
    assert not ActivityLog.objects.filter(action="catalog.track.uploaded").exists()


def test_unknown_track_is_404(admin: APIClient) -> None:
    assert admin.post(_url(999), {"file": _file()}, format="multipart").status_code == 404


def test_regular_user_cannot_upload(db: None) -> None:
    client = APIClient()
    client.force_login(make_user("pepe", USER_GROUP))
    track = TrackFactory()
    assert client.post(_url(track.pk), {"file": _file()}, format="multipart").status_code == 403
    assert not Download.objects.exists()


def test_anonymous_cannot_upload(db: None) -> None:
    track = TrackFactory()
    response = APIClient().post(_url(track.pk), {"file": _file()}, format="multipart")
    assert response.status_code in (401, 403)
