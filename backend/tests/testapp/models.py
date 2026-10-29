"""Modelos de prueba. / Test models."""

from django.db import models

from core.models import AppendOnlyModel


class Entry(AppendOnlyModel):
    """Registro mínimo de solo añadir. / Minimal append-only record."""

    text = models.CharField(max_length=20)

    class Meta:
        """Etiqueta propia para no chocar con apps reales. / Own label to avoid clashes."""

        app_label = "testapp"
