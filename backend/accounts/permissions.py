"""Permisos de DRF por grupo. / Group-based DRF permissions."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .roles import is_administrator


class IsAdministrator(BasePermission):
    """Solo los miembros del grupo «administrador».

    Only members of the "administrador" group.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        """Comprueba el grupo del usuario. / Checks the user's group."""
        return is_administrator(request.user)
