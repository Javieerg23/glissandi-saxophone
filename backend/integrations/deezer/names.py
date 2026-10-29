"""Reglas de nombres y colaboraciones de Deezer.

Name and collaboration rules for Deezer.
"""

import re
from collections.abc import Iterable, Mapping
from typing import Any

from integrations.deezer.models import ArtistRef

# Solo "feat./ft./featuring" entre paréntesis o corchetes.
# shortcut: "with X" y "- feat. X" sin paréntesis no se reconocen; ampliar si aparecen
# en datos reales.
# Only "feat./ft./featuring" inside parentheses or brackets.
_FEAT = re.compile(r"\s*[(\[]\s*(?:feat\.?|ft\.?|featuring)\s+([^)\]]+)[)\]]", re.IGNORECASE)
# Separadores de la lista de invitados. Los nombres con "&" propio (Earth, Wind & Fire)
# solo se salvan cuando Deezer los entrega en ``contributors``.
# Guest list separators. Names containing "&" survive only via ``contributors``.
_SPLIT = re.compile(r"\s*(?:,|&|\band\b)\s*", re.IGNORECASE)


def split_featured(title: str) -> tuple[str, tuple[str, ...]]:
    """Separa el título limpio de los invitados anunciados en él.

    Splits a title into its clean form and the guests announced in it.

    Args:
        title: Título tal como lo da Deezer. / Title as Deezer gives it.

    Returns:
        ``(título sin "feat.", nombres de invitados)``.
        ``(title without "feat.", guest names)``.
    """
    guests: list[str] = []
    for match in _FEAT.finditer(title):
        guests.extend(n for n in _SPLIT.split(match.group(1).strip()) if n)
    return _FEAT.sub("", title).strip(), tuple(guests)


def merge_artists(*groups: Iterable[ArtistRef]) -> tuple[ArtistRef, ...]:
    """Une listas de artistas sin repetir, conservando el orden.

    Merges artist lists without duplicates, keeping order. Names compare
    case-insensitively; an entry with an id replaces an earlier one without it.
    """
    merged: dict[str, ArtistRef] = {}
    for ref in (r for group in groups for r in group):
        key = ref.name.casefold()
        if key not in merged or (merged[key].id is None and ref.id is not None):
            merged[key] = ref
    return tuple(merged.values())


def artist_refs(
    main: Mapping[str, Any] | None, contributors: Iterable[Mapping[str, Any]] = ()
) -> tuple[ArtistRef, ...]:
    """Convierte el artista principal y los colaboradores de Deezer en referencias.

    Turns Deezer's main artist and contributors into references. The main artist
    goes first, then contributors in the order Deezer lists them.
    """
    people = ([main] if main else []) + list(contributors)
    return merge_artists(ArtistRef(p["name"], p.get("id")) for p in people)
