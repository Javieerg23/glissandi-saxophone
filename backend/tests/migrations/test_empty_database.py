"""Arranque con la base de datos vacía. / Startup with an empty database."""

import pytest
from django.apps import apps
from django.test import Client

from .test_round_trip import LOCAL_APPS


@pytest.mark.django_db(transaction=True)
def test_base_recien_migrada_no_tiene_contenido_y_responde_health(client: Client) -> None:
    """Las tablas propias empiezan vacías y el servicio responde.

    Our tables start empty and the service still answers. Las tablas se comprueban aquí
    porque ``transaction=True`` borra todo al terminar cada test, roles incluidos.

    The tables are checked here because ``transaction=True`` flushes everything, role
    groups included, when each test finishes.
    """
    for model in apps.get_models():
        if model._meta.app_label in LOCAL_APPS:
            assert model._base_manager.count() == 0, model._meta.label

    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
