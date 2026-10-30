"""Tests de la API del catálogo. / Catalogue API tests."""

from typing import Any

import pytest
import responses
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, USER_GROUP
from activity.models import ActivityLog
from catalog.factories import (
    AlbumFactory,
    ArtistFactory,
    DownloadFactory,
    TrackFactory,
)
from catalog.models import Album, Artist, BlockedItem, Track
from tests.accounts.conftest import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/catalog"
DEEZER = "https://api.deezer.com/search/artist"


@pytest.fixture
def admin(admin_user: User) -> APIClient:
    """Cliente con sesión de administrador. / Administrator client."""
    client = APIClient()
    client.force_login(admin_user)
    return client


@pytest.fixture
def user(db: None) -> APIClient:
    """Cliente con sesión de usuario normal. / Regular user client."""
    client = APIClient()
    client.force_login(make_user("pepe", USER_GROUP))
    return client


@pytest.fixture
def admin_user(db: None) -> User:
    """Administrador. / Administrator."""
    return make_user("admin", ADMIN_GROUP)


def _ids(response: Any) -> list[int]:
    return [item["id"] for item in response.data["results"]]


# --- Permisos / Permissions ---


@pytest.mark.parametrize("path", ["artists", "albums", "tracks", "blocked", "deezer/artists"])
def test_anonymous_cannot_read(path: str) -> None:
    assert APIClient().get(f"{BASE}/{path}/").status_code in (401, 403)


def test_user_reads_but_cannot_write(user: APIClient) -> None:
    artist = ArtistFactory()
    assert user.get(f"{BASE}/artists/{artist.pk}/").status_code == 200
    assert user.patch(f"{BASE}/artists/{artist.pk}/", {"name": "X"}).status_code == 403
    assert user.post(f"{BASE}/blocked/", {"kind": "artist", "deezer_id": 1}).status_code == 403
    assert user.put(f"{BASE}/albums/1/artists/", {"artists": [1]}, format="json").status_code == 403
    assert user.post(f"{BASE}/artists/{artist.pk}/revert/", {"history_id": 1}).status_code == 403


# --- Lectura, filtros y búsqueda / Reading, filters, search ---


def test_artists_filter_search_and_pagination(admin: APIClient) -> None:
    ana, bea = ArtistFactory(name="Ana Torroja"), ArtistFactory(name="Bea")
    assert _ids(admin.get(f"{BASE}/artists/?name__icontains=torro")) == [ana.pk]
    assert _ids(admin.get(f"{BASE}/artists/?search=bea")) == [bea.pk]
    assert _ids(admin.get(f"{BASE}/artists/?deezer_id={bea.deezer_id}")) == [bea.pk]
    page = admin.get(f"{BASE}/artists/?page_size=1&ordering=-name")
    assert page.data["count"] == 2
    assert _ids(page) == [bea.pk]


def test_albums_filter_by_artist_and_date(admin: APIClient) -> None:
    old = AlbumFactory(title="Viejo", release_date="1999-01-01")
    new = AlbumFactory(title="Nuevo", release_date="2020-05-05")
    artist = new.artists.get()
    assert _ids(admin.get(f"{BASE}/albums/?artist={artist.pk}")) == [new.pk]
    assert _ids(admin.get(f"{BASE}/albums/?released_after=2000-01-01")) == [new.pk]
    assert _ids(admin.get(f"{BASE}/albums/?released_before=2000-01-01")) == [old.pk]
    assert _ids(admin.get(f"{BASE}/albums/?search={artist.name}")) == [new.pk]
    body = admin.get(f"{BASE}/albums/{new.pk}/").data
    assert body["artists"] == [{"id": artist.pk, "name": artist.name, "position": 0}]


def test_tracks_filter_by_download(admin: APIClient) -> None:
    got, missing = TrackFactory(), TrackFactory()
    DownloadFactory(track=got)
    assert _ids(admin.get(f"{BASE}/tracks/?downloaded=true")) == [got.pk]
    assert _ids(admin.get(f"{BASE}/tracks/?downloaded=false")) == [missing.pk]
    assert _ids(admin.get(f"{BASE}/tracks/?album={got.album_id}")) == [got.pk]
    assert _ids(admin.get(f"{BASE}/tracks/?artist={got.artists.get().pk}")) == [got.pk]
    assert admin.get(f"{BASE}/tracks/{got.pk}/").data["downloaded"] is True


# --- Edición / Editing ---


def test_edit_changes_mutable_and_ignores_immutable(admin: APIClient) -> None:
    track = TrackFactory(title="Viejo", deezer_id=77, isrc="ES0000000001")
    response = admin.patch(
        f"{BASE}/tracks/{track.pk}/",
        {"title": "Nuevo", "deezer_id": 1, "isrc": "XX", "duration": 5},
    )
    assert response.status_code == 200
    track.refresh_from_db()
    assert (track.title, track.deezer_id, track.isrc, track.duration) == (
        "Nuevo",
        77,
        "ES0000000001",
        None,
    )
    entry = ActivityLog.objects.get(action="catalog.track.updated")
    assert entry.detail == {"fields": ["title"]}


def test_edit_validates(admin: APIClient) -> None:
    artist = ArtistFactory()
    assert admin.patch(f"{BASE}/artists/{artist.pk}/", {"name": ""}).status_code == 400


