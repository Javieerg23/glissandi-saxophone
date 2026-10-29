"""Tests de las reglas de nombres. / Tests for the naming rules."""

import pytest

from integrations.deezer.models import ArtistRef
from integrations.deezer.names import artist_refs, merge_artists, split_featured


@pytest.mark.parametrize(
    ("title", "clean", "guests"),
    [
        ("Intro", "Intro", ()),
        ("Get Lucky (feat. Pharrell Williams)", "Get Lucky", ("Pharrell Williams",)),
        ("Song [ft. A]", "Song", ("A",)),
        ("Song (Featuring A, B & C)", "Song", ("A", "B", "C")),
        ("Song (feat. A and B)", "Song", ("A", "B")),
        ("Song (feat. A) (Radio Edit)", "Song (Radio Edit)", ("A",)),
        ("Song (Live) (feat. A)", "Song (Live)", ("A",)),
        ("Song (feat. A) [feat. B]", "Song", ("A", "B")),
        ("Song (Remix)", "Song (Remix)", ()),
        ("Song (feat. ,)", "Song", ()),
    ],
)
def test_split_featured(title: str, clean: str, guests: tuple[str, ...]) -> None:
    assert split_featured(title) == (clean, guests)


def test_merge_artists_dedups_case_insensitively_and_prefers_ids() -> None:
    merged = merge_artists(
        [ArtistRef("Ana"), ArtistRef("Luis", 2)], [ArtistRef("ana", 1), ArtistRef("LUIS")]
    )
    assert merged == (ArtistRef("ana", 1), ArtistRef("Luis", 2))


def test_artist_refs_main_first_then_contributors() -> None:
    refs = artist_refs({"id": 1, "name": "A"}, [{"id": 2, "name": "B"}, {"id": 1, "name": "A"}])
    assert refs == (ArtistRef("A", 1), ArtistRef("B", 2))


def test_artist_refs_without_main() -> None:
    assert artist_refs(None, [{"name": "B"}]) == (ArtistRef("B"),)
    assert artist_refs(None) == ()
