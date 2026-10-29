"""Tests de la configuración inicial. / Initial setup tests."""

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP, is_administrator

from .conftest import BASE, PASSWORD

pytestmark = pytest.mark.django_db


def test_los_grupos_existen_tras_migrar() -> None:
    """La migración crea los dos grupos. / The migration creates both groups."""
    assert set(Group.objects.values_list("name", flat=True)) >= {ADMIN_GROUP, USER_GROUP}


def test_estado_sin_usuarios_pide_configurar(api: APIClient) -> None:
    """Sin usuarios hay que configurar, y la respuesta entrega la cookie CSRF."""
    response = api.get(f"{BASE}/setup/")

    assert response.json() == {"needed": True}
    assert "csrftoken" in response.cookies


def test_estado_con_usuarios_no_pide_configurar(api: APIClient, admin_user: User) -> None:
    """Con algún usuario la configuración queda cerrada."""
    assert api.get(f"{BASE}/setup/").json() == {"needed": False}


def test_crea_el_primer_administrador(api: APIClient) -> None:
    """El primer usuario es administrador y superusuario, y queda con sesión."""
    response = api.post(f"{BASE}/setup/", {"username": "root", "password": PASSWORD})

    assert response.status_code == 201
    user = User.objects.get(username="root")
    assert user.is_superuser and user.is_staff
    assert is_administrator(user)
    assert api.get(f"{BASE}/me/").status_code == 200


def test_rechaza_clave_debil(api: APIClient) -> None:
    """Los validadores de contraseña de Django se aplican."""
    response = api.post(f"{BASE}/setup/", {"username": "root", "password": "1234"})

    assert response.status_code == 400
    assert not User.objects.exists()


def test_no_se_puede_configurar_dos_veces(api: APIClient, admin_user: User) -> None:
    """Con usuarios existentes el POST se rechaza sin crear nada."""
    response = api.post(f"{BASE}/setup/", {"username": "otro", "password": PASSWORD})

    assert response.status_code == 403
    assert User.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_la_migracion_de_grupos_es_reversible() -> None:
    """Deshacer la migración borra los grupos y rehacerla los recrea."""
    call_command("migrate", "accounts", "zero", verbosity=0)
    assert not Group.objects.filter(name__in=[ADMIN_GROUP, USER_GROUP]).exists()

    call_command("migrate", "accounts", verbosity=0)
    assert Group.objects.filter(name__in=[ADMIN_GROUP, USER_GROUP]).count() == 2
