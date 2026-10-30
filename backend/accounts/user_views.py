"""Gestión de usuarios para administradores. / User management for administrators."""

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from activity.services import log_activity
from core.serializers import DetailSerializer

from .permissions import IsAdministrator
from .roles import ADMIN_GROUP
from .serializers import (
    ManagedUserCreateSerializer,
    ManagedUserSerializer,
    ManagedUserUpdateSerializer,
)


class UserViewSet(viewsets.GenericViewSet[User]):
    """Listar, crear y cambiar usuarios. No hay borrado: se desactiva.

    List, create and change users. There is no delete: accounts are deactivated.
    """

    queryset = User.objects.prefetch_related("groups").order_by("username")
    serializer_class = ManagedUserSerializer
    permission_classes = [IsAdministrator]

    @extend_schema(responses=ManagedUserSerializer(many=True), tags=["accounts"])
    def list(self, request: Request) -> Response:
        """Lista todos los usuarios. / Lists every user."""
        return Response(ManagedUserSerializer(self.get_queryset(), many=True).data)

    @extend_schema(
        request=ManagedUserCreateSerializer,
        responses={201: ManagedUserSerializer, 400: DetailSerializer},
        tags=["accounts"],
    )
    def create(self, request: Request) -> Response:
        """Crea un usuario con su rol. / Creates a user with a role."""
        serializer = ManagedUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            user = User.objects.create_user(data["username"], password=data["password"])
            user.groups.add(Group.objects.get(name=data["role"]))
            log_activity(
                request.user, "accounts.user.created", obj=user, detail={"role": data["role"]}
            )
        return Response(ManagedUserSerializer(user).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ManagedUserUpdateSerializer,
        responses={200: ManagedUserSerializer, 400: DetailSerializer},
        tags=["accounts"],
    )
    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        """Cambia el rol o desactiva a un usuario. / Changes a user's role or deactivates them.

        Nadie se quita a sí mismo el rol de administrador ni se desactiva, así
        siempre queda un administrador con sesión.
        Nobody can demote or deactivate themselves, so an administrator always remains.
        """
        target = self.get_object()
        serializer = ManagedUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data
        demotes = "role" in changes and changes["role"] != ADMIN_GROUP
        if target.pk == request.user.pk and (changes.get("is_active") is False or demotes):
            return Response(
                {"detail": _("No puedes desactivarte ni quitarte el rol de administrador.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            if "role" in changes:
                target.groups.set([Group.objects.get(name=changes["role"])])
            if "is_active" in changes:
                target.is_active = changes["is_active"]
                target.save(update_fields=["is_active"])
            log_activity(request.user, "accounts.user.updated", obj=target, detail=changes)
        return Response(ManagedUserSerializer(target).data)
