"""Subida a mano del audio de una canción que no se encuentra.

Hand upload of the audio of a track that cannot be found.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from activity.services import log_activity
from core.serializers import DetailSerializer
from integrations.audio import AudioError, InvalidAudio, convert, render_path, write_tags
from integrations.audio.validate import MAX_BYTES, validate_audio
from preferences.models import get_value

from .models import Download, Track
from .serializers import TrackSerializer
from .services.downloading import _tags
from .views import AdministratorWrites, _user


class TrackUploadSerializer(serializers.Serializer[Any]):
    """Fichero de audio subido. / Uploaded audio file."""

    file = serializers.FileField(help_text="mp3, m4a, flac, opus, ogg, wav; 200 MB max.")


class TrackUploadView(APIView):
    """Recibe el audio de una canción, lo convierte, lo etiqueta y lo guarda.

    Receives a track's audio, converts and tags it, and stores it like a download.
    """

    permission_classes = [AdministratorWrites]
    parser_classes = [MultiPartParser]

    @extend_schema(
        description=(
            "Valida el fichero (tipo y tamaño), lo convierte al formato de los ajustes, lo "
            "etiqueta con los datos de la canción, lo guarda con la plantilla de nombres y "
            "registra la descarga sin URL de origen. / Validates, converts, tags and stores "
            "the file, and records a download with no source URL."
        ),
        request={"multipart/form-data": TrackUploadSerializer},
        responses={
            201: TrackSerializer,
            400: DetailSerializer,
            403: DetailSerializer,
            404: DetailSerializer,
            422: DetailSerializer,
        },
        examples=[
            OpenApiExample(
                "Fichero no válido",
                value={"file": ["El fichero no es un audio válido o supera los 200 MB."]},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Fallo de conversión",
                value={"detail": "No se pudo convertir el audio."},
                response_only=True,
                status_codes=["422"],
            ),
        ],
        tags=["catalog"],
    )
    def post(self, request: Request, pk: int) -> Response:
        """Guarda el audio subido como descarga de la canción. / Stores the upload."""
        track = get_object_or_404(Track.objects.select_related("album"), pk=pk)
        serializer = TrackUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data["file"]
        fmt = get_value("download.format")
        folder = Path(get_value("download.folder"))
        tags = _tags(track)
        # Igual que en la descarga: todo se hace en una carpeta temporal y solo se mueve el
        # fichero terminado, para no dejar nada a medias en la biblioteca si algo falla.
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            # Del nombre original solo se aprovecha la extensión: el resto lo pone el catálogo.
            source = work / f"upload{Path(uploaded.name).suffix.lower()}"
            with source.open("wb") as out:
                for chunk in uploaded.chunks():
                    out.write(chunk)
            try:
                validate_audio(source, max_bytes=MAX_BYTES)
            except InvalidAudio as exc:
                raise ValidationError(
                    {"file": [_("El fichero no es un audio válido o supera los 200 MB.")]}
                ) from exc
            try:
                converted = convert(source, work, fmt, stem="track")
                write_tags(converted, tags)
            except AudioError:
                return Response(
                    {"detail": _("No se pudo convertir el audio.")},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            dest = folder / render_path(
                get_value("download.name_template"), tags, converted.suffix.lstrip(".")
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(converted, dest)
        with transaction.atomic():
            Download.objects.create(track=track, file_path=str(dest), audio_format=fmt)
            log_activity(
                _user(request),
                "catalog.track.uploaded",
                track,
                {"file_path": str(dest), "audio_format": fmt},
            )
        return Response(
            TrackSerializer(Track.objects.with_downloaded().get(pk=track.pk)).data,
            status=status.HTTP_201_CREATED,
        )
