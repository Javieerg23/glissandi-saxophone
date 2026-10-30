"""Gestión de usuarios por administradores. / Administrator user management tests."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP, role_of
from activity.models import ActivityLog

from .conftest import BASE, PASSWORD

pytestmark = pytest.mark.django_db
USERS = f"{BASE}/users/"


def test_usuario_normal_no_gestiona_usuarios(api: APIClient, basic_user: User) -> None:
    """Un usuario sin rol de administrador recibe 403 en todas las operaciones."""
    api.force_login(basic_user)

    assert api.get(USERS).status_code == 403
    assert api.post(USERS, {}, format="json").status_code == 403
    assert api.patch(f"{USERS}{basic_user.pk}/", {}, format="json").status_code == 403


def test_anonimo_no_gestiona_usuarios(api: APIClient) -> None:
    """Sin sesión la API responde 403."""
    assert api.get(USERS).status_code == 403


def test_administrador_lista_usuarios_con_rol(
    api: APIClient, admin_user: User, basic_user: User
) -> None:
    """La lista trae usuario, rol y estado, ordenada por nombre."""
    api.force_login(admin_user)

    body = api.get(USERS).json()

    assert [row["username"] for row in body] == ["admin", "pepe"]
    assert body[1] == {
        "id": basic_user.pk,
        "username": "pepe",
        "role": USER_GROUP,
        "is_active": True,
        "last_login": None,
        "date_joined": basic_user.date_joined.isoformat().replace("+00:00", "Z"),
    }


def test_crear_usuario_con_rol_y_registro(api: APIClient, admin_user: User) -> None:
    """Crea el usuario, le asigna su grupo y deja constancia en la actividad."""
    api.force_login(admin_user)

    response = api.post(
        USERS, {"username": "ana", "password": PASSWORD, "role": ADMIN_GROUP}, format="json"
    )

    assert response.status_code == 201
    ana = User.objects.get(username="ana")
    assert role_of(ana) == ADMIN_GROUP
    assert ana.check_password(PASSWORD)
    entry = ActivityLog.objects.get(action="accounts.user.created")
    assert (entry.user, entry.target, entry.detail) == (admin_user, ana, {"role": ADMIN_GROUP})


def test_crear_usuario_por_defecto_es_normal(api: APIClient, admin_user: User) -> None:
    """Sin rol, el usuario nuevo es de la clase normal."""
    api.force_login(admin_user)

    api.post(USERS, {"username": "luis", "password": PASSWORD}, format="json")

    assert role_of(User.objects.get(username="luis")) == USER_GROUP


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"username": "pepe", "password": PASSWORD}, "username"),
        ({"username": "nueva", "password": "123"}, "password"),
        ({"username": "nueva", "password": PASSWORD, "role": "superusuario"}, "role"),
    ],
)
def test_crear_usuario_valida_entrada(
    api: APIClient, admin_user: User, basic_user: User, payload: dict[str, str], field: str
) -> None:
    """Nombre repetido, contraseña débil o rol desconocido dan 400 y no crean nada."""
    api.force_login(admin_user)

    response = api.post(USERS, payload, format="json")

    assert response.status_code == 400
    assert field in response.json()
    assert not User.objects.filter(username="nueva").exists()


def test_cambiar_rol_de_otro_usuario(api: APIClient, admin_user: User, basic_user: User) -> None:
    """El administrador puede subir a otro usuario al grupo administrador."""
    api.force_login(admin_user)

    response = api.patch(f"{USERS}{basic_user.pk}/", {"role": ADMIN_GROUP}, format="json")

    assert response.status_code == 200
    assert response.json()["role"] == ADMIN_GROUP
    assert role_of(basic_user) == ADMIN_GROUP
    assert ActivityLog.objects.filter(action="accounts.user.updated").count() == 1


def test_desactivar_usuario_cierra_su_sesion(
    api: APIClient, admin_user: User, basic_user: User
) -> None:
    """Un usuario desactivado no puede volver a entrar y pierde la sesión abierta."""
    other = APIClient()
    other.force_login(basic_user)
    api.force_login(admin_user)

    response = api.patch(f"{USERS}{basic_user.pk}/", {"is_active": False}, format="json")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert other.get(f"{BASE}/me/").status_code == 403
    assert api.post(f"{BASE}/login/", {"username": "pepe", "password": PASSWORD}).status_code == 400


@pytest.mark.parametrize("payload", [{"is_active": False}, {"role": USER_GROUP}])
def test_administrador_no_se_desactiva_ni_se_degrada(
    api: APIClient, admin_user: User, payload: dict[str, object]
) -> None:
    """Nadie se quita a sí mismo el acceso de administrador."""
    api.force_login(admin_user)

    response = api.patch(f"{USERS}{admin_user.pk}/", payload, format="json")

    assert response.status_code == 400
    admin_user.refresh_from_db()
    assert admin_user.is_active and role_of(admin_user) == ADMIN_GROUP


def test_administrador_puede_reafirmar_su_rol(api: APIClient, admin_user: User) -> None:
    """Enviar el mismo rol de administrador a uno mismo no es una degradación."""
    api.force_login(admin_user)

    response = api.patch(f"{USERS}{admin_user.pk}/", {"role": ADMIN_GROUP}, format="json")

    assert response.status_code == 200


def test_no_hay_borrado_de_usuarios(api: APIClient, admin_user: User, basic_user: User) -> None:
    """La API no ofrece borrar ni reemplazar usuarios."""
    api.force_login(admin_user)

    assert api.delete(f"{USERS}{basic_user.pk}/").status_code == 405
    assert api.put(f"{USERS}{basic_user.pk}/", {}, format="json").status_code == 405
    assert User.objects.filter(pk=basic_user.pk).exists()
