"""Serializadores de actividad y logs técnicos. / Activity and technical log serializers."""

from django_db_logger.models import StatusLog
from rest_framework import serializers

from activity.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer[ActivityLog]):
    """Una entrada del historial de actividad. / One activity history entry."""

    object_type = serializers.SerializerMethodField()

    class Meta:
        """Todo de solo lectura. / Everything is read only."""

        model = ActivityLog
        fields = [
            "id",
            "created_at",
            "user",
            "username",
            "action",
            "object_type",
            "object_id",
            "detail",
        ]
        read_only_fields = fields

    def get_object_type(self, obj: ActivityLog) -> str:
        """Devuelve ``app.modelo`` del objeto afectado. / Returns ``app.model`` of the target."""
        content_type = obj.content_type
        return f"{content_type.app_label}.{content_type.model}" if content_type else ""


class TechnicalLogSerializer(serializers.ModelSerializer[StatusLog]):
    """Una línea de log técnico en base de datos. / One technical log line in the database."""

    created_at = serializers.DateTimeField(source="create_datetime", read_only=True)

    class Meta:
        """Todo de solo lectura. / Everything is read only."""

        model = StatusLog
        fields = ["id", "created_at", "level", "logger_name", "msg", "trace"]
        read_only_fields = fields
