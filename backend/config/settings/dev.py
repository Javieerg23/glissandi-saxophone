"""Ajustes de desarrollo local. / Local development settings."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "dev-only-insecure-key")

from .base import *  # noqa: E402, F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
