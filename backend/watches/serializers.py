"""Serializadores de novedades. / New-release serializers."""

from typing import Any

from django.db import transaction
from rest_framework import serializers

from catalog.models import Artist
from catalog.serializers import ArtistIdsSerializer, CreditSerializer

from .models import Watch, WatchArtist, WatchRun


class WatchSerializer(serializers.ModelSerializer[Watch]):
    """Vigilancia de novedades con sus artistas en orden. / New-release watch with ordered artists.

    Los artistas se leen en ``artists`` (id, nombre y posición) y se escriben como lista
    ordenada de ids en ``artist_ids``; sin ``artist_ids`` se dejan como estaban.
    Artists are read from ``artists`` and written as an ordered id list in ``artist_ids``;
    leaving ``artist_ids`` out keeps them unchanged.
    """

    artists = CreditSerializer(source="watch_artists", many=True, read_only=True)
    artist_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )

    class Meta:
        """Campos expuestos. / Exposed fields."""

        model = Watch
        fields = [
            "id",
            "name",
            "enabled",
            "interval_hours",
            "auto_download",
            "artists",
            "artist_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_artist_ids(self, ids: list[int]) -> list[Artist]:
        """Mismas reglas que ``set_artists`` del catálogo.

        Same rules as the catalogue's ``set_artists``: no repeats, all must exist.
        """
        return ArtistIdsSerializer().validate_artists(ids)

    def create(self, validated_data: dict[str, Any]) -> Watch:
        """Crea la vigilancia y sus artistas. / Creates the watch and its artists."""
        artists = validated_data.pop("artist_ids", [])
        with transaction.atomic():
            watch = super().create(validated_data)
            _set_artists(watch, artists)
        return watch

    def update(self, instance: Watch, validated_data: dict[str, Any]) -> Watch:
        """Actualiza y, si llegan, reemplaza los artistas.

        Updates and, when sent, replaces the artists.
        """
        artists = validated_data.pop("artist_ids", None)
        with transaction.atomic():
            watch = super().update(instance, validated_data)
            if artists is not None:
                watch.watch_artists.all().delete()
                _set_artists(watch, artists)
        return watch


def _set_artists(watch: Watch, artists: list[Artist]) -> None:
    WatchArtist.objects.bulk_create(
        WatchArtist(watch=watch, artist=artist, position=position)
        for position, artist in enumerate(artists)
    )


class WatchRunSerializer(serializers.ModelSerializer[WatchRun]):
    """Resultado de una comprobación, solo lectura. / One check result, read-only."""

    class Meta:
        """Todos los campos son de solo lectura. / Every field is read-only."""

        model = WatchRun
        fields = ["id", "watch", "started_at", "finished_at", "status", "found", "detail"]
        read_only_fields = fields
