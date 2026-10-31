"""Tests de la API de ajustes. / Settings API tests."""

from collections.abc import Iterator

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP
from activity.models import ActivityLog
from preferences.defaults import DEFAULTS
from preferences.models import Preference

pytestmark = pytest.mark.django_db

URL = "/api/v1/preferences/"


@pytest.fixture
def declared(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Declara dos ajustes de prueba. / Declares two test settings."""
    monkeypatch.setitem(DEFAULTS, "demo.flag", True)
    monkeypatch.setitem(DEFAULTS, "demo.count", 3)
    yield


def _login(role: str, username: str) -> APIClient:
    user = User.objects.create_user(username, password="una-clave-larga-y-rara-9")
    user.groups.add(Group.objects.get(name=role))
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def admin() -> APIClient:
    return _login(ADMIN_GROUP, "admin")


def test_regular_user_is_forbidden(declared: None) -> None:
    client = _login(USER_GROUP, "pepe")
    assert client.get(URL).status_code == 403
    assert client.get(f"{URL}demo.flag/").status_code == 403


def test_anonymous_is_forbidden(declared: None) -> None:
    assert APIClient().get(URL).status_code == 403


def test_list_shows_defaults_until_overridden(admin: APIClient, declared: None) -> None:
    rows = {row["key"]: row for row in admin.get(URL).json()}
    assert rows["demo.flag"] == {"key": "demo.flag", "value": True, "default": True}
    assert rows["demo.count"]["value"] == 3


def test_unknown_key_is_404(admin: APIClient, declared: None) -> None:
    assert admin.get(f"{URL}no.existe/").status_code == 404
    assert admin.put(f"{URL}no.existe/", {"value": 1}, format="json").status_code == 404


def test_put_changes_value_and_logs_it(admin: APIClient, declared: None) -> None:
    response = admin.put(f"{URL}demo.count/", {"value": 7}, format="json")
    assert response.status_code == 200
    assert response.json()["value"] == 7
    assert admin.get(f"{URL}demo.count/").json()["value"] == 7
    assert ActivityLog.objects.filter(action="preferences.updated").exists()


def test_second_put_updates_the_same_row(admin: APIClient, declared: None) -> None:
    admin.put(f"{URL}demo.count/", {"value": 1}, format="json")
    admin.put(f"{URL}demo.count/", {"value": 2}, format="json")
    assert Preference.objects.filter(key="demo.count").count() == 1
    assert admin.get(f"{URL}demo.count/").json()["value"] == 2


@pytest.mark.parametrize(
    "value",
    ["siete", True, 1.5, None, [1]],
)
def test_put_rejects_a_different_type(admin: APIClient, declared: None, value: object) -> None:
    response = admin.put(f"{URL}demo.count/", {"value": value}, format="json")
    assert response.status_code == 400
    assert Preference.objects.filter(key="demo.count").count() == 0


def test_put_accepts_a_bool_for_a_bool_setting(admin: APIClient, declared: None) -> None:
    response = admin.put(f"{URL}demo.flag/", {"value": False}, format="json")
    assert response.status_code == 200
    assert response.json()["value"] is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("download.format", "wma"),
        ("download.name_template", "{artist}/{desconocido}"),
        ("download.name_template", "{artist"),
        ("download.name_template", "/"),
    ],
)
def test_put_rejects_values_downloads_cannot_use(admin: APIClient, key: str, value: str) -> None:
    """Un valor que haría fallar cada descarga se rechaza al guardarlo."""
    response = admin.put(f"{URL}{key}/", {"value": value}, format="json")
    assert response.status_code == 400
    assert not Preference.objects.filter(key=key).exists()


@pytest.mark.parametrize(
    ("key", "value"), [("download.format", "flac"), ("download.name_template", "{year}/{title}")]
)
def test_put_accepts_valid_download_values(admin: APIClient, key: str, value: str) -> None:
    assert admin.put(f"{URL}{key}/", {"value": value}, format="json").status_code == 200
