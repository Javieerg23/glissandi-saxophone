"""Serializadores de la API del catálogo. / Catalogue API serializers.

Los identificadores externos y todo lo que viene de Deezer o MusicBrainz son de solo
lectura; solo se edita lo que el usuario puede corregir.

External identifiers and anything sourced from Deezer or MusicBrainz are read-only;
only what a user may correct is editable.
"""

from typing import Any

from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import Album, Artist, BlockedItem, Track


class ArtistSerializer(serializers.ModelSerializer[Artist]):
    """Artista; nombre e imagen son editables. / Artist; name and image are editable."""

    class Meta:
        """Campos del artista. / Artist fields."""

        model = Artist
        fields = ["id", "name", "image_url", "deezer_id", "musicbrainz_id"]
        read_only_fields = ["id", "deezer_id", "musicbrainz_id"]


class CreditSerializer(serializers.Serializer[Any]):
    """Artista de un crédito, en orden. / Artist of a credit, in order."""

    id = serializers.IntegerField(source="artist_id")
    name = serializers.CharField(source="artist.name")
    position = serializers.IntegerField()


class AlbumSerializer(serializers.ModelSerializer[Album]):
    """Álbum con sus artistas; título, fecha y portada son editables. / Album with artists."""

    artists = CreditSerializer(source="credits", many=True, read_only=True)

    class Meta:
        """Campos del álbum. / Album fields."""

        model = Album
        fields = [
            "id",
            "title",
            "release_date",
            "cover_url",
            "artists",
            "deezer_id",
            "musicbrainz_id",
        ]
        read_only_fields = ["id", "artists", "deezer_id", "musicbrainz_id"]


class TrackSerializer(serializers.ModelSerializer[Track]):
    """Canción con sus artistas; título y numeración son editables. / Track with artists."""

    artists = CreditSerializer(source="credits", many=True, read_only=True)
    downloaded = serializers.BooleanField(read_only=True)

    class Meta:
        """Campos de la canción. / Track fields."""

        model = Track
        fields = [
            "id",
            "album",
            "title",
            "track_number",
            "disc_number",
            "duration",
            "isrc",
            "artists",
            "downloaded",
            "deezer_id",
            "musicbrainz_id",
        ]
        read_only_fields = [
            "id",
            "album",
            "duration",
            "isrc",
            "artists",
            "downloaded",
            "deezer_id",
            "musicbrainz_id",
        ]


class ArtistIdsSerializer(serializers.Serializer[Any]):
    """Lista ordenada de artistas; el primero es el principal. / Ordered artist list."""

    artists = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)

    def validate_artists(self, ids: list[int]) -> list[Artist]:
        """Comprueba que no hay repetidos y que todos existen. / Checks duplicates and existence."""
        if len(set(ids)) != len(ids):
            raise serializers.ValidationError(_("Hay artistas repetidos."))
        found = Artist.objects.in_bulk(ids)
        if len(found) != len(ids):
            raise serializers.ValidationError(_("Algún artista no existe."))
        return [found[i] for i in ids]


class HistoryEntrySerializer(serializers.Serializer[Any]):
    """Versión anterior de un elemento. / Past version of an item."""

    history_id = serializers.IntegerField()
    history_date = serializers.DateTimeField()
    history_type = serializers.CharField(help_text="+ creado, ~ modificado, - borrado.")
    history_user = serializers.CharField(allow_null=True)
    changes = serializers.DictField(help_text="Valores de los campos editables.")


class RevertSerializer(serializers.Serializer[Any]):
    """Versión a la que volver. / Version to go back to."""

    history_id = serializers.IntegerField()


class BlockedItemSerializer(serializers.ModelSerializer[BlockedItem]):
    """Elemento bloqueado; un bloqueo por tipo e identificador. / Blocked item."""

    class Meta:
        """Campos del bloqueo. / Block fields."""

        model = BlockedItem
        fields = ["id", "kind", "deezer_id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class DeezerSearchQuerySerializer(serializers.Serializer[Any]):
    """Parámetros de la búsqueda en Deezer. / Deezer search parameters."""

    q = serializers.CharField(max_length=200)
    index = serializers.IntegerField(min_value=0, default=0)


class DeezerArtistSerializer(serializers.Serializer[Any]):
    """Artista encontrado en Deezer. / Artist found on Deezer."""

    deezer_id = serializers.IntegerField()
    name = serializers.CharField()
    image_url = serializers.CharField(allow_null=True)
    album_count = serializers.IntegerField(allow_null=True)
    fan_count = serializers.IntegerField(allow_null=True)
    in_catalog = serializers.BooleanField()
    blocked = serializers.BooleanField()


class DeezerSearchSerializer(serializers.Serializer[Any]):
    """Página de resultados de Deezer. / Page of Deezer results."""

    results = DeezerArtistSerializer(many=True)
    total = serializers.IntegerField()
    next_index = serializers.IntegerField(allow_null=True)


class LibrarySummarySerializer(serializers.Serializer[Any]):
    """Recuentos de la biblioteca. / Library counts."""

    artists = serializers.IntegerField()
    albums = serializers.IntegerField()
    tracks = serializers.IntegerField()
    downloaded = serializers.IntegerField(help_text="Canciones con alguna descarga.")
