"""Vistas de proxies. / Proxy views.

Solo administradores. La prueba de conexión no devuelve el error bruto: puede
contener la URL del proxy con credenciales.
Administrators only. The connection test does not return the raw error: it
may contain the proxy URL with credentials.
"""

from typing import Any

import requests
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from accounts.permissions import IsAdministrator
from activity.services import log_activity
from integrations.http import build_session

from .models import Proxy
from .serializers import ProxyCheckSerializer, ProxySerializer

# Un punto fijo y ligero de la API pública de Deezer: basta para saber si el proxy sale.
# A fixed, light Deezer API endpoint: enough to tell whether traffic leaves through the proxy.
CHECK_URL = "https://api.deezer.com/infos"


def _fetch_status(proxy: Proxy) -> int | None:
    """Pide ``CHECK_URL`` a través del proxy. / Requests ``CHECK_URL`` through the proxy.

    Returns:
        El código HTTP, o ``None`` si no hubo respuesta. / HTTP status, or ``None``
        when there was no response.
    """
    with build_session() as session:
        session.proxies = {"http": proxy.url, "https": proxy.url}
        try:
            return session.get(CHECK_URL).status_code
        except requests.RequestException:
            return None


class ProxyViewSet(viewsets.ModelViewSet[Proxy]):
    """CRUD de proxies y prueba de conexión. / Proxy CRUD and connection test."""

    queryset = Proxy.objects.all()
    serializer_class = ProxySerializer
    permission_classes = [IsAdministrator]

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        """Guarda y registra la creación. / Saves and logs the creation."""
        proxy: Proxy = serializer.save()
        log_activity(self.request.user, "proxies.created", proxy)

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        """Guarda y registra el cambio. / Saves and logs the change."""
        proxy: Proxy = serializer.save()
        log_activity(self.request.user, "proxies.updated", proxy)

    def perform_destroy(self, instance: Proxy) -> None:
        """Registra y borra. / Logs and deletes."""
        with transaction.atomic():
            log_activity(self.request.user, "proxies.deleted", instance)
            instance.delete()

    @extend_schema(
        request=None,
        responses={200: ProxyCheckSerializer},
        tags=["proxies"],
    )
    @action(detail=True, methods=["post"], url_path="check")
    def check(self, request: Request, pk: str | None = None) -> Response:
        """Comprueba que el proxy da salida al tráfico. / Checks that the proxy relays traffic.

        Un código 2xx o 3xx cuenta como correcto.
        A 2xx or 3xx status counts as success.
        """
        proxy = self.get_object()
        status_code = _fetch_status(proxy)
        ok = status_code is not None and status_code < 400
        log_activity(
            request.user, "proxies.checked", proxy, detail={"ok": ok, "status_code": status_code}
        )
        return Response(ProxyCheckSerializer({"ok": ok, "status_code": status_code}).data)
