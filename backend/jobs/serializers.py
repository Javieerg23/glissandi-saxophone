"""Serializadores de la API de tareas. / Task API serializers."""

from typing import Any

from rest_framework import serializers

from jobs import registry
from jobs.models import JobRun, JobRunLine


class JobRunSerializer(serializers.ModelSerializer[JobRun]):
    """Estado y progreso de una ejecución, solo lectura.

    State and progress of a run, read only.
    """

    user = serializers.CharField(source="user.username", read_only=True, default=None)

    class Meta:
        """Todo es de solo lectura: lo escribe el motor. / All read only: the engine writes it."""

        model = JobRun
        fields = [
            "id",
            "kind",
            "params",
            "user",
            "status",
            "started_at",
            "finished_at",
            "done",
            "total",
            "current",
            "summary",
        ]
        read_only_fields = fields


class JobRunLineSerializer(serializers.ModelSerializer[JobRunLine]):
    """Línea del registro de una ejecución. / One log line of a run."""

    class Meta:
        """Las líneas son inmutables. / Lines are immutable."""

        model = JobRunLine
        fields = ["position", "level", "message", "created_at"]
        read_only_fields = fields


class JobStartSerializer(serializers.Serializer[Any]):
    """Petición para lanzar una tarea. / Request to start a task."""

    kind = serializers.CharField(help_text="Tipo registrado. / Registered kind.")
    params = serializers.DictField(
        required=False, default=dict, help_text="Parámetros JSON. / JSON params."
    )

    def validate_kind(self, value: str) -> str:
        """Solo acepta tipos del registro. / Accepts registered kinds only."""
        if value not in registry.kinds():
            raise serializers.ValidationError(f"Tipo desconocido: {value}.")
        return value
