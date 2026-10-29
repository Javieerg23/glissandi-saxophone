"""Tests de los permisos por grupo. / Group permission tests."""

import pytest
from django.contrib.auth.models import AnonymousUser, User
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from accounts.permissions import IsAdministrator

pytestmark = pytest.mark.django_db


def _allowed(user: User | AnonymousUser) -> bool:
    request = Request(APIRequestFactory().get("/"))
    request.user = user
    return IsAdministrator().has_permission(request, None)  # type: ignore[arg-type]


def test_administrador_permitido(admin_user: User) -> None:
    """Los miembros del grupo administrador pasan."""
    assert _allowed(admin_user)


def test_usuario_normal_denegado(basic_user: User) -> None:
    """Los miembros del grupo usuario no pasan."""
    assert not _allowed(basic_user)


def test_anonimo_denegado() -> None:
    """Sin sesión no pasa nadie."""
    assert not _allowed(AnonymousUser())
