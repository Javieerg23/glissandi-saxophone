"""Vistas de novedades. / New-release views.

Las comprobaciones (``WatchRun``) solo se leen: las escribe la tarea de comprobación.
Checks (``WatchRun``) are read-only here: the check task writes them.
"""

from typing import Any

from django.db import transaction
from django.db.models import ProtectedError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer

from activity.services import log_activity

from .models import Watch, WatchRun
from .serializers import WatchRunSerializer, WatchSerializer


class WatchInUse(APIException):
    """La vigilancia tiene comprobaciones registradas. / The watch has recorded checks."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = _("La vigilancia tiene comprobaciones registradas y no se puede borrar.")
    default_code = "watch_in_use"


class WatchPagination(PageNumberPagination):
    """Páginas de 50 elementos. / 50 items per page."""

    page_size = 50


class WatchViewSet(viewsets.ModelViewSet[Watch]):
    """CRUD de vigilancias e historial de comprobaciones. / Watch CRUD and check history."""

    queryset = Watch.objects.all()
    serializer_class = WatchSerializer
    pagination_class = WatchPagination

    def perform_create(self, serializer: BaseSerializer[Any]) -> None:
        """Guarda y registra la creación. / Saves and logs the creation."""
        watch: Watch = serializer.save()
        log_activity(self.request.user, "watches.created", watch)

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        """Guarda y registra el cambio. / Saves and logs the change."""
        watch: Watch = serializer.save()
        log_activity(self.request.user, "watches.updated", watch)

    def perform_destroy(self, instance: Watch) -> None:
        """Borra si no tiene comprobaciones; si las tiene, responde 409.

        Deletes unless it has checks, in which case it answers 409. The log
        row is written inside the same transaction, so a refused delete leaves
        no trace.
        """
        try:
            with transaction.atomic():
                log_activity(self.request.user, "watches.deleted", instance)
                instance.delete()
        except ProtectedError as error:
            raise WatchInUse() from error

    @extend_schema(responses=WatchRunSerializer(many=True), tags=["watches"])
    @action(detail=True, methods=["get"])
    def runs(self, request: Request, pk: str | None = None) -> Response:
        """Historial de comprobaciones, de la más reciente a la más antigua.

        Check history, newest first.
        """
        watch = self.get_object()
        paginator = WatchPagination()
        page = paginator.paginate_queryset(WatchRun.objects.filter(watch=watch), request, self)
        serializer = WatchRunSerializer(page, many=True)  # type: ignore[arg-type]
        return paginator.get_paginated_response(serializer.data)
