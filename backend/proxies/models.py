"""Modelos de la app ``proxies``. / ``proxies`` app models."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Proxy(models.Model):
    """Proxy saliente con contadores de éxito y fallo.

    Outbound proxy with success and failure counters. The counters are the
    operational state the rotation logic reads, so the row is mutable.
    """

    url = models.CharField(_("URL"), max_length=500, unique=True)
    enabled = models.BooleanField(_("activo"), default=True)
    success_count = models.PositiveIntegerField(_("éxitos"), default=0)
    failure_count = models.PositiveIntegerField(_("fallos"), default=0)
    last_used_at = models.DateTimeField(_("último uso"), null=True, blank=True)
    last_failed_at = models.DateTimeField(_("último fallo"), null=True, blank=True)
    created_at = models.DateTimeField(_("creado"), auto_now_add=True)

    class Meta:
        """Orden por URL. / Ordered by URL."""

        ordering = ["url"]

    def __str__(self) -> str:
        """Devuelve la URL. / Returns the URL."""
        return self.url
