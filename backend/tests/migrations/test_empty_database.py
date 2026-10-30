"""Arranque con la base de datos vacía. / Startup with an empty database."""

import pytest
from django.apps import apps
from django.contrib.auth.models import Group
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import Client
from django_test_migrations.contrib.pytest_plugin import MigratorFactory

from .test_round_trip import LOCAL_APPS


@pytest.mark.django_db(transaction=True)
def test_base_vacia_arranca_y_responde_health(
    migrator_factory: MigratorFactory, client: Client
) -> None:
    """Migrar desde cero deja solo los roles; el servicio responde.

    Migrating from scratch leaves only the role groups; the service still answers.
    """
    migrator = migrator_factory()
    loader = MigrationLoader(connection)
    migrator.apply_initial_migration(loader.graph.leaf_nodes())

    assert set(Group.objects.values_list("name", flat=True)) == {"administrador", "usuario"}
    for model in apps.get_models():
        if model._meta.app_label in LOCAL_APPS and model is not Group:
            assert model._base_manager.count() == 0, model._meta.label

    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
