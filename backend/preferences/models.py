"""Modelos de la app ``preferences``. / ``preferences`` app models."""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from simple_history.models import HistoricalRecords

from .defaults import DEFAULTS


class Preference(models.Model):
    """Ajuste de la aplicación guardado como JSON. / Application setting stored as JSON.

    Editable, so every change is kept in the history table. Only keys declared
    in ``DEFAULTS`` are accepted.
    """

    key = models.CharField(gettext_lazy("clave"), max_length=100, unique=True)
    value = models.JSONField(gettext_lazy("valor"), null=True)
    updated_at = models.DateTimeField(gettext_lazy("actualizada"), auto_now=True)

    history = HistoricalRecords()

    class Meta:
        """Orden por clave. / Ordered by key."""

        ordering = ["key"]

    def __str__(self) -> str:
        """Devuelve la clave. / Returns the key."""
        return self.key

    def clean(self) -> None:
        """Rechaza claves que no tienen valor por defecto. / Rejects undeclared keys.

        Raises:
            ValidationError: Si la clave no está en ``DEFAULTS``.
        """
        if self.key not in DEFAULTS:
            raise ValidationError({"key": _("Clave de preferencia desconocida.")})


def get_value(key: str) -> Any:
    """Devuelve el valor guardado o, si no hay fila, el valor por defecto.

    Returns the stored value, or the code default when no row exists. A stored
    ``null`` is a real value: the row exists, so the default is not used.

    Args:
        key: Clave declarada en ``DEFAULTS``.

    Returns:
        El valor guardado o el valor por defecto. / The stored or default value.

    Raises:
        KeyError: Si la clave no está declarada en ``DEFAULTS``.
    """
    if key not in DEFAULTS:
        raise KeyError(key)
    preference = Preference.objects.filter(key=key).first()
    return DEFAULTS[key] if preference is None else preference.value
