"""Ajustes para la batería de tests. / Settings for the test suite."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-key")

from .base import *  # noqa: E402, F403

# Hashing rápido: la seguridad de las contraseñas no es lo que se prueba aquí.
# Fast hashing: password strength is not what these tests exercise.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
