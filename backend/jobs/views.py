"""Vistas de la API de tareas. / Task API views."""

from typing import cast

from django.contrib.auth.models import User
from django.utils.translation import gettext as _
from django_filters import rest_framework as filters  # type: ignore[import-untyped]
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from activity.services import log_activity
from core.serializers import DetailSerializer
from jobs import runner
from jobs.models import JobRun, JobRunLine
from jobs.serializers import JobRunLineSerializer, JobRunSerializer, JobStartSerializer

#: Tope de líneas por petición; la web sigue pidiendo con ``?after=``.
#: Cap of lines per request; the web keeps polling with ``?after=``.
MAX_LINES = 500


class RunPagination(PageNumberPagination):
    """Paginación del historial de ejecuciones. / Run history pagination."""

    page_size = 25


class JobRunFilter(filters.FilterSet):  # type: ignore[misc]
    """Filtros del listado: tipo, estado y fechas de inicio. / List filters."""

    started_after = filters.IsoDateTimeFilter(field_name="started_at", lookup_expr="gte")
    started_before = filters.IsoDateTimeFilter(field_name="started_at", lookup_expr="lte")

    class Meta:
        """Campos filtrables por igualdad. / Fields filtered by equality."""

        model = JobRun
        fields = ["kind", "status"]


class JobRunViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet[JobRun],
):
    """Lanza, consulta y detiene tareas en segundo plano.

    Starts, inspects and stops background tasks. Runs are never edited or
    deleted through the API: the engine owns them.
    """

    queryset = JobRun.objects.select_related("user")
    serializer_class = JobRunSerializer
    pagination_class = RunPagination
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = JobRunFilter

    @extend_schema(
        request=JobStartSerializer,
        responses={201: JobRunSerializer, 400: DetailSerializer, 409: DetailSerializer},
        examples=[
            OpenApiExample("Importar", value={"kind": "import", "params": {"deezer_ids": [27]}})
        ],
        tags=["jobs"],
    )
    def create(self, request: Request) -> Response:
        """Lanza una tarea; 409 si ya hay otra activa del mismo tipo.

        Starts a task; 409 if one of the same kind is already active.
        """
        serializer = JobStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = cast(User, request.user)
        try:
            run = runner.start(
                serializer.validated_data["kind"], serializer.validated_data["params"], user
            )
        except runner.JobAlreadyRunning:
            return Response(
                {"detail": _("Ya hay una tarea de este tipo en curso.")},
                status=status.HTTP_409_CONFLICT,
            )
        log_activity(user, "jobs.run.started", run, {"kind": run.kind})
        return Response(JobRunSerializer(run).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "after", int, description="Última posición ya recibida. / Last position received."
            )
        ],
        responses=JobRunLineSerializer(many=True),
        tags=["jobs"],
    )
    @action(detail=True, methods=["get"])
    def lines(self, request: Request, pk: str | None = None) -> Response:
        """Líneas de registro posteriores a ``after`` (por defecto, desde el principio).

        Log lines after position ``after`` (default: from the start).
        """
        run = self.get_object()
        try:
            after = int(request.query_params.get("after", 0))
        except ValueError:
            return Response(
                {"detail": _("«after» debe ser un entero.")}, status=status.HTTP_400_BAD_REQUEST
            )
        lines = JobRunLine.objects.filter(run=run, position__gt=after)[:MAX_LINES]
        return Response(JobRunLineSerializer(list(lines), many=True).data)  # type: ignore[arg-type]

    @extend_schema(
        request=None,
        responses={200: JobRunSerializer, 409: DetailSerializer},
        tags=["jobs"],
    )
    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: str | None = None) -> Response:
        """Pide detener la tarea; 409 si ya terminó. / Asks to stop; 409 if already closed."""
        run = self.get_object()
        try:
            run = runner.stop(run.pk)
        except runner.JobClosed:
            return Response(
                {"detail": _("La tarea ya ha terminado.")}, status=status.HTTP_409_CONFLICT
            )
        log_activity(cast(User, request.user), "jobs.run.stop_requested", run, {"kind": run.kind})
        return Response(JobRunSerializer(run).data)
