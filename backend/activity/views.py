"""Vistas de actividad y logs técnicos, solo lectura. / Read-only activity and log views."""

from typing import Any, cast

import django_filters
from django.db.models import QuerySet
from django_db_logger.models import StatusLog
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdministrator
from activity.models import ActivityLog

from .serializers import ActivityLogSerializer, TechnicalLogSerializer


class Pagination(PageNumberPagination):
    """Páginas de 50 filas, hasta 200. / 50-row pages, up to 200.

    Los registros pueden ser muchos: no se devuelve nunca la tabla entera.
    Logs grow large, so the whole table is never returned.
    """

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class ActivityFilter(django_filters.FilterSet):
    """Filtros del historial de actividad. / Activity history filters."""

    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    user = django_filters.NumberFilter(field_name="user_id")
    username = django_filters.CharFilter(field_name="username", lookup_expr="iexact")
    action = django_filters.CharFilter(lookup_expr="icontains")
    object_type = django_filters.CharFilter(method="filter_object_type")
    object_id = django_filters.CharFilter(field_name="object_id")

    def filter_object_type(self, queryset: QuerySet[ActivityLog], name: str, value: str) -> Any:
        """Filtra por ``app.modelo``, p. ej. ``catalog.artist``.

        Filters by ``app.model``, e.g. ``catalog.artist``.
        """
        app_label, _, model = value.partition(".")
        return queryset.filter(content_type__app_label=app_label, content_type__model=model)


class TechnicalLogFilter(django_filters.FilterSet):
    """Filtros de los logs técnicos. / Technical log filters."""

    min_level = django_filters.NumberFilter(field_name="level", lookup_expr="gte")
    module = django_filters.CharFilter(field_name="logger_name", lookup_expr="icontains")
    date_from = django_filters.DateFilter(field_name="create_datetime", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="create_datetime", lookup_expr="date__lte")
    task = django_filters.NumberFilter(method="filter_task")
    search = django_filters.CharFilter(field_name="msg", lookup_expr="icontains")

    def filter_task(self, queryset: QuerySet[StatusLog], name: str, value: Any) -> Any:
        """Filtra por tarea: el formato ``[job N]`` lo pone ``config.settings`` en cada línea.

        Filters by task: every line carries the ``[job N]`` prefix set in the logging config.
        """
        return queryset.filter(msg__startswith=f"[job {int(value)}] ")


class ActivityViewSet(viewsets.ReadOnlyModelViewSet[ActivityLog]):
    """Historial de actividad. Solo lectura: nadie borra ni modifica registros.

    Activity history. Read only: nobody deletes or edits records.
    """

    # core.AppendOnlyQuerySet está tipado para AppendOnlyModel; el cast lo corrige aquí.
    # core.AppendOnlyQuerySet is typed for AppendOnlyModel; the cast corrects it here.
    queryset = cast("QuerySet[ActivityLog]", ActivityLog.objects.select_related("content_type"))
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = ActivityFilter


class TechnicalLogViewSet(viewsets.ReadOnlyModelViewSet[StatusLog]):
    """Logs técnicos de la base de datos, solo para administradores.

    Technical logs stored in the database, administrators only.
    """

    queryset = cast("QuerySet[StatusLog]", StatusLog.objects.all())
    serializer_class = TechnicalLogSerializer
    permission_classes = [IsAdministrator]
    pagination_class = Pagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = TechnicalLogFilter
