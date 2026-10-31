"""Tests de la API de proxies. / Proxy API tests."""

import pytest
import requests
import responses
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP
from activity.models import ActivityLog
from proxies.models import Proxy
from proxies.views import CHECK_URL

pytestmark = pytest.mark.django_db

URL = "/api/v1/proxies/"
PROXY = "http://127.0.0.1:8080"


def _login(role: str, username: str) -> APIClient:
    user = User.objects.create_user(username, password="una-clave-larga-y-rara-9")
    user.groups.add(Group.objects.get(name=role))
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def admin() -> APIClient:
    return _login(ADMIN_GROUP, "admin")


@pytest.fixture
def proxy() -> Proxy:
    return Proxy.objects.create(url=PROXY)


def test_regular_user_is_forbidden(proxy: Proxy) -> None:
    client = _login(USER_GROUP, "pepe")
    assert client.get(URL).status_code == 403
    assert client.get(f"{URL}{proxy.pk}/").status_code == 403


def test_anonymous_is_forbidden() -> None:
    assert APIClient().get(URL).status_code == 403


def test_admin_creates_and_lists_proxies(admin: APIClient) -> None:
    response = admin.post(URL, {"url": PROXY}, format="json")
    assert response.status_code == 201
    assert admin.get(URL).json()[0]["url"] == PROXY
    assert ActivityLog.objects.filter(
        action="proxies.created", username="admin", object_id=str(response.json()["id"])
    ).exists()


def test_counters_are_read_only(admin: APIClient) -> None:
    response = admin.post(URL, {"url": PROXY, "success_count": 99}, format="json")
    assert response.json()["success_count"] == 0


@pytest.mark.parametrize("url", ["ftp://host:21", "http://", "no-es-una-url"])
def test_rejects_invalid_urls(admin: APIClient, url: str) -> None:
    assert admin.post(URL, {"url": url}, format="json").status_code == 400


def test_admin_updates_and_deletes(admin: APIClient, proxy: Proxy) -> None:
    response = admin.patch(f"{URL}{proxy.pk}/", {"enabled": False}, format="json")
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert admin.delete(f"{URL}{proxy.pk}/").status_code == 204
    assert not Proxy.objects.exists()
    for action in ("proxies.updated", "proxies.deleted"):
        assert ActivityLog.objects.filter(
            action=action, username="admin", object_id=str(proxy.pk)
        ).exists()


@responses.activate
def test_check_reports_success(admin: APIClient, proxy: Proxy) -> None:
    responses.get(CHECK_URL, status=200)
    response = admin.post(f"{URL}{proxy.pk}/check/")
    assert response.json() == {"ok": True, "status_code": 200}
    assert ActivityLog.objects.filter(action="proxies.checked").exists()


@responses.activate
def test_check_reports_an_error_status(admin: APIClient, proxy: Proxy) -> None:
    responses.get(CHECK_URL, status=403)
    response = admin.post(f"{URL}{proxy.pk}/check/")
    assert response.json() == {"ok": False, "status_code": 403}


@responses.activate
def test_check_hides_connection_errors(admin: APIClient, proxy: Proxy) -> None:
    # El texto del error puede llevar la URL del proxy con credenciales: no se devuelve.
    # The error text may carry the proxy URL with credentials: it is never returned.
    responses.get(CHECK_URL, body=requests.ConnectionError(f"{PROXY} refused"))
    response = admin.post(f"{URL}{proxy.pk}/check/")
    assert response.json() == {"ok": False, "status_code": None}
    assert PROXY not in response.content.decode()


def test_check_unknown_proxy_is_404(admin: APIClient) -> None:
    assert admin.post(f"{URL}999/check/").status_code == 404
