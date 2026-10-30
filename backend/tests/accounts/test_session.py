"""Tests de login, logout, perfil y credenciales. / Login, logout, profile, credentials."""

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP

from .conftest import BASE, PASSWORD

pytestmark = pytest.mark.django_db


def test_login_correcto_abre_sesion(api: APIClient, basic_user: User) -> None:
    """Con credenciales válidas se abre la sesión y se devuelve el perfil."""
    response = api.post(f"{BASE}/login/", {"username": "pepe", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"username": "pepe", "role": USER_GROUP}
    assert api.get(f"{BASE}/me/").status_code == 200


def test_login_incorrecto_no_distingue_usuario_de_clave(api: APIClient, basic_user: User) -> None:
    """El error es el mismo con usuario inexistente o clave errónea."""
    bad_pass = api.post(f"{BASE}/login/", {"username": "pepe", "password": "x"})
    no_user = api.post(f"{BASE}/login/", {"username": "nadie", "password": "x"})

    assert bad_pass.status_code == no_user.status_code == 400
    assert bad_pass.json() == no_user.json()


def test_login_exige_csrf(basic_user: User) -> None:
    """Sin token CSRF el login se rechaza."""
    client = APIClient(enforce_csrf_checks=True)

    response = client.post(f"{BASE}/login/", {"username": "pepe", "password": PASSWORD})

    assert response.status_code == 403


def test_login_con_csrf_por_cabecera(basic_user: User) -> None:
    """El token se envía en la cabecera X-CSRFToken, como hará el frontend."""
    client = APIClient(enforce_csrf_checks=True)
    token = client.get(f"{BASE}/setup/").cookies["csrftoken"].value

    response = client.post(
        f"{BASE}/login/",
        {"username": "pepe", "password": PASSWORD},
        headers={"x-csrftoken": token},
    )

    assert response.status_code == 200


def test_axes_bloquea_tras_demasiados_fallos(api: APIClient, basic_user: User) -> None:
    """Tras los intentos permitidos, ni la clave correcta entra."""
    for _ in range(5):
        api.post(f"{BASE}/login/", {"username": "pepe", "password": "mala"})

    response = api.post(f"{BASE}/login/", {"username": "pepe", "password": PASSWORD})

    assert response.status_code == 429


def test_logout_cierra_sesion(api: APIClient, basic_user: User) -> None:
    """Tras el logout el perfil deja de estar disponible."""
    api.force_login(basic_user)

    assert api.post(f"{BASE}/logout/").status_code == 204
    assert api.get(f"{BASE}/me/").status_code == 403


def test_endpoints_privados_exigen_sesion(api: APIClient) -> None:
    """Sin sesión, todo lo que no es setup ni login queda cerrado."""
    assert api.get(f"{BASE}/me/").status_code == 403
    assert api.post(f"{BASE}/logout/").status_code == 403
    assert api.post(f"{BASE}/password/", {}).status_code == 403
    assert api.post(f"{BASE}/username/", {}).status_code == 403


def test_me_informa_del_rol(api: APIClient, admin_user: User) -> None:
    """El perfil incluye el rol, que el frontend usa para mostrar secciones."""
    api.force_login(admin_user)

    assert api.get(f"{BASE}/me/").json() == {
        "username": "admin",
        "role": ADMIN_GROUP,
        "failed_attempts": 0,
    }


def test_me_cuenta_los_fallos_desde_el_ultimo_acceso(api: APIClient, basic_user: User) -> None:
    """Los fallos se cuentan hasta el siguiente inicio de sesión correcto."""
    for _ in range(2):
        api.post(f"{BASE}/login/", {"username": "pepe", "password": "mala"})
    api.post(f"{BASE}/login/", {"username": "pepe", "password": PASSWORD})
    assert api.get(f"{BASE}/me/").json()["failed_attempts"] == 0

    api.post(f"{BASE}/login/", {"username": "pepe", "password": "mala"})
    assert api.get(f"{BASE}/me/").json()["failed_attempts"] == 1


def test_cambio_de_clave(api: APIClient, basic_user: User) -> None:
    """Cambiar la clave conserva la sesión y deja inservible la anterior."""
    api.force_login(basic_user)

    response = api.post(
        f"{BASE}/password/", {"current_password": PASSWORD, "new_password": "otra-clave-larga-77"}
    )

    assert response.status_code == 204
    assert api.get(f"{BASE}/me/").status_code == 200
    basic_user.refresh_from_db()
    assert basic_user.check_password("otra-clave-larga-77")


def test_cambio_de_clave_exige_la_actual(api: APIClient, basic_user: User) -> None:
    """Una sesión robada no basta para cambiar la clave."""
    api.force_login(basic_user)

    response = api.post(
        f"{BASE}/password/", {"current_password": "mala", "new_password": "otra-clave-larga-77"}
    )

    assert response.status_code == 400


def test_cambio_de_clave_valida_la_nueva(api: APIClient, basic_user: User) -> None:
    """La nueva clave pasa por los validadores."""
    api.force_login(basic_user)

    response = api.post(f"{BASE}/password/", {"current_password": PASSWORD, "new_password": "1234"})

    assert response.status_code == 400


def test_cambio_de_usuario(api: APIClient, basic_user: User) -> None:
    """Cambia el nombre de usuario con la clave actual."""
    api.force_login(basic_user)

    response = api.post(f"{BASE}/username/", {"current_password": PASSWORD, "username": "paco"})

    assert response.status_code == 200
    assert response.json()["username"] == "paco"
    basic_user.refresh_from_db()
    assert basic_user.username == "paco"


def test_cambio_de_usuario_exige_la_clave(api: APIClient, basic_user: User) -> None:
    """Sin la clave actual correcta no se renombra."""
    api.force_login(basic_user)

    response = api.post(f"{BASE}/username/", {"current_password": "mala", "username": "paco"})

    assert response.status_code == 400


def test_cambio_de_usuario_no_pisa_a_otro(
    api: APIClient, basic_user: User, admin_user: User
) -> None:
    """El nombre debe ser único."""
    api.force_login(basic_user)

    response = api.post(f"{BASE}/username/", {"current_password": PASSWORD, "username": "admin"})

    assert response.status_code == 400
