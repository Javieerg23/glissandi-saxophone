"""Ajustes de desarrollo local. / Local development settings."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-only-insecure-key")

from .base import *  # noqa: E402, F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Sin HTTPS en local: las cookies seguras y la redirección impedirían iniciar sesión.
# No HTTPS locally: secure cookies and the redirect would prevent logging in.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
