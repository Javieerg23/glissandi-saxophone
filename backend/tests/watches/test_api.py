"""Tests de la API de novedades. / New-release API tests."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from activity.models import ActivityLog
from watches.models import Watch, WatchRun

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
    assert ActivityLog.objects.filter(action="watches.created").exists()


def test_duplicate_name_is_rejected(client_logged: APIClient, watch: Watch) -> None:
    response = client_logged.post(URL, {"name": watch.name}, format="json")
    assert response.status_code == 400


def test_updates_enabled_flag(client_logged: APIClient, watch: Watch) -> None:
    response = client_logged.patch(f"{URL}{watch.pk}/", {"enabled": False}, format="json")
    assert response.json()["enabled"] is False
    assert ActivityLog.objects.filter(action="watches.updated").exists()


def test_deletes_a_watch_without_checks(client_logged: APIClient, watch: Watch) -> None:
    assert client_logged.delete(f"{URL}{watch.pk}/").status_code == 204
    assert not Watch.objects.exists()
    assert ActivityLog.objects.filter(action="watches.deleted").exists()


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
