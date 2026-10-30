"""Vistas de la API del catálogo. / Catalogue API views.

Lectura para cualquier usuario con sesión; cambiar, bloquear o revertir exige ser
administrador. Cada cambio queda en la actividad y, vía django-simple-history, en el
historial del elemento.

Any signed-in user may read; editing, blocking or reverting requires an administrator.
Every change goes to the activity log and, through django-simple-history, to the
item's own history.
"""

from typing import Any, ClassVar, cast

import requests
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.translation import gettext as _
from django_filters.rest_framework import DjangoFilterBackend  # type: ignore[import-untyped]
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from accounts.roles import is_administrator
from activity.services import log_activity
from core.serializers import DetailSerializer
from integrations.deezer import DeezerClient, DeezerError

from .filters import AlbumFilter, ArtistFilter, TrackFilter
from .models import Album, Artist, BlockedItem, Download, Track
from .serializers import (
    AlbumSerializer,
    ArtistIdsSerializer,
    ArtistSerializer,
    BlockedItemSerializer,
    DeezerSearchQuerySerializer,
    DeezerSearchSerializer,
    HistoryEntrySerializer,
    LibrarySummarySerializer,
    RevertSerializer,
    TrackSerializer,
)


class AdministratorWrites(BasePermission):
    """Sesión para leer; administrador para cambiar. / Session to read, admin to write."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Lectura con sesión, escritura solo de administradores. / Read vs write."""
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return is_administrator(request.user)


