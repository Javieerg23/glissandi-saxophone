"""Copia de la biblioteca en JSON: exportar, vista previa e importar.

JSON library backup: export, preview and restore.

La copia es la salida de ``dumpdata`` de los modelos de la biblioteca y se carga con
``loaddata`` en la tarea ``library_restore``. Las filas que ya existen (mismo ``pk``)
no se tocan: así se respetan las tablas de solo añadir y nunca se pisa lo editado.

The backup is ``dumpdata`` output for the library models and is loaded with
``loaddata`` in the ``library_restore`` task. Rows that already exist (same ``pk``)
are left alone, so append-only tables are respected and edits are never overwritten.
"""

import json
import tempfile
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Any, cast

from django.contrib.auth.models import User
from django.core import serializers as django_serializers
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.serializers.base import DeserializationError
from django.db.models import Model
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdministrator
from activity.services import log_activity
from core.serializers import DetailSerializer
from jobs import runner
from jobs.serializers import JobRunSerializer

#: Modelos de la biblioteca, en orden de dependencias. Sin las tablas de historial:
#: apuntan a usuarios que no existen en otra instalación.
#: Library models in dependency order. History tables are left out: they point to
#: users that do not exist on another installation.
LIBRARY_MODELS = (
    "catalog.artist",
    "catalog.album",
    "catalog.albumartist",
    "catalog.track",
    "catalog.trackartist",
    "catalog.blockeditem",
    "catalog.download",
)

#: Recuentos de la vista previa. / Preview counts.
PREVIEW_MODELS = {
    "artists": "catalog.artist",
    "albums": "catalog.album",
    "tracks": "catalog.track",
    "downloads": "catalog.download",
}

#: Prefijo de los ficheros subidos que espera la tarea. / Prefix of uploads the task expects.
UPLOAD_PREFIX = "glissandi-restore-"


class BackupError(ValueError):
    """El fichero no es una copia válida de la biblioteca. / Not a valid library backup."""


def export_library() -> str:
    """Biblioteca entera en el formato de ``dumpdata``. / Whole library as ``dumpdata`` JSON."""
    out = StringIO()
    call_command("dumpdata", *LIBRARY_MODELS, format="json", stdout=out)
    return out.getvalue()


def parse_backup(data: bytes) -> list[tuple[dict[str, Any], Model]]:
    """Valida una copia y la devuelve junto a sus objetos sin guardar.

    Validates a backup and returns each entry with its unsaved object.

    Raises:
        BackupError: Si no es JSON, trae otros modelos o algún campo no encaja.
            If it is not JSON, holds other models or some field does not fit.
    """
    try:
        entries = json.loads(data)
    except ValueError:
        raise BackupError(_("El fichero no es JSON válido.")) from None
    if not isinstance(entries, list) or not all(
        isinstance(e, dict)
        and e.get("model") in LIBRARY_MODELS
        and isinstance(e.get("fields"), dict)
        for e in entries
    ):
        raise BackupError(_("El fichero no es una copia de la biblioteca."))
    try:
        objects = [d.object for d in django_serializers.deserialize("python", entries)]
    except (DeserializationError, FieldDoesNotExist) as error:
        message = _("La copia tiene datos no válidos: %(error)s") % {"error": error}
        raise BackupError(message) from None
    return list(zip(entries, objects, strict=True))


def _existing(parsed: list[tuple[dict[str, Any], Model]]) -> list[bool]:
    """Si cada entrada ya está en la base de datos. / Whether each entry is already stored."""
    stored: dict[type[Model], set[Any]] = defaultdict(set)
    for model in {type(obj) for _entry, obj in parsed}:
        # Todos los pk de una vez: un ``pk__in`` enorme superaría el límite de SQLite.
        # All pks at once: a huge ``pk__in`` would hit SQLite's parameter limit.
        stored[model] = set(model._default_manager.values_list("pk", flat=True))
    return [obj.pk in stored[type(obj)] for _entry, obj in parsed]


def preview(parsed: list[tuple[dict[str, Any], Model]]) -> dict[str, dict[str, int]]:
    """Cuántos elementos trae la copia y cuántos ya existen. / Totals and already stored."""
    counts = {key: {"total": 0, "existing": 0} for key in PREVIEW_MODELS}
    labels = {label: key for key, label in PREVIEW_MODELS.items()}
    for (entry, _obj), exists in zip(parsed, _existing(parsed), strict=True):
        if key := labels.get(entry["model"]):
            counts[key]["total"] += 1
            counts[key]["existing"] += exists
    return counts


def restore(parsed: list[tuple[dict[str, Any], Model]]) -> dict[str, int]:
    """Carga con ``loaddata`` solo las entradas que faltan. / Loads only missing entries.

    Returns:
        Entradas creadas y omitidas. / Created and skipped entries.
    """
    flags = zip(parsed, _existing(parsed), strict=True)
    new = [entry for (entry, _obj), exists in flags if not exists]
    if new:
        # ``loaddata`` lee de fichero; a cambio da transacción, orden y secuencias al día.
        # ``loaddata`` reads from a file; in return it handles transaction, order and sequences.
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / "library.json"
            fixture.write_text(json.dumps(new))
            call_command("loaddata", str(fixture), verbosity=0)
    return {"created": len(new), "skipped": len(parsed) - len(new)}


