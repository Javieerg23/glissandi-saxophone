"""Configuración de la app ``core``. / ``core`` app configuration."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """App con los endpoints transversales (estado del servicio)."""

    name = "core"
