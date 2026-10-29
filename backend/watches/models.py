"""Modelos de la app ``watches``. / ``watches`` app models."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from core.models import AppendOnlyModel


class Watch(models.Model):  # type: ignore[django-manager-missing]  # django-stubs no ve el manager heredado de AppendOnlyModel
    """Vigilancia de novedades: nombre y si está activa.

    New-release watch: its name and whether it is active. Editable, so every
    change is kept in the history table.
    """

    name = models.CharField(_("nombre"), max_length=120, unique=True)
    enabled = models.BooleanField(_("activa"), default=True)
    created_at = models.DateTimeField(_("creada"), auto_now_add=True)
    updated_at = models.DateTimeField(_("actualizada"), auto_now=True)

    history = HistoricalRecords()

    class Meta:
        """Orden alfabético por nombre. / Alphabetical by name."""

        ordering = ["name"]

    def __str__(self) -> str:
        """Devuelve el nombre. / Returns the name."""
        return self.name


class WatchRun(AppendOnlyModel):
    """Resultado de una comprobación de novedades.

    Outcome of one new-release check. Written once when the check finishes,
    so it can stay append-only: the row never has to change to show progress.
    """

    class Status(models.TextChoices):
        """Resultado final de la comprobación. / Final outcome of the check."""

        SUCCEEDED = "succeeded", _("correcta")
        FAILED = "failed", _("fallida")

    watch = models.ForeignKey(
        Watch, on_delete=models.PROTECT, related_name="runs", verbose_name=_("vigilancia")
    )
    started_at = models.DateTimeField(_("inicio"), default=timezone.now)
    finished_at = models.DateTimeField(_("fin"), default=timezone.now)
    status = models.CharField(_("estado"), max_length=10, choices=Status.choices)
    found = models.PositiveIntegerField(_("novedades encontradas"), default=0)
    detail = models.TextField(_("detalle"), blank=True)

    class Meta:
        """Las más recientes primero. / Most recent first."""

        ordering = ["-finished_at", "-id"]
