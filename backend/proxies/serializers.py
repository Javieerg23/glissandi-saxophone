"""Serializadores de proxies. / Proxy serializers."""

from typing import Any
from urllib.parse import urlsplit

from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import Proxy

ALLOWED_SCHEMES = ("http", "https", "socks5", "socks5h")


class ProxySerializer(serializers.ModelSerializer[Proxy]):
    """Proxy saliente. Los contadores los actualiza la descarga, no la API.

    Outbound proxy. The counters are maintained by downloads, not by the API.
    """

    class Meta:
        """Campos expuestos. / Exposed fields."""

        model = Proxy
        fields = [
            "id",
            "url",
            "enabled",
            "success_count",
            "failure_count",
            "last_used_at",
            "last_failed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "success_count",
            "failure_count",
            "last_used_at",
            "last_failed_at",
            "created_at",
        ]

    def validate_url(self, value: str) -> str:
        """Acepta solo esquemas de proxy conocidos con un host. / Known proxy schemes with a host.

        Args:
            value: URL del proxy. / Proxy URL.

        Returns:
            La misma URL. / The same URL.

        Raises:
            ValidationError: Si el esquema no es válido o falta el host.
        """
        parsed = urlsplit(value)
        if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
            raise serializers.ValidationError(
                _("Usa un proxy con esquema http, https, socks5 o socks5h y un host.")
            )
        return value


class ProxyCheckSerializer(serializers.Serializer[dict[str, Any]]):
    """Resultado de probar un proxy. / Result of testing a proxy."""

    ok = serializers.BooleanField()
    status_code = serializers.IntegerField(allow_null=True)
