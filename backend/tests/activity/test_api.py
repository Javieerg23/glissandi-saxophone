"""Tests de la API de actividad y logs técnicos. / Activity and technical log API tests."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from django_db_logger.models import StatusLog
from rest_framework.test import APIClient

from accounts.roles import USER_GROUP
from activity.models import ActivityLog
from activity.services import log_activity
from core.models import AppendOnlyError
from tests.accounts.conftest import make_user

pytestmark = pytest.mark.django_db
ENTRIES = "/api/v1/activity/entries/"
LOGS = "/api/v1/activity/logs/"


def test_actividad_exige_sesion(api: APIClient) -> None:
    """Sin sesión no se ve el historial."""
    assert api.get(ENTRIES).status_code in (401, 403)


def test_actividad_se_lista_con_su_forma(api: APIClient, basic_user: User) -> None:
    """Cada entrada trae usuario, acción, objeto afectado y detalle."""
    api.force_login(basic_user)
    log_activity(basic_user, "catalog.artist.blocked", obj=basic_user, detail={"reason": "x"})

    row = api.get(ENTRIES).json()["results"][0]

    assert row["action"] == "catalog.artist.blocked"
    assert row["username"] == "pepe"
    assert row["object_type"] == "auth.user"
    assert row["object_id"] == str(basic_user.pk)
    assert row["detail"] == {"reason": "x"}


@pytest.fixture
def three_entries(basic_user: User) -> list[ActivityLog]:
    """Tres entradas; la primera tiene diez días. / Three entries; the first is ten days old."""
    other = make_user("ana", USER_GROUP)
    old = timezone.now() - timedelta(days=10)
    with patch("django.utils.timezone.now", return_value=old):
        first = log_activity(basic_user, "catalog.artist.blocked", obj=basic_user)
    return [
        first,
        log_activity(other, "catalog.album.edited"),
        log_activity(other, "watches.watch.created"),
    ]


@pytest.mark.parametrize(
    ("query", "expected_actions"),
    [
        ({"username": "ana"}, {"catalog.album.edited", "watches.watch.created"}),
        ({"action": "blocked"}, {"catalog.artist.blocked"}),
        ({"object_type": "auth.user"}, {"catalog.artist.blocked"}),
        (
            {"date_from": (timezone.now() - timedelta(days=5)).date().isoformat()},
            {"catalog.album.edited", "watches.watch.created"},
        ),
        (
            {"date_to": (timezone.now() - timedelta(days=5)).date().isoformat()},
            {"catalog.artist.blocked"},
        ),
    ],
)
def test_actividad_filtra(
    api: APIClient,
    basic_user: User,
    three_entries: list[ActivityLog],
    query: dict[str, str],
    expected_actions: set[str],
) -> None:
    """Los filtros de usuario, acción, objeto y fechas acotan la lista."""
    api.force_login(basic_user)

    rows = api.get(ENTRIES, query).json()["results"]

    assert {row["action"] for row in rows} == expected_actions


def test_actividad_filtra_por_usuario_id(
    api: APIClient, basic_user: User, three_entries: list[ActivityLog]
) -> None:
    """El filtro por id de usuario devuelve solo sus acciones."""
    api.force_login(basic_user)

    rows = api.get(ENTRIES, {"user": basic_user.pk}).json()["results"]

    assert [row["action"] for row in rows] == ["catalog.artist.blocked"]


def test_actividad_rechaza_fecha_invalida(api: APIClient, basic_user: User) -> None:
    """Una fecha mal formada da 400."""
    api.force_login(basic_user)

    assert api.get(ENTRIES, {"date_from": "ayer"}).status_code == 400


def test_actividad_no_se_modifica_ni_borra(
    api: APIClient, basic_user: User, three_entries: list[ActivityLog]
) -> None:
    """La API de actividad es de solo lectura."""
    api.force_login(basic_user)
    url = f"{ENTRIES}{three_entries[0].pk}/"

    assert api.delete(url).status_code == 405
    assert api.patch(url, {"action": "x"}, format="json").status_code == 405
    with pytest.raises(AppendOnlyError):
        three_entries[0].delete()


def test_logs_tecnicos_solo_para_administradores(api: APIClient, basic_user: User) -> None:
    """Un usuario normal no ve los logs técnicos."""
    api.force_login(basic_user)

    assert api.get(LOGS).status_code == 403


def test_logs_tecnicos_filtros_y_busqueda(api: APIClient, admin_user: User) -> None:
    """Nivel, módulo, texto, tarea y fecha acotan los logs técnicos."""
    StatusLog.objects.create(logger_name="jobs.runner", level=40, msg="[job 7] fallo de red")
    StatusLog.objects.create(logger_name="accounts", level=20, msg="[job 3] arranque")
    StatusLog.objects.create(logger_name="jobs.runner", level=30, msg="sin tarea")
    api.force_login(admin_user)

    def msgs(query: dict[str, str | int]) -> set[str]:
        return {row["msg"] for row in api.get(LOGS, query).json()["results"]}

    assert msgs({"min_level": 30}) == {"[job 7] fallo de red", "sin tarea"}
    assert msgs({"module": "accounts"}) == {"[job 3] arranque"}
    assert msgs({"search": "RED"}) == {"[job 7] fallo de red"}
    assert msgs({"task": 7}) == {"[job 7] fallo de red"}
    assert msgs({"date_from": timezone.now().date().isoformat()}) == {
        "[job 7] fallo de red",
        "[job 3] arranque",
        "sin tarea",
    }


def test_logs_tecnicos_no_se_modifican(api: APIClient, admin_user: User) -> None:
    """Los logs técnicos tampoco se editan ni se borran desde la API."""
    entry = StatusLog.objects.create(logger_name="x", level=20, msg="m")
    api.force_login(admin_user)
    url = f"{LOGS}{entry.pk}/"

    assert api.get(url).json()["msg"] == "m"
    assert api.delete(url).status_code == 405
    assert api.patch(url, {"msg": "n"}, format="json").status_code == 405
