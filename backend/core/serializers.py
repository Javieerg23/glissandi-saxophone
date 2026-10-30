"""Serializadores compartidos; describen las respuestas en el esquema OpenAPI.

Shared serializers; they describe responses in the OpenAPI schema.
"""

from typing import Any

from rest_framework import serializers


class HealthSerializer(serializers.Serializer[Any]):
    """Respuesta del endpoint de estado. / Health endpoint response."""

    status = serializers.CharField()
    message = serializers.CharField()


class DetailSerializer(serializers.Serializer[Any]):
    """Cuerpo de error con un mensaje legible. / Error body with a readable message."""

    detail = serializers.CharField()
