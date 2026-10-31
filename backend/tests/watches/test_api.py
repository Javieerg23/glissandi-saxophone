"""Tests de la API de novedades. / New-release API tests."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from activity.models import ActivityLog
from catalog.models import Artist
from watches.models import Watch, WatchArtist, WatchRun

pytestmark = pytest.mark.django_db

URL = "/api/v1/watches/"


@pytest.fixture
def client_logged() -> APIClient:
    user = User.objects.create_user("pepe", password="una-clave-larga-y-rara-9")
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def watch() -> Watch:
    return Watch.objects.create(name="Novedades de Rosalía")


def test_anonymous_is_forbidden() -> None:
    assert APIClient().get(URL).status_code == 403


def test_creates_lists_and_logs(client_logged: APIClient) -> None:
    response = client_logged.post(URL, {"name": "Novedades"}, format="json")
    assert response.status_code == 201
    assert response.json()["enabled"] is True
    assert client_logged.get(URL).json()["results"][0]["name"] == "Novedades"
    assert ActivityLog.objects.filter(
        action="watches.created", username="pepe", object_id=str(response.json()["id"])
    ).exists()


def test_duplicate_name_is_rejected(client_logged: APIClient, watch: Watch) -> None:
    response = client_logged.post(URL, {"name": watch.name}, format="json")
    assert response.status_code == 400


def test_updates_enabled_flag(client_logged: APIClient, watch: Watch) -> None:
    response = client_logged.patch(f"{URL}{watch.pk}/", {"enabled": False}, format="json")
    assert response.json()["enabled"] is False
    assert ActivityLog.objects.filter(
        action="watches.updated", username="pepe", object_id=str(watch.pk)
    ).exists()


def test_deletes_a_watch_without_checks(client_logged: APIClient, watch: Watch) -> None:
    assert client_logged.delete(f"{URL}{watch.pk}/").status_code == 204
    assert not Watch.objects.exists()
    assert ActivityLog.objects.filter(
        action="watches.deleted", username="pepe", object_id=str(watch.pk)
    ).exists()


def test_refuses_to_delete_a_watch_with_checks(client_logged: APIClient, watch: Watch) -> None:
    WatchRun.objects.create(watch=watch, status=WatchRun.Status.SUCCEEDED)
    response = client_logged.delete(f"{URL}{watch.pk}/")
    assert response.status_code == 409
    assert Watch.objects.filter(pk=watch.pk).exists()
    # La transacción deshace el registro de la baja rechazada.
    # The transaction rolls back the log row of the refused delete.
    assert not ActivityLog.objects.filter(action="watches.deleted").exists()


def test_runs_are_listed_newest_first(client_logged: APIClient, watch: Watch) -> None:
    now = timezone.now()
    WatchRun.objects.create(
        watch=watch,
        status=WatchRun.Status.SUCCEEDED,
        started_at=now - timedelta(hours=2),
        finished_at=now - timedelta(hours=2),
        found=1,
    )
    WatchRun.objects.create(
        watch=watch,
        status=WatchRun.Status.FAILED,
        started_at=now,
        finished_at=now,
        detail="Deezer no responde",
    )
    results = client_logged.get(f"{URL}{watch.pk}/runs/").json()["results"]
    assert [row["status"] for row in results] == ["failed", "succeeded"]
    assert results[0]["detail"] == "Deezer no responde"


def test_runs_of_unknown_watch_is_404(client_logged: APIClient) -> None:
    assert client_logged.get(f"{URL}999/runs/").status_code == 404


def test_creates_with_ordered_artists_and_settings(client_logged: APIClient) -> None:
    second, first = Artist.objects.create(name="B"), Artist.objects.create(name="A")
    body = {
        "name": "Novedades",
        "artist_ids": [first.pk, second.pk],
        "interval_hours": 6,
        "auto_download": True,
    }
    data = client_logged.post(URL, body, format="json").json()
    assert [(a["id"], a["name"]) for a in data["artists"]] == [(first.pk, "A"), (second.pk, "B")]
    assert (data["interval_hours"], data["auto_download"]) == (6, True)
    assert "artist_ids" not in data


def test_replaces_artists_in_new_order(client_logged: APIClient, watch: Watch) -> None:
    a, b = Artist.objects.create(name="A"), Artist.objects.create(name="B")
    client_logged.patch(f"{URL}{watch.pk}/", {"artist_ids": [a.pk, b.pk]}, format="json")
    response = client_logged.patch(f"{URL}{watch.pk}/", {"artist_ids": [b.pk]}, format="json")
    assert [x["name"] for x in response.json()["artists"]] == ["B"]


def test_patch_without_artist_ids_keeps_artists(client_logged: APIClient, watch: Watch) -> None:
    artist = Artist.objects.create(name="A")
    WatchArtist.objects.create(watch=watch, artist=artist)
    response = client_logged.patch(f"{URL}{watch.pk}/", {"enabled": False}, format="json")
    assert [x["id"] for x in response.json()["artists"]] == [artist.pk]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"artist_ids": [999]}, "artist_ids"),
        ({"interval_hours": 0}, "interval_hours"),
    ],
)
def test_rejects_invalid_fields(
    client_logged: APIClient, body: dict[str, object], field: str
) -> None:
    response = client_logged.post(URL, {"name": "N", **body}, format="json")
    assert response.status_code == 400
    assert list(response.json()) == [field]


def test_rejects_repeated_artists(client_logged: APIClient) -> None:
    artist = Artist.objects.create(name="A")
    body = {"name": "N", "artist_ids": [artist.pk, artist.pk]}
    response = client_logged.post(URL, body, format="json")
    assert list(response.json()) == ["artist_ids"]
