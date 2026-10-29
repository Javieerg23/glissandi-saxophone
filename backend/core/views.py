"""Vistas transversales. / Cross-cutting views."""

from django.utils.translation import gettext as _
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """Indica que el servicio responde; lo usan el front y los despliegues.

    Reports that the service is up; used by the frontend and deployments.
    """
    return Response({"status": "ok", "message": _("El servicio funciona.")})
