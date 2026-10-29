"""Tests del cliente de MusicBrainz sin red. / MusicBrainz client tests without network."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import requests
import responses

from integrations.musicbrainz.client import (
    API_URL,
    COVER_ART_URL,
    MIN_INTERVAL,
    MusicBrainzClient,
    RateLimiter,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "musicbrainz"
RECORDING = "7a2b5d8e-1c3f-4e6a-9b0d-2f4e6a8c1b3d"
ARTIST = "0383dadf-2a4e-4d10-a46a-e9e041da8eb3"
OTHER_ARTIST = "5e3b1c2d-9f8e-4a7b-6c5d-4e3f2a1b0c9d"


def _fixture(name: str) -> dict[str, Any]:
    """Carga una respuesta grabada. / Loads a recorded response."""
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


class _FakeClock:
    """Reloj que avanza al dormir, para probar el ritmo sin esperar.

    Clock that advances when slept on, so rate limiting is tested without waiting.
    """

    def __init__(self) -> None:
        """Empieza en el instante 0. / Starts at time 0."""
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        """Devuelve el instante actual. / Returns the current time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Registra y avanza el reloj. / Records the sleep and advances the clock."""
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def fake_clock() -> _FakeClock:
    """Reloj simulado por test. / Fake clock per test."""
    return _FakeClock()


@pytest.fixture
def client(fake_clock: _FakeClock) -> MusicBrainzClient:
    """Cliente con ritmo controlado por el reloj simulado. / Client paced by the fake clock."""
    limiter = RateLimiter(clock=fake_clock.clock, sleep=fake_clock.sleep)
    return MusicBrainzClient(limiter=limiter)


@responses.activate
def test_search_by_isrc_normalizes_and_parses(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording", json=_fixture("recording_search_isrc.json"))
    found = client.search_recordings_by_isrc("gb-um7-10-29604")
    assert responses.calls[0].request.url is not None
    assert "query=isrc%3A%22GBUM71029604%22" in responses.calls[0].request.url
    assert [r.mbid for r in found] == [RECORDING, "1f0e9d8c-7b6a-4f5e-8d3c-2b1a0f9e8d7c"]
    assert found[0].isrcs == ("GBUM71029604",)
    assert found[0].artists == ("Queen",)
    assert found[0].score == 100
    assert found[1].isrcs == ()


@responses.activate
def test_search_recordings_by_name_parses_score(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording", json=_fixture("recording_search_name.json"))
    found = client.search_recordings("Bohemian Rhapsody", "Queen")
    assert found[0].title == "Bohemian Rhapsody"
    assert found[0].score == 96


@responses.activate
def test_search_recordings_escapes_lucene_syntax(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording", json={"recordings": []})
    assert client.search_recordings('Say "Hi" \\ now', "Band") == []
    url = responses.calls[0].request.url
    assert url is not None
    assert "recording%3A%22Say+%5C%22Hi%5C%22+%5C%5C+now%22" in url


@responses.activate
def test_search_artists_parses(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/artist", json=_fixture("artist_search.json"))
    found = client.search_artists("Queen")
    assert [a.name for a in found] == ["Queen", "Queen Latifah"]
    assert found[0].mbid == ARTIST
    assert found[1].score == 37


@responses.activate
def test_find_recording_resolves_by_mbid(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording/{RECORDING}", json=_fixture("recording_lookup.json"))
    recording = client.find_recording(RECORDING)
    assert recording is not None
    assert recording.isrcs == ("GBUM71029604",)
    assert recording.score == 0


@responses.activate
def test_find_recording_returns_none_on_404(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording/{RECORDING}", status=404)
    assert client.find_recording(RECORDING) is None


@responses.activate
def test_http_errors_other_than_404_raise(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording/{RECORDING}", status=400)
    with pytest.raises(requests.HTTPError):
        client.find_recording(RECORDING)


@responses.activate
def test_verify_isrc_true_when_listed(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording/{RECORDING}", json=_fixture("recording_lookup.json"))
    assert client.verify_isrc(RECORDING, "GB-UM7-1-02960-4") is True


@responses.activate
def test_verify_isrc_false_when_different(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording/{RECORDING}", json=_fixture("recording_lookup.json"))
    assert client.verify_isrc(RECORDING, "USRC17607839") is False


@responses.activate
def test_verify_isrc_false_when_recording_unknown(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/recording/{RECORDING}", status=404)
    assert client.verify_isrc(RECORDING, "GBUM71029604") is False


@responses.activate
def test_artist_image_url_from_image_relation(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/artist/{ARTIST}", json=_fixture("artist_lookup_url_rels.json"))
    assert client.find_artist_image_url(ARTIST) == (
        "https://commons.wikimedia.org/wiki/File:Queen_band.jpg"
    )


@responses.activate
def test_artist_without_image_relation_returns_none(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/artist/{OTHER_ARTIST}", json=_fixture("artist_lookup_no_image.json"))
    assert client.find_artist_image_url(OTHER_ARTIST) is None


@responses.activate
def test_unknown_artist_returns_none(client: MusicBrainzClient) -> None:
    responses.get(f"{API_URL}/artist/{ARTIST}", status=404)
    assert client.find_artist_image_url(ARTIST) is None


def test_cover_art_url_for_release_group() -> None:
    assert MusicBrainzClient.cover_art_url(RECORDING) == (
        f"{COVER_ART_URL}/release-group/{RECORDING}/front"
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.find_recording("../../etc"),
        lambda c: c.find_artist_image_url("not-a-uuid"),
        lambda c: MusicBrainzClient.cover_art_url("x/y"),
    ],
)
def test_rejects_identifiers_that_are_not_uuids(
    client: MusicBrainzClient, call: Callable[[MusicBrainzClient], object]
) -> None:
    with pytest.raises(ValueError, match="badly formed|is not a valid UUID|hexadecimal"):
        call(client)


def test_rate_limiter_first_call_does_not_wait(fake_clock: _FakeClock) -> None:
    limiter = RateLimiter(clock=fake_clock.clock, sleep=fake_clock.sleep)
    limiter.wait()
    assert fake_clock.slept == []


def test_rate_limiter_waits_the_missing_time(fake_clock: _FakeClock) -> None:
    limiter = RateLimiter(clock=fake_clock.clock, sleep=fake_clock.sleep)
    limiter.wait()
    fake_clock.now += 0.25
    limiter.wait()
    assert fake_clock.slept == [pytest.approx(MIN_INTERVAL - 0.25)]


def test_rate_limiter_does_not_wait_after_interval(fake_clock: _FakeClock) -> None:
    limiter = RateLimiter(clock=fake_clock.clock, sleep=fake_clock.sleep)
    limiter.wait()
    fake_clock.now += 2.0
    limiter.wait()
    assert fake_clock.slept == []


@responses.activate
def test_client_spaces_consecutive_requests(
    client: MusicBrainzClient, fake_clock: _FakeClock
) -> None:
    responses.get(f"{API_URL}/artist", json={"artists": []})
    client.search_artists("a")
    client.search_artists("b")
    assert fake_clock.slept == [pytest.approx(MIN_INTERVAL)]
    assert len(responses.calls) == 2
