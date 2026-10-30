"""Ajustes para la batería de tests. / Settings for the test suite."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-key")

from .base import *  # noqa: E402, F403

# Hashing rápido: la seguridad de las contraseñas no es lo que se prueba aquí.
# Fast hashing: password strength is not what these tests exercise.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# App con modelos de prueba (p. ej. para ``AppendOnlyModel``; sin migraciones) y el comando
# ``lintmigrations`` que usa la CI.
# App hosting test models (e.g. for ``AppendOnlyModel``; no migrations) and the
# ``lintmigrations`` command the CI runs.
INSTALLED_APPS = [*INSTALLED_APPS, "tests.testapp", "django_migration_linter"]  # noqa: F405

# El cliente de test habla HTTP; las cookies conservan su indicador Secure para comprobarlo.
# The test client speaks HTTP; cookies keep their Secure flag so it can be asserted.
SECURE_SSL_REDIRECT = False
