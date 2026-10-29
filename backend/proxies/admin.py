"""Administración de la app ``proxies``. / ``proxies`` app admin."""

from django.contrib import admin

from .models import Proxy


@admin.register(Proxy)
class ProxyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Lista de proxies con sus contadores. / Proxy list with its counters."""

    list_display = ("url", "enabled", "success_count", "failure_count")
    list_filter = ("enabled",)
    search_fields = ("url",)
