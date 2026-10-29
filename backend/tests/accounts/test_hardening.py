"""Tests del endurecimiento HTTP. / HTTP hardening tests."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from rest_framework.test import APIClient

from .conftest import BASE, PASSWORD

BACKEND = Path(__file__).resolve().parents[2]


def _script_src(response_header: str) -> list[str]:
    directives = {d.split()[0]: d.split()[1:] for d in response_header.split(";") if d.strip()}
    return directives["script-src"]


def test_csp_de_scripts_sin_inline_ni_eval(client: Client) -> None:
    """La CSP se envía y no relaja los scripts."""
    header = client.get("/api/health/")["Content-Security-Policy"]

    assert "'unsafe-inline'" not in _script_src(header)
    assert "'unsafe-eval'" not in _script_src(header)
    assert "'self'" in _script_src(header)


def test_cabeceras_de_seguridad(client: Client) -> None:
    """X-Frame-Options y HSTS (solo sobre HTTPS) están presentes."""
    response = client.get("/api/health/", secure=True)

    assert response["X-Frame-Options"] == "DENY"
    assert "max-age=" in response["Strict-Transport-Security"]
    assert "Strict-Transport-Security" not in client.get("/api/health/")


@pytest.mark.django_db
def test_cookie_de_sesion_segura(basic_user: User) -> None:
    """La cookie de sesión es HttpOnly, Secure, SameSite y caduca."""
    api = APIClient()
    response = api.post(f"{BASE}/login/", {"username": "pepe", "password": PASSWORD})
    cookie = response.cookies[settings.SESSION_COOKIE_NAME]

    assert cookie["httponly"] and cookie["secure"]
    assert cookie["samesite"] == "Lax"
    assert cookie["max-age"] == settings.SESSION_COOKIE_AGE


def test_check_deploy_sin_avisos() -> None:
    """Con los ajustes base (los de producción) ``check --deploy`` no avisa de nada."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.base",
        "DJANGO_SECRET_KEY": "x7#k9Qz" * 10,
        "DJANGO_ALLOWED_HOSTS": "glissandi.example.org",
    }
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "manage.py",
            "check",
            "--deploy",
            "--tag",
            "security",
            "--fail-level",
            "WARNING",
        ],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
