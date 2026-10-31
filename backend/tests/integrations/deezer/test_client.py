"""Tests del cliente de Deezer, sin red. / Deezer client tests, no network."""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import requests
import responses

from integrations.deezer import AlbumRef, ArtistRef, DeezerClient, DeezerError, Page
from integrations.deezer.models import VARIOUS_ARTISTS_ID, Album

FIXTURES = Path(__file__).parents[2] / "fixtures" / "deezer"
API = "https://api.deezer.com"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def client() -> DeezerClient:
    return DeezerClient()


@responses.activate
def test_search_artists_paginates(client: DeezerClient) -> None:
    responses.get(f"{API}/search/artist", json=_fixture("search_artist"))
    page = client.search_artists("daft", limit=500)
    assert [a.name for a in page.items] == ["Daft Punk", "Daft Funk"]
    assert page.items[0].image_url.endswith("1000x1000.jpg")  # type: ignore[union-attr]
    assert (page.total, page.next_index) == (5, 2)
    query = responses.calls[0].request.params  # type: ignore[attr-defined]
    assert query == {"q": "daft", "index": "0", "limit": "100"}


@responses.activate
def test_last_page_has_no_next_index(client: DeezerClient) -> None:
    responses.get(f"{API}/artist/27/albums", json=_fixture("artist_albums"))
    page = client.artist_albums(27)
    assert page.next_index is None and page.total == 2


@responses.activate
def test_get_artist(client: DeezerClient) -> None:
    responses.get(f"{API}/artist/27", json=_fixture("artist"))
    artist = client.get_artist(27)
    assert (artist.id, artist.album_count, artist.fan_count) == (27, 38, 4500000)


@responses.activate
def test_artist_albums_handles_null_dates_and_covers(client: DeezerClient) -> None:
    responses.get(f"{API}/artist/27/albums", json=_fixture("artist_albums"))
    first, second = client.artist_albums(27).items
    assert first.release_date == date(2001, 3, 7)
    assert second.release_date is None and second.cover_url is None and second.explicit
    assert first.artists == ()


@responses.activate
def test_get_album(client: DeezerClient) -> None:
    responses.get(f"{API}/album/302127", json=_fixture("album"))
    album = client.get_album(302127)
    assert album.artists == (ArtistRef("Daft Punk", 27),)
    assert (album.upc, album.track_count, album.record_type) == ("724384960650", 14, "album")
    assert not album.is_various_artists


@responses.activate
def test_various_artists_album(client: DeezerClient) -> None:
    responses.get(f"{API}/album/700", json=_fixture("album_various"))
    album = client.get_album(700)
    assert album.is_various_artists and album.artists[0].id == VARIOUS_ARTISTS_ID
    assert album.upc is None


@responses.activate
def test_album_tracks_inherit_album_and_parse_title_guests(client: DeezerClient) -> None:
    responses.get(f"{API}/album/302127/tracks", json=_fixture("album_tracks"))
    album = Album(302127, "Discovery", (), cover_url="c.jpg")
    page = client.album_tracks(album)
    first, second = page.items
    assert first.album == AlbumRef(302127, "Discovery", "c.jpg")
    assert first.artists == (ArtistRef("Daft Punk", 27),)
    assert second.title == "Aerodynamic"
    assert second.artists == (
        ArtistRef("Daft Punk", 27),
        ArtistRef("Nile Rodgers"),
        ArtistRef("Pharrell"),
    )
    assert page.next_index == 2


@responses.activate
def test_get_track_with_collaborations(client: DeezerClient) -> None:
    responses.get(f"{API}/track/67238735", json=_fixture("track"))
    track = client.get_track(67238735)
    assert track.title == "Get Lucky [Radio Edit]"
    assert track.artists == (ArtistRef("Daft Punk", 27), ArtistRef("Pharrell Williams", 1234))
    assert (track.isrc, track.track_position, track.disk_number) == ("USQX91300108", 8, 1)
    assert track.album == AlbumRef(6575789, "Random Access Memories", track.album.cover_url)  # type: ignore[union-attr]


@responses.activate
def test_get_track_minimal_fields(client: DeezerClient) -> None:
    responses.get(f"{API}/track/1", json=_fixture("track_minimal"))
    track = client.get_track(1)
    assert track.isrc is None and track.album is None and not track.explicit
    assert track.artists == (ArtistRef("Solo", 9),)


@responses.activate
def test_get_track_by_isrc(client: DeezerClient) -> None:
    responses.get(f"{API}/track/isrc:USQX91300108", json=_fixture("track"))
    assert client.get_track_by_isrc("USQX91300108").id == 67238735


@responses.activate
def test_search_tracks_sends_the_query(client: DeezerClient) -> None:
    body = {"data": [_fixture("track_minimal")], "total": 3, "next": "…"}
    responses.get(f"{API}/search/track", json=body)
    page = client.search_tracks('artist:"Solo" track:"Intro"')
    assert [t.title for t in page.items] == ["Intro"]
    assert (page.total, page.next_index) == (3, 1)
    query = responses.calls[0].request.params  # type: ignore[attr-defined]
    assert query["q"] == 'artist:"Solo" track:"Intro"'


@responses.activate
@pytest.mark.parametrize(
    ("fixture", "message"), [("error_quota", "Quota limit exceeded"), ("error_empty", "Error")]
)
def test_application_errors_raise(client: DeezerClient, fixture: str, message: str) -> None:
    responses.get(f"{API}/artist/1", json=_fixture(fixture))
    with pytest.raises(DeezerError, match=message):
        client.get_artist(1)


@responses.activate
def test_http_errors_propagate(client: DeezerClient) -> None:
    responses.get(f"{API}/artist/1", status=404)
    with pytest.raises(requests.HTTPError, match="404"):
        client.get_artist(1)


def test_page_defaults() -> None:
    assert Page() == Page(items=(), total=0, next_index=None)
