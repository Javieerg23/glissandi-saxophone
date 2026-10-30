"""Ida y vuelta de las migraciones de cada app local. / Round trip of each local app's migrations.

Cada migración debe poder revertirse y volver a aplicarse: así se detectan operaciones sin
``reverse_code`` antes de que lleguen a producción.

Every migration must be reversible and re-appliable, so operations without a
``reverse_code`` are caught before they reach production.
"""

from pathlib import Path

import pytest
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

# Solo las apps propias: las de terceros no las mantenemos nosotros.
# Only our own apps: third-party apps are not maintained here.
LOCAL_APPS = sorted(
    config.label
    for config in apps.get_app_configs()
    if Path(config.path).is_relative_to(settings.BASE_DIR)
    and (Path(config.path) / "migrations").is_dir()
)


def _pending_migrations() -> list[str]:
    """Devuelve las migraciones sin aplicar. / Returns the migrations not yet applied."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return [f"{migration.app_label}.{migration.name}" for migration, _ in plan]


def _applied_apps() -> set[str]:
    """Devuelve las apps con alguna migración aplicada. / Returns apps with an applied migration."""
    return {app for app, _ in MigrationRecorder(connection).applied_migrations()}


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("app_label", LOCAL_APPS)
def test_ida_y_vuelta_de_cada_app(app_label: str) -> None:
    """Revierte la app a cero, comprueba que se ha revertido y la vuelve a aplicar.

    Reverts the app to zero, checks it was reverted, then applies it again. Se usa el
    comando ``migrate`` y no ``django_test_migrations.Migrator``: este último deja el
    estado de los modelos históricos de ``simple_history`` desincronizado para el resto
    de la suite.

    Uses the ``migrate`` command rather than ``django_test_migrations.Migrator``, which
    leaves the ``simple_history`` model state out of sync for the rest of the suite.
    """
    call_command("migrate", app_label, "zero", verbosity=0)
    assert app_label not in _applied_apps()

    call_command("migrate", verbosity=0)
    assert _pending_migrations() == []
    assert app_label in _applied_apps()
