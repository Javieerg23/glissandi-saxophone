"""Configuración de la app ``jobs``. / ``jobs`` app configuration."""

import importlib
import pkgutil

from django.apps import AppConfig, apps


class JobsConfig(AppConfig):
    """Configuración de la app ``jobs``. / ``jobs`` app configuration."""

    name = "jobs"

    def ready(self) -> None:
        """Importa los módulos de ``<app>/tasks/`` para que se registren.

        Imports every ``<app>/tasks/`` module so its tasks register themselves.
        """
        for config in apps.get_app_configs():
            try:
                package = importlib.import_module(f"{config.name}.tasks")
            except ModuleNotFoundError as error:
                # Solo se ignora que falte el paquete; un fallo dentro de él debe verse.
                # Only a missing package is ignored; a failure inside one must surface.
                if error.name != f"{config.name}.tasks":
                    raise
                continue
            for module in pkgutil.iter_modules(package.__path__):
                importlib.import_module(f"{package.__name__}.{module.name}")
