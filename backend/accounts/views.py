"""Vistas de cuentas y sesión. / Account and session views."""

from typing import Any, cast

from axes.models import AccessAttempt
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Sum
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers import DetailSerializer

from .roles import ADMIN_GROUP, role_of
from .serializers import (
    CredentialsSerializer,
    MeSerializer,
    NewAccountSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    SetupStatusSerializer,
    UsernameChangeSerializer,
)


def _me(request: Request) -> User:
    """El usuario de una petición ya autenticada. / The authenticated caller."""
    return cast(User, request.user)


def _profile(user: User) -> dict[str, str]:
    return {"username": user.get_username(), "role": role_of(user)}


# DRF exime de CSRF las vistas sin sesión; el login y el alta sí deben exigirlo.
# DRF exempts views without session auth from CSRF; login and setup must enforce it.
@method_decorator(csrf_protect, name="dispatch")
class _AnonymousView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []


class SetupView(_AnonymousView):
    """Estado y alta del primer administrador; se cierra al existir cualquier usuario.

    Status and creation of the first administrator; closed once any user exists.
    """

    @extend_schema(responses=SetupStatusSerializer, tags=["accounts"])
    @method_decorator(ensure_csrf_cookie)
    def get(self, request: Request) -> Response:
        """Indica si falta configurar y entrega la cookie CSRF. / Reports setup status."""
        return Response({"needed": not User.objects.exists()})

    @extend_schema(
        request=NewAccountSerializer,
        responses={201: ProfileSerializer, 403: DetailSerializer},
        tags=["accounts"],
    )
    def post(self, request: Request) -> Response:
        """Crea el primer administrador y abre su sesión. / Creates the first admin."""
        serializer = NewAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # La comprobación y el alta van juntas para que dos peticiones simultáneas
        # no creen dos administradores.
        # Check and create together so concurrent requests cannot make two admins.
        with transaction.atomic():
            if User.objects.select_for_update().exists():
                return Response(
                    {"detail": _("La configuración inicial ya se hizo.")},
                    status=status.HTTP_403_FORBIDDEN,
                )
            user = User.objects.create_superuser(
                serializer.validated_data["username"],
                password=serializer.validated_data["password"],
            )
            user.groups.add(Group.objects.get(name=ADMIN_GROUP))
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(_profile(user), status=status.HTTP_201_CREATED)


class LoginView(_AnonymousView):
    """Inicio de sesión; django-axes bloquea los intentos repetidos.

    Login; django-axes blocks repeated attempts.
    """

    @extend_schema(
        request=CredentialsSerializer,
        responses={200: ProfileSerializer, 400: DetailSerializer},
        tags=["accounts"],
    )
    def post(self, request: Request) -> Response:
        """Abre la sesión con usuario y contraseña. / Opens a session."""
        serializer = CredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request._request, **serializer.validated_data)
        if user is None:
            # Mismo mensaje para usuario inexistente y clave errónea.
            # Same message for unknown user and wrong password.
            return Response(
                {"detail": _("Usuario o contraseña incorrectos.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request._request, user)
        return Response(_profile(user))


class LogoutView(APIView):
    """Cierre de sesión. / Logout."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None}, tags=["accounts"])
    def post(self, request: Request) -> Response:
        """Cierra la sesión. / Closes the session."""
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Datos del usuario con sesión. / Current user data."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer, tags=["accounts"])
    def get(self, request: Request) -> Response:
        """Devuelve usuario, rol e intentos fallidos desde el último inicio de sesión.

        Returns username, role and failed attempts since the last successful sign-in.
        """
        user = _me(request)
        # django-axes borra los intentos de un usuario al entrar bien, así que la suma
        # cuenta solo lo ocurrido desde el último inicio de sesión.
        # django-axes clears a user's attempts on a successful sign-in, so the sum only
        # covers failures since the last sign-in.
        failed = AccessAttempt.objects.filter(username=user.get_username()).aggregate(
            total=Sum("failures_since_start")
        )["total"]
        return Response({**_profile(user), "failed_attempts": failed or 0})


class PasswordChangeView(APIView):
    """Cambio de contraseña. / Password change."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=PasswordChangeSerializer, responses={204: None}, tags=["accounts"])
    def post(self, request: Request) -> Response:
        """Cambia la contraseña y conserva la sesión actual. / Changes the password."""
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = _me(request)
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        # Django invalida las sesiones al cambiar la clave; así no se echa a quien la cambia.
        # Django invalidates sessions on password change; keep the caller's logged in.
        update_session_auth_hash(request._request, user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsernameChangeView(APIView):
    """Cambio de nombre de usuario. / Username change."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=UsernameChangeSerializer, responses=ProfileSerializer, tags=["accounts"])
    def post(self, request: Request) -> Response:
        """Renombra al usuario. / Renames the user."""
        serializer = UsernameChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = _me(request)
        user.username = serializer.validated_data["username"]
        user.save(update_fields=["username"])
        return Response(_profile(user))
