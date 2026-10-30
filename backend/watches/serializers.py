"""Serializadores de novedades. / New-release serializers."""

from rest_framework import serializers

from .models import Watch, WatchRun


class WatchSerializer(serializers.ModelSerializer[Watch]):
    """Vigilancia de novedades. / New-release watch."""

    class Meta:
        """Campos expuestos. / Exposed fields."""

        model = Watch
        fields = ["id", "name", "enabled", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class WatchRunSerializer(serializers.ModelSerializer[WatchRun]):
    """Resultado de una comprobación, solo lectura. / One check result, read-only."""

    class Meta:
        """Todos los campos son de solo lectura. / Every field is read-only."""

        model = WatchRun
        fields = ["id", "watch", "started_at", "finished_at", "status", "found", "detail"]
        read_only_fields = fields