# --- Artistas de álbum y canción / Album and track artists ---


@pytest.mark.parametrize(("path", "factory"), [("albums", AlbumFactory), ("tracks", TrackFactory)])
def test_replace_artists_in_order(admin: APIClient, path: str, factory: Any) -> None:
    item = factory()
    a, b = ArtistFactory(), ArtistFactory()
    response = admin.put(
        f"{BASE}/{path}/{item.pk}/artists/", {"artists": [b.pk, a.pk]}, format="json"
    )
    assert response.status_code == 200
    assert [x["id"] for x in response.data["artists"]] == [b.pk, a.pk]
    assert [x["position"] for x in response.data["artists"]] == [0, 1]
    assert ActivityLog.objects.filter(action__endswith=".artists_changed").count() == 1


@pytest.mark.parametrize("payload", [[], [1, 1], [999999]])
def test_replace_artists_rejects_bad_lists(admin: APIClient, payload: list[int]) -> None:
    album = AlbumFactory()
    artist = album.artists.get()
    if payload == [1, 1]:
        payload = [artist.pk, artist.pk]
    response = admin.put(f"{BASE}/albums/{album.pk}/artists/", {"artists": payload}, format="json")
    assert response.status_code == 400
    assert album.artists.get() == artist


# --- Historial y reversión / History and revert ---


def test_history_and_revert(admin: APIClient, admin_user: User) -> None:
    artist = ArtistFactory(name="Original")
    admin.patch(f"{BASE}/artists/{artist.pk}/", {"name": "Cambiado"})
    history = admin.get(f"{BASE}/artists/{artist.pk}/history/").data
    assert [h["changes"]["name"] for h in history] == ["Cambiado", "Original"]
    assert history[0]["history_user"] == admin_user.username
    assert history[1]["history_user"] is None

    response = admin.post(
        f"{BASE}/artists/{artist.pk}/revert/", {"history_id": history[1]["history_id"]}
    )
    assert response.status_code == 200
    assert response.data["name"] == "Original"
    artist.refresh_from_db()
    assert artist.name == "Original"
    assert ActivityLog.objects.filter(action="catalog.artist.reverted").exists()


def test_revert_keeps_identifiers(admin: APIClient) -> None:
    artist = ArtistFactory(deezer_id=5, musicbrainz_id=None)
    first = artist.history.earliest().history_id
    artist.musicbrainz_id = "5b3a1b9c-7a25-4b5c-8f0e-1c1f1a1b1c1d"
    artist.save()
    assert (
        admin.post(f"{BASE}/artists/{artist.pk}/revert/", {"history_id": first}).status_code == 200
    )
    artist.refresh_from_db()
    assert str(artist.musicbrainz_id) == "5b3a1b9c-7a25-4b5c-8f0e-1c1f1a1b1c1d"


def test_revert_unknown_version_is_404(admin: APIClient) -> None:
    artist = ArtistFactory()
    other = ArtistFactory().history.get().history_id
    assert (
        admin.post(f"{BASE}/artists/{artist.pk}/revert/", {"history_id": other}).status_code == 404
    )


# --- Bloqueos / Blocking ---


def test_block_list_and_unblock(admin: APIClient) -> None:
    created = admin.post(f"{BASE}/blocked/", {"kind": "album", "deezer_id": 9, "name": "Malo"})
    assert created.status_code == 201
    assert admin.post(f"{BASE}/blocked/", {"kind": "album", "deezer_id": 9}).status_code == 400
    assert admin.get(f"{BASE}/blocked/?kind=album").data["count"] == 1
    assert admin.get(f"{BASE}/blocked/?kind=track").data["count"] == 0
    assert admin.get(f"{BASE}/blocked/?search=mal").data["count"] == 1
    assert admin.delete(f"{BASE}/blocked/{created.data['id']}/").status_code == 204
    assert not BlockedItem.objects.exists()
    assert list(ActivityLog.objects.order_by("id").values_list("action", flat=True)) == [
        "catalog.blocked.added",
        "catalog.blocked.removed",
    ]


# --- Búsqueda en Deezer / Deezer search ---


@responses.activate
def test_deezer_search_marks_known_and_blocked(user: APIClient) -> None:
    ArtistFactory(deezer_id=1)
    BlockedItem.objects.create(kind="artist", deezer_id=2)
    responses.get(
        DEEZER,
        json={
            "data": [
                {"id": i, "name": f"A{i}", "picture_xl": f"http://img/{i}"} for i in (1, 2, 3)
            ],
            "total": 3,
        },
    )
    body = user.get(f"{BASE}/deezer/artists/?q=a").data
    assert [(r["deezer_id"], r["in_catalog"], r["blocked"]) for r in body["results"]] == [
        (1, True, False),
        (2, False, True),
        (3, False, False),
    ]
    assert (body["total"], body["next_index"]) == (3, None)


def test_deezer_search_requires_query(user: APIClient) -> None:
    assert user.get(f"{BASE}/deezer/artists/").status_code == 400


@responses.activate
def test_deezer_failure_is_502(user: APIClient) -> None:
    responses.get(DEEZER, json={"error": {"type": "Exception", "message": "boom"}})
    assert user.get(f"{BASE}/deezer/artists/?q=a").status_code == 502
    assert Artist.objects.count() == 0 and Album.objects.count() == 0 and Track.objects.count() == 0
