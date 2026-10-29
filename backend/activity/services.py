"""Servicios de actividad y mantenimiento de logs. / Activity and log-maintenance services."""

from datetime import timedelta
from typing import Any

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Model
from django.utils import timezone
from django_db_logger.models import StatusLog

from activity.logs import redact
from activity.models import ActivityLog

TECHNICAL_LOG_RETENTION_DAYS = 30


def log_activity(
    user: User | AnonymousUser | None,
    action: str,
    obj: Model | None = None,
    detail: dict[str, Any] | None = None,
) -> ActivityLog:
    """Registra una acción en el historial de actividad.

    Records an action in the activity history.

    Args:
        user: Quien actúa; ``None`` o anónimo para acciones del sistema.
            The actor; ``None`` or anonymous for system actions.
        action: Código de la acción, p. ej. ``"catalog.artist.blocked"``.
            Action code, e.g. ``"catalog.artist.blocked"``.
        obj: Objeto afectado, si lo hay. / Affected object, if any.
        detail: Datos extra serializables a JSON; se ocultan los sensibles.
            Extra JSON-serializable data; sensitive values are hidden.

    Returns:
        La fila creada. / The created row.
    """
    actor = user if user is not None and user.is_authenticated else None
    return ActivityLog.objects.create(
        user=actor,
        username=actor.get_username() if actor else "",
        action=action,
        content_type=ContentType.objects.get_for_model(obj) if obj else None,
        # Se asigna sin ``target``: con ``None`` el GFK vaciaría ``object_id`` (NOT NULL).
        # Assigned without ``target``: with ``None`` the GFK would null ``object_id``.
        object_id=str(obj.pk) if obj else "",
        detail=redact(detail or {}),
    )


def purge_technical_logs(days: int = TECHNICAL_LOG_RETENTION_DAYS) -> int:
    """Borra los logs técnicos más antiguos que ``days`` días.

    Deletes technical logs older than ``days`` days. Only ``StatusLog`` is
    touched: ``ActivityLog`` is never purged.

    Args:
        days: Antigüedad máxima conservada. / Maximum age kept.

    Returns:
        Número de filas borradas. / Number of rows deleted.
    """
    cutoff = timezone.now() - timedelta(days=days)
    deleted: int
    deleted, _ = StatusLog.objects.filter(create_datetime__lt=cutoff).delete()
    return deleted
