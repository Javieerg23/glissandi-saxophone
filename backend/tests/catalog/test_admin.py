"""Tests de la administración y las migraciones del catálogo. / Admin and migration tests."""

import pytest
from django.contrib import admin
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory

from catalog.models import Download


def test_download_admin_is_read_only() -> None:
    model_admin = admin.site._registry[Download]
    request = RequestFactory().get("/")
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)


@pytest.mark.django_db(transaction=True)
def test_initial_migration_is_reversible() -> None:
    executor = MigrationExecutor(connection)
    executor.migrate([("catalog", None)])
    assert "catalog_track" not in connection.introspection.table_names()
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes("catalog"))
    assert "catalog_track" in connection.introspection.table_names()