class CatalogPagination(PageNumberPagination):
    """Paginación por número de página. / Page-number pagination."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def _user(request: Request) -> User:
    return cast(User, request.user)


class _CatalogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet[Any],
):
    """Base común: lista, detalle, edición, historial y reversión.

    Shared base: list, detail, edit, history and revert.
    """

    permission_classes = [AdministratorWrites]
    pagination_class = CatalogPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    # Prefijo de las acciones de actividad y campos que edita el usuario (los que
    # revierte el historial). / Activity-action prefix and user-editable fields.
    kind: ClassVar[str]
    editable_fields: ClassVar[tuple[str, ...]]

    def perform_update(self, serializer: BaseSerializer[Any]) -> None:
        """Guarda con autor en el historial y registra la actividad. / Saves and logs."""
        # simple_history lee este atributo para rellenar ``history_user``.
        # simple_history reads this attribute to fill ``history_user``.
        serializer.instance._history_user = _user(self.request)  # type: ignore[union-attr]
        serializer.save()
        log_activity(
            _user(self.request),
            f"catalog.{self.kind}.updated",
            serializer.instance,
            {"fields": sorted(serializer.validated_data)},
        )

    @extend_schema(responses=HistoryEntrySerializer(many=True), tags=["catalog"])
    @action(detail=True, methods=["get"])
    def history(self, request: Request, pk: str | None = None) -> Response:
        """Versiones del elemento, la más reciente primero. / Item versions, newest first."""
        entries = [
            {
                "history_id": record.history_id,
                "history_date": record.history_date,
                "history_type": record.history_type,
                "history_user": record.history_user.get_username() if record.history_user else None,
                "changes": {name: getattr(record, name) for name in self.editable_fields},
            }
            for record in self.get_object().history.all()
        ]
        return Response(HistoryEntrySerializer(entries, many=True).data)

    @extend_schema(request=RevertSerializer, tags=["catalog"])
    @action(detail=True, methods=["post"])
    def revert(self, request: Request, pk: str | None = None) -> Response:
        """Devuelve los campos editables a los de una versión. / Restores a version."""
        body = RevertSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item = self.get_object()
        record = item.history.filter(history_id=body.validated_data["history_id"]).first()
        if record is None:
            raise NotFound(_("Esa versión no existe."))
        # Solo los campos editables: los identificadores externos son inmutables.
        # Editable fields only: external identifiers are immutable.
        for name in self.editable_fields:
            setattr(item, name, getattr(record, name))
        item._history_user = _user(request)
        item.save()
        log_activity(
            _user(request),
            f"catalog.{self.kind}.reverted",
            item,
            {"history_id": record.history_id},
        )
        return Response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data)


class _CreditsMixin:
    """Acción para sustituir los artistas de un álbum o canción.

    Action to replace the artists of an album or track.
    """

    kind: ClassVar[str]

    @extend_schema(request=ArtistIdsSerializer, tags=["catalog"])
    @action(detail=True, methods=["put"], url_path="artists")
    def set_artists(self, request: Request, pk: str | None = None) -> Response:
        """Reemplaza los artistas, en el orden recibido. / Replaces the artists in order."""
        viewset = cast(_CatalogViewSet, self)
        body = ArtistIdsSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        item = viewset.get_object()
        with transaction.atomic():
            item.credits.all().delete()
            credit = item.credits.model
            credit.objects.bulk_create(
                credit(**{item.credits.field.name: item}, artist=artist, position=position)
                for position, artist in enumerate(body.validated_data["artists"])
            )
        log_activity(
            _user(request),
            f"catalog.{self.kind}.artists_changed",
            item,
            {"artists": [a.pk for a in body.validated_data["artists"]]},
        )
        return Response(viewset.get_serializer(viewset.get_queryset().get(pk=item.pk)).data)


class ArtistViewSet(_CatalogViewSet):
    """Artistas del catálogo. / Catalogue artists."""

    queryset = Artist.objects.all()
    serializer_class = ArtistSerializer
    filterset_class = ArtistFilter
    search_fields = ["name"]
    ordering_fields = ["name", "id"]
    ordering = ["name", "id"]
    kind = "artist"
    editable_fields = ("name", "image_url")


class AlbumViewSet(_CreditsMixin, _CatalogViewSet):
    """Álbumes del catálogo. / Catalogue albums."""

    queryset = Album.objects.prefetch_related("credits__artist")
    serializer_class = AlbumSerializer
    filterset_class = AlbumFilter
    search_fields = ["title", "credits__artist__name"]
    ordering_fields = ["title", "release_date", "id"]
    ordering = ["title", "id"]
    kind = "album"
    editable_fields = ("title", "release_date", "cover_url")


class TrackViewSet(_CreditsMixin, _CatalogViewSet):
    """Canciones del catálogo. / Catalogue tracks."""

    queryset = Track.objects.with_downloaded().prefetch_related("credits__artist")
    serializer_class = TrackSerializer
    filterset_class = TrackFilter
    search_fields = ["title", "credits__artist__name"]
    ordering_fields = ["title", "track_number", "id"]
    ordering = ["album", "disc_number", "track_number", "id"]
    kind = "track"
    editable_fields = ("title", "track_number", "disc_number")


class BlockedItemViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet[BlockedItem],
):
    """Lista de bloqueados: bloquear es crear y desbloquear es borrar.

    Blocked list: blocking is creating and unblocking is deleting.
    """

    queryset = BlockedItem.objects.order_by("-created_at", "-id")
    serializer_class = BlockedItemSerializer
    permission_classes = [AdministratorWrites]
    pagination_class = CatalogPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["kind", "deezer_id"]
    search_fields = ["name"]

    def perform_create(self, serializer: BaseSerializer[BlockedItem]) -> None:
        """Bloquea y registra la actividad. / Blocks and logs."""
        item = serializer.save()
        log_activity(
            _user(self.request),
            "catalog.blocked.added",
            item,
            {"kind": item.kind, "deezer_id": item.deezer_id},
        )

    def perform_destroy(self, instance: BlockedItem) -> None:
        """Desbloquea y registra la actividad. / Unblocks and logs."""
        # Se registra antes de borrar: después ya no hay ``pk`` para el objeto.
        # Logged before deleting: afterwards the object has no ``pk``.
        log_activity(
            _user(self.request),
            "catalog.blocked.removed",
            instance,
            {"kind": instance.kind, "deezer_id": instance.deezer_id},
        )
        instance.delete()


class DeezerArtistSearchView(APIView):
    """Busca artistas en Deezer para poder importarlos. / Searches Deezer artists to import."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[DeezerSearchQuerySerializer],
        responses={200: DeezerSearchSerializer, 502: DetailSerializer},
        tags=["catalog"],
    )
    def get(self, request: Request) -> Response:
        """Resultados con marca de los que ya están o están bloqueados. / Annotated results."""
        query = DeezerSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            page = DeezerClient().search_artists(
                query.validated_data["q"], index=query.validated_data["index"]
            )
        except (DeezerError, requests.RequestException):
            return Response(
                {"detail": _("Deezer no responde.")}, status=status.HTTP_502_BAD_GATEWAY
            )
        ids = [a.id for a in page.items]
        known = set(Artist.objects.filter(deezer_id__in=ids).values_list("deezer_id", flat=True))
        blocked = set(
            BlockedItem.objects.filter(kind=BlockedItem.Kind.ARTIST, deezer_id__in=ids).values_list(
                "deezer_id", flat=True
            )
        )
        results = [
            {
                "deezer_id": a.id,
                "name": a.name,
                "image_url": a.image_url,
                "album_count": a.album_count,
                "fan_count": a.fan_count,
                "in_catalog": a.id in known,
                "blocked": a.id in blocked,
            }
            for a in page.items
        ]
        return Response({"results": results, "total": page.total, "next_index": page.next_index})


class LibrarySummaryView(APIView):
    """Recuentos para el panel. / Counts for the dashboard."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=LibrarySummarySerializer, tags=["catalog"])
    def get(self, request: Request) -> Response:
        """Artistas, álbumes, canciones y canciones descargadas. / Library counts."""
        return Response(
            {
                "artists": Artist.objects.count(),
                "albums": Album.objects.count(),
                "tracks": Track.objects.count(),
                # Canciones, no descargas: una canción puede descargarse más de una vez.
                # Tracks, not downloads: a track may be downloaded more than once.
                "downloaded": Download.objects.values("track").distinct().count(),
            }
        )