def upload_path(name: object) -> Path:
    """Ruta de un fichero subido para restaurar, sin salir de la carpeta temporal.

    Path of an uploaded restore file, never outside the temp folder.

    Raises:
        BackupError: Si el nombre no es el de una subida. / If it is not an upload's name.
    """
    if not isinstance(name, str) or not name.startswith(UPLOAD_PREFIX) or Path(name).name != name:
        raise BackupError(_("Fichero de copia desconocido."))
    return Path(tempfile.gettempdir()) / name


# --- API ---


class BackupUploadSerializer(serializers.Serializer[Any]):
    """Fichero de copia subido. / Uploaded backup file."""

    file = serializers.FileField(help_text="JSON exportado. / Exported JSON.")


class BackupCountSerializer(serializers.Serializer[Any]):
    """Elementos de un tipo en la copia. / Items of one kind in the backup."""

    total = serializers.IntegerField()
    existing = serializers.IntegerField(help_text="Ya en la biblioteca. / Already in the library.")


class BackupPreviewSerializer(serializers.Serializer[Any]):
    """Vista previa de una copia. / Backup preview."""

    artists = BackupCountSerializer()
    albums = BackupCountSerializer()
    tracks = BackupCountSerializer()
    downloads = BackupCountSerializer()


def _read_upload(request: Request) -> bytes:
    """Contenido del fichero subido. / Uploaded file content.

    Raises:
        ValidationError: Si falta el fichero. / If the file is missing.
    """
    body = BackupUploadSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    data: bytes = body.validated_data["file"].read()
    return data


def _bad_file(error: BackupError) -> Response:
    return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)


_INVALID = OpenApiResponse(DetailSerializer, description="Fichero no válido. / Invalid file.")


class LibraryExportView(APIView):
    """Descarga la biblioteca en JSON. / Downloads the library as JSON."""

    permission_classes = [IsAdministrator]

    @extend_schema(
        description="Copia completa de la biblioteca (``dumpdata``), como fichero adjunto. "
        "/ Full library backup (``dumpdata``) as an attachment.",
        responses={
            (200, "application/json"): OpenApiResponse(
                OpenApiTypes.BINARY, description="Fichero de copia. / Backup file."
            ),
            403: DetailSerializer,
        },
        tags=["catalog"],
    )
    def get(self, request: Request) -> HttpResponse:
        """Fichero ``glissandi-<fecha>.json``. / ``glissandi-<date>.json`` file."""
        response = HttpResponse(export_library(), content_type="application/json")
        name = f"glissandi-{timezone.localdate():%Y%m%d}.json"
        response["Content-Disposition"] = f'attachment; filename="{name}"'
        return response


class LibraryBackupPreviewView(APIView):
    """Vista previa de una copia antes de importarla. / Backup preview before restoring."""

    permission_classes = [IsAdministrator]
    parser_classes = [MultiPartParser]

    @extend_schema(
        description="Cuenta lo que trae la copia y lo que ya existe; no cambia nada. "
        "/ Counts what the backup holds and what already exists; changes nothing.",
        request={"multipart/form-data": BackupUploadSerializer},
        responses={200: BackupPreviewSerializer, 400: _INVALID, 403: DetailSerializer},
        examples=[
            OpenApiExample(
                "Vista previa",
                response_only=True,
                value={
                    "artists": {"total": 12, "existing": 10},
                    "albums": {"total": 40, "existing": 35},
                    "tracks": {"total": 480, "existing": 420},
                    "downloads": {"total": 300, "existing": 300},
                },
            )
        ],
        tags=["catalog"],
    )
    def post(self, request: Request) -> Response:
        """Recuentos por tipo. / Counts per kind."""
        try:
            parsed = parse_backup(_read_upload(request))
        except BackupError as error:
            return _bad_file(error)
        return Response(BackupPreviewSerializer(preview(parsed)).data)


class LibraryRestoreView(APIView):
    """Importa una copia en segundo plano. / Restores a backup in the background."""

    permission_classes = [IsAdministrator]
    parser_classes = [MultiPartParser]

    @extend_schema(
        description="Valida la copia y lanza la tarea ``library_restore``, que añade lo que "
        "falta sin reescribir lo que ya existe. / Validates the backup and starts the "
        "``library_restore`` task, which adds what is missing without rewriting existing rows.",
        request={"multipart/form-data": BackupUploadSerializer},
        responses={
            201: JobRunSerializer,
            400: _INVALID,
            403: DetailSerializer,
            409: OpenApiResponse(
                DetailSerializer, description="Ya hay otra en curso. / Another one is running."
            ),
        },
        tags=["catalog"],
    )
    def post(self, request: Request) -> Response:
        """Ejecución lanzada. / Started run."""
        try:
            data = _read_upload(request)
            parse_backup(data)
        except BackupError as error:
            return _bad_file(error)
        with tempfile.NamedTemporaryFile(prefix=UPLOAD_PREFIX, suffix=".json", delete=False) as out:
            out.write(data)
        user = cast(User, request.user)
        try:
            run = runner.start("library_restore", {"file": Path(out.name).name}, user)
        except runner.JobAlreadyRunning:
            Path(out.name).unlink()
            return Response(
                {"detail": _("Ya hay una tarea de este tipo en curso.")},
                status=status.HTTP_409_CONFLICT,
            )
        log_activity(user, "catalog.library.restore_started", run)
        return Response(JobRunSerializer(run).data, status=status.HTTP_201_CREATED)
