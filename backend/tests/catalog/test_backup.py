"""Tests de la copia de la biblioteca en JSON. / Tests for the JSON library backup."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import QuerySet
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP
from activity.models import ActivityLog
from catalog.backup import LIBRARY_MODELS, UPLOAD_PREFIX, BackupError, upload_path
from catalog.factories import ArtistFactory, DownloadFactory, TrackArtistFactory, TrackFactory
from catalog.models import Artist, BlockedItem, Download, Track
from jobs import runner
from jobs.models import JobRun
from tests.accounts.conftest import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/catalog/backup"


@pytest.fixture(autouse=True)
def upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Carpeta temporal propia para ver qué ficheros quedan. / Own temp dir to see leftovers."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


@pytest.fixture
def admin_user(db: None) -> User:
    """Administrador. / Administrator."""
    return make_user("admin", ADMIN_GROUP)


@pytest.fixture
def admin(admin_user: User) -> APIClient:
    """Cliente con sesión de administrador. / Administrator client."""
    client = APIClient()
    client.force_login(admin_user)
    return client


@pytest.fixture
def user(db: None) -> APIClient:
    """Cliente con sesión de usuario normal. / Regular user client."""
    client = APIClient()
    client.force_login(make_user("pepe", USER_GROUP))
    return client


def _library() -> None:
    """Biblioteca con todos los tipos de fila. / Library holding every kind of row."""
    track = TrackFactory()
    TrackArtistFactory(track=track, position=1)
    DownloadFactory(track=track)
    TrackFactory(album=track.album)
    BlockedItem.objects.create(kind=BlockedItem.Kind.ALBUM, deezer_id=7, name="Malo")


def _export(client: APIClient) -> list[dict[str, Any]]:
    response = client.get(f"{BASE}/")
    assert response.status_code == 200
    return json.loads(response.content)  # type: ignore[no-any-return]


def _file(entries: Any, raw: bytes | None = None) -> SimpleUploadedFile:
    content = raw if raw is not None else json.dumps(entries).encode()
    return SimpleUploadedFile("biblioteca.json", content, content_type="application/json")


def _empty_library() -> None:
    """Vacía las tablas, también las de solo añadir. / Empties the tables, append-only ones too."""
    for label in reversed(LIBRARY_MODELS):
        QuerySet(apps.get_model(label))._raw_delete("default")


def _restore(client: APIClient, entries: Any) -> Any:
    return client.post(f"{BASE}/restore/", {"file": _file(entries)}, format="multipart")


# --- Permisos / Permissions ---


def test_anonymous_is_rejected() -> None:
    client = APIClient()
    assert client.get(f"{BASE}/").status_code in (401, 403)
    assert client.post(f"{BASE}/preview/").status_code in (401, 403)
    assert client.post(f"{BASE}/restore/").status_code in (401, 403)


def test_regular_user_is_rejected(user: APIClient) -> None:
    assert user.get(f"{BASE}/").status_code == 403
    assert user.post(f"{BASE}/preview/", {"file": _file([])}, format="multipart").status_code == 403
    assert _restore(user, []).status_code == 403


def test_task_refuses_non_administrators(upload_dir: Path) -> None:
    (upload_dir / f"{UPLOAD_PREFIX}x.json").write_text("[]")
    for who in (make_user("pepe", USER_GROUP), None):
        run = runner.start("library_restore", {"file": f"{UPLOAD_PREFIX}x.json"}, who)
        assert run.status == JobRun.Status.FAILED


# --- Exportar / Export ---


def test_export_is_a_json_attachment_without_history(admin: APIClient) -> None:
    _library()
    response = admin.get(f"{BASE}/")
    assert response["Content-Type"] == "application/json"
    assert response["Content-Disposition"].startswith('attachment; filename="glissandi-')
    models = {entry["model"] for entry in _export(admin)}
    assert models == set(LIBRARY_MODELS)


# --- Vista previa / Preview ---


def test_preview_counts_total_and_existing(admin: APIClient) -> None:
    _library()
    entries = _export(admin)
    entries.append({"model": "catalog.artist", "pk": 999, "fields": {"name": "Nuevo"}})
    response = admin.post(f"{BASE}/preview/", {"file": _file(entries)}, format="multipart")
    assert response.status_code == 200
    assert response.data == {
        "artists": {"total": Artist.objects.count() + 1, "existing": Artist.objects.count()},
        "albums": {"total": 1, "existing": 1},
        "tracks": {"total": 2, "existing": 2},
        "downloads": {"total": 1, "existing": 1},
    }


@pytest.mark.parametrize(
    ("entries", "raw"),
    [
        (None, b"{no es json"),
        ({"model": "catalog.artist"}, None),
        ([{"model": "auth.user", "pk": 1, "fields": {"username": "x"}}], None),
        (["catalog.artist"], None),
        ([{"model": "catalog.artist", "pk": 1}], None),
        ([{"model": "catalog.artist", "pk": 1, "fields": {"nope": 1}}], None),
        ([{"model": "catalog.track", "pk": 1, "fields": {"duration": "abc"}}], None),
    ],
    ids=["not-json", "not-list", "foreign-model", "not-object", "no-fields", "bad-field", "bad"],
)
def test_invalid_files_are_rejected(
    admin: APIClient, upload_dir: Path, entries: Any, raw: bytes | None
) -> None:
    for path in ("preview", "restore"):
        response = admin.post(f"{BASE}/{path}/", {"file": _file(entries, raw)}, format="multipart")
        assert response.status_code == 400
        assert response.data["detail"]
    assert not JobRun.objects.exists()
    assert not list(upload_dir.iterdir())


def test_missing_file_is_rejected(admin: APIClient) -> None:
    assert admin.post(f"{BASE}/preview/", {}, format="multipart").status_code == 400


# --- Importar / Restore ---


def test_round_trip_restores_the_same_library(admin: APIClient, upload_dir: Path) -> None:
    _library()
    exported = _export(admin)
    _empty_library()
    assert not Track.objects.exists()

    response = _restore(admin, exported)

    assert response.status_code == 201
    run = JobRun.objects.get(pk=response.data["id"])
    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary == {"created": len(exported), "skipped": 0}
    assert _export(admin) == exported
    assert not list(upload_dir.iterdir())
    # Las secuencias siguen detrás de los ids restaurados. / Sequences stay past restored ids.
    assert ArtistFactory().pk > max(e["pk"] for e in exported if e["model"] == "catalog.artist")
    assert ActivityLog.objects.filter(action="catalog.library.restore_started").exists()


def test_restore_never_rewrites_existing_rows(admin: APIClient) -> None:
    _library()
    exported = _export(admin)
    Artist.objects.filter(pk=exported[0]["pk"]).update(name="Cambiado")
    BlockedItem.objects.all().delete()

    run = JobRun.objects.get(pk=_restore(admin, exported).data["id"])

    assert run.summary == {"created": 1, "skipped": len(exported) - 1}
    assert Artist.objects.get(pk=exported[0]["pk"]).name == "Cambiado"
    assert BlockedItem.objects.count() == 1
    assert Download.objects.count() == 1


def test_restore_with_nothing_new_loads_nothing(admin: APIClient) -> None:
    _library()
    run = JobRun.objects.get(pk=_restore(admin, _export(admin)).data["id"])
    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary["created"] == 0


def test_restore_while_another_runs_is_a_conflict(admin: APIClient, upload_dir: Path) -> None:
    JobRun.objects.create(kind="library_restore", status=JobRun.Status.RUNNING)
    assert _restore(admin, []).status_code == 409
    assert not list(upload_dir.iterdir())


@pytest.mark.parametrize("name", [None, "../x.json", "otro.json", f"sub/{UPLOAD_PREFIX}x.json"])
def test_task_rejects_files_outside_its_uploads(admin_user: User, name: Any) -> None:
    run = runner.start("library_restore", {"file": name}, admin_user)
    assert run.status == JobRun.Status.FAILED


@pytest.mark.parametrize(
    "name", [5, "otro.json", f"{UPLOAD_PREFIX}x/../../etc/passwd", f"/var/{UPLOAD_PREFIX}x.json"]
)
def test_upload_path_only_accepts_upload_names(name: object) -> None:
    """La tarea solo abre ficheros de la carpeta temporal con el prefijo de subida."""
    with pytest.raises(BackupError):
        upload_path(name)


def test_upload_path_stays_in_the_temp_folder() -> None:
    name = f"{UPLOAD_PREFIX}abc.json"
    assert upload_path(name) == Path(tempfile.gettempdir()) / name
