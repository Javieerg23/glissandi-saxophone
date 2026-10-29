"""Utilidades de los tests de cuentas. / Account test helpers."""

import pytest
from django.contrib.auth.models import Group, User
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP

PASSWORD = "una-clave-larga-y-rara-9"
BASE = "/api/v1/accounts"


@pytest.fixture
def api() -> APIClient:
    """Cliente de la API. / API client."""
    return APIClient()


def make_user(username: str, group: str) -> User:
    """Crea un usuario dentro de un grupo. / Creates a user inside a group."""
    user = User.objects.create_user(username, password=PASSWORD)
    user.groups.add(Group.objects.get(name=group))
    return user


@pytest.fixture
def admin_user(db: None) -> User:
    """Usuario administrador. / Administrator user."""
    return make_user("admin", ADMIN_GROUP)


@pytest.fixture
def basic_user(db: None) -> User:
    """Usuario normal. / Regular user."""
    return make_user("pepe", USER_GROUP)
