"""Filtros de la API del catálogo. / Catalogue API filters."""

from django.db.models import QuerySet
from django_filters import (  # type: ignore[import-untyped]
    BooleanFilter,
    DateFilter,
    FilterSet,
    NumberFilter,
)

from .models import Album, Artist, Track


class ArtistFilter(FilterSet):
    """Filtra artistas por nombre e identificadores externos. / Filters artists."""

    class Meta:
        """Campos filtrables. / Filterable fields."""

        model = Artist
        fields = {
            "name": ["icontains"],
            "deezer_id": ["exact"],
            "musicbrainz_id": ["exact"],
        }


class AlbumFilter(FilterSet):
    """Filtra álbumes por título, artista y fecha de publicación. / Filters albums."""

    artist = NumberFilter(field_name="credits__artist_id")
    released_after = DateFilter(field_name="release_date", lookup_expr="gte")
    released_before = DateFilter(field_name="release_date", lookup_expr="lte")

    class Meta:
        """Campos filtrables. / Filterable fields."""

        model = Album
        fields = {"title": ["icontains"], "deezer_id": ["exact"], "musicbrainz_id": ["exact"]}


class TrackFilter(FilterSet):
    """Filtra canciones por título, álbum, artista y descarga. / Filters tracks."""

    album = NumberFilter(field_name="album_id")
    artist = NumberFilter(field_name="credits__artist_id")
    downloaded = BooleanFilter(method="filter_downloaded")

    class Meta:
        """Campos filtrables. / Filterable fields."""

        model = Track
        fields = {"title": ["icontains"], "deezer_id": ["exact"], "isrc": ["exact"]}

    def filter_downloaded(
        self, queryset: QuerySet[Track], name: str, value: bool
    ) -> QuerySet[Track]:
        """Usa la anotación de ``with_downloaded``. / Uses the ``with_downloaded`` annotation."""
        return queryset.filter(downloaded=value)  # type: ignore[misc]  # anotación de with_downloaded
