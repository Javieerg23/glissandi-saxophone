"""Modelos de la app ``jobs``. / ``jobs`` app models."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import AppendOnlyError, AppendOnlyModel


class JobRun(models.Model):
    """Ejecución de una tarea en segundo plano.

    One run of a background task. It is edited while it reports progress and
    sealed when ``finished_at`` is set: a closed run is history.
    """

    class Status(models.TextChoices):
        """Ciclo de vida de la ejecución. / Lifecycle of the run."""

        PENDING = "pending", _("pendiente")
        RUNNING = "running", _("en curso")
        STOPPING = "stopping", _("deteniéndose")
        STOPPED = "stopped", _("detenida")
        SUCCEEDED = "succeeded", _("correcta")
        FAILED = "failed", _("fallida")
        INTERRUPTED = "interrupted", _("interrumpida")

    #: Estados en los que la tarea aún ocupa su tipo. / States where the run still holds its kind.
    ACTIVE = (Status.PENDING, Status.RUNNING, Status.STOPPING)

    kind = models.CharField(_("tipo"), max_length=50, db_index=True)
    params = models.JSONField(_("parámetros"), default=dict, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="job_runs",
        verbose_name=_("usuario"),
    )
    status = models.CharField(
        _("estado"), max_length=11, choices=Status.choices, default=Status.PENDING
    )
    started_at = models.DateTimeField(_("inicio"), default=timezone.now)
    finished_at = models.DateTimeField(_("fin"), null=True, blank=True)
    done = models.PositiveIntegerField(_("hechas"), default=0)
    total = models.PositiveIntegerField(_("total"), default=0)
    current = models.CharField(_("elemento actual"), max_length=255, blank=True)
    summary = models.JSONField(_("resumen"), default=dict, blank=True)

    class Meta:
        """Las más recientes primero. / Most recent first."""

        ordering = ["-started_at", "-id"]

    def __str__(self) -> str:
        """Devuelve tipo e identificador. / Returns kind and id."""
        return f"{self.kind} #{self.pk}"

    @property
    def is_closed(self) -> bool:
        """Indica si la ejecución ya terminó. / Whether the run has ended."""
        return self.finished_at is not None

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Guarda solo mientras la fila en base de datos siga abierta.

        Saves only while the stored row is still open. The check reads the
        database, not ``self``, so a stale copy cannot reopen a closed run.
        """
        if (
            not self._state.adding
            and JobRun.objects.filter(pk=self.pk, finished_at__isnull=False).exists()
        ):
            raise AppendOnlyError("Una ejecución cerrada no se modifica.")
        super().save(*args, **kwargs)


class JobRunLine(AppendOnlyModel):
    """Línea del registro de una ejecución. / One log line of a run."""

    class Level(models.TextChoices):
        """Gravedad de la línea. / Severity of the line."""

        INFO = "info", _("información")
        WARNING = "warning", _("aviso")
        ERROR = "error", _("error")

    run = models.ForeignKey(
        JobRun, on_delete=models.PROTECT, related_name="lines", verbose_name=_("ejecución")
    )
    position = models.PositiveIntegerField(_("posición"))
    level = models.CharField(_("nivel"), max_length=7, choices=Level.choices, default=Level.INFO)
    message = models.TextField(_("mensaje"))
    created_at = models.DateTimeField(_("fecha"), default=timezone.now)

    class Meta:
        """Orden de escritura. / Write order."""

        ordering = ["run_id", "position"]
        constraints = [
            models.UniqueConstraint(fields=["run", "position"], name="jobrunline_run_position_uniq")
        ]
