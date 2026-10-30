"""Tests de la tarea de descarga, con yt-dlp y ffmpeg simulados. / Download task tests."""

from pathlib import Path
from typing import Any

import pytest

from activity.models import ActivityLog
from catalog.factories import ArtistFactory, DownloadFactory, TrackArtistFactory, TrackFactory
from catalog.models import Download, Track
from catalog.services import downloading
from integrations.youtube import NoProxyAvailable, VideoMatch, YoutubeError
from jobs import runner
from jobs.models import JobRun
from preferences.models import Preference
from proxies.models import Proxy

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def fake_media(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Sustituye yt-dlp, ffmpeg y mutagen; devuelve lo que se les pidió.

    Replaces yt-dlp, ffmpeg and mutagen; returns what they were asked.
    """
    calls: dict[str, Any] = {"proxies": [], "tagged": []}
    Preference.objects.create(key="download.folder", value=str(tmp_path / "library"))

    def find(title: str, artists: list[str], duration: float, *, proxy: str | None) -> VideoMatch:
        calls["proxies"].append(proxy)
        return VideoMatch("abcdefghijk", title, duration)

    def fetch(video_id: str, dest_dir: Path, *, proxy: str | None) -> Path:
        raw = dest_dir / f"{video_id}.webm"
        raw.write_bytes(b"raw")
        return raw

    def to_format(source: Path, dest_dir: Path, fmt: str) -> Path:
        out = dest_dir / f"{source.stem}.{fmt}"
        out.write_bytes(b"audio")
        return out

    monkeypatch.setattr(downloading, "find_best_video", find)
    monkeypatch.setattr(downloading, "download_audio", fetch)
    monkeypatch.setattr(downloading, "convert", to_format)
    monkeypatch.setattr(downloading, "write_tags", lambda path, tags: calls["tagged"].append(tags))
    return calls


def _run(**params: Any) -> JobRun:
    return runner.start("download", params, None)


def test_downloads_converts_tags_and_records(fake_media: dict[str, Any], tmp_path: Path) -> None:
    track = TrackFactory(title="Song", duration=200)
    run = _run(track_ids=[track.pk])

    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary == {"downloaded": 1, "failed": 0, "skipped": 0}
    download = Download.objects.get(track=track)
    assert Path(download.file_path).read_bytes() == b"audio"
    assert Path(download.file_path).is_relative_to(tmp_path / "library")
    assert Path(download.file_path).name.endswith("Song.mp3")
    assert download.audio_format == "mp3"
    assert download.source_url == "https://www.youtube.com/watch?v=abcdefghijk"
    assert fake_media["tagged"][0].title == "Song"
    assert ActivityLog.objects.filter(action="catalog.download.finished").exists()


def test_respects_format_preference(tmp_path: Path) -> None:
    Preference.objects.create(key="download.format", value="flac")
    track = TrackFactory(duration=200)
    _run(track_ids=[track.pk])
    assert Download.objects.get(track=track).audio_format == "flac"


def test_tags_follow_credit_order_and_release_year() -> None:
    track = TrackFactory(duration=200, credit=None)
    track.album.release_date = "2020-05-01"
    track.album.save()
    TrackArtistFactory(track=track, artist=ArtistFactory(name="Second"), position=1)
    TrackArtistFactory(track=track, artist=ArtistFactory(name="First"), position=0)
    tags = downloading._tags(Track.objects.get(pk=track.pk))
    assert tags.artists == ("First", "Second")
    assert tags.year == 2020


def test_already_downloaded_track_is_not_repeated(fake_media: dict[str, Any]) -> None:
    done = DownloadFactory(track=TrackFactory(duration=200)).track
    run = _run(track_ids=[done.pk])
    assert run.summary == {"downloaded": 0, "failed": 0, "skipped": 1}
    assert Download.objects.filter(track=done).count() == 1
    assert fake_media["proxies"] == []


def test_all_pending_skips_downloaded() -> None:
    DownloadFactory(track=TrackFactory(duration=200))
    pending = TrackFactory(duration=200)
    run = _run(all_pending=True)
    assert run.summary["downloaded"] == 1
    assert Download.objects.filter(track=pending).exists()


def test_failure_of_one_track_does_not_stop_the_rest() -> None:
    broken = TrackFactory(title="Broken", duration=None)
    fine = TrackFactory(title="Fine", duration=200)
    run = _run(track_ids=[broken.pk, fine.pk])
    assert run.status == JobRun.Status.SUCCEEDED
    assert run.summary == {"downloaded": 1, "failed": 1, "skipped": 0}
    assert run.lines.filter(level="error", message__contains="Broken").exists()


def test_track_without_matching_video_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(downloading, "find_best_video", lambda *a, **k: None)
    run = _run(track_ids=[TrackFactory(duration=200).pk])
    assert run.summary["failed"] == 1
    assert Download.objects.count() == 0


def test_proxy_counters_on_success_and_failure(
    fake_media: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    Proxy.objects.create(url="http://proxy:3128")
    Proxy.objects.create(url="http://off:3128", enabled=False)
    ok = TrackFactory(duration=200)
    _run(track_ids=[ok.pk])
    proxy = Proxy.objects.get(url="http://proxy:3128")
    assert (proxy.success_count, proxy.failure_count) == (1, 0)
    assert proxy.last_used_at is not None
    assert fake_media["proxies"] == ["http://proxy:3128"]

    def boom(*args: Any, **kwargs: Any) -> Path:
        raise YoutubeError("blocked")

    monkeypatch.setattr(downloading, "download_audio", boom)
    _run(track_ids=[TrackFactory(duration=200).pk])
    proxy.refresh_from_db()
    assert (proxy.success_count, proxy.failure_count) == (1, 1)
    assert proxy.last_failed_at is not None
    assert Proxy.objects.get(url="http://off:3128").success_count == 0


def test_all_proxies_cooling_down_fails_tracks() -> None:
    Proxy.objects.create(url="http://proxy:3128")
    pool = downloading.build_pool()
    pool.report_failure("http://proxy:3128", 10**12)
    track = TrackFactory(duration=200)
    with pytest.raises(NoProxyAvailable):
        downloading.download_track(track, pool, fmt="mp3", folder=Path("x"), template="{title}")


def test_stop_is_cooperative_between_tracks(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = TrackFactory(duration=200), TrackFactory(duration=200)
    real = downloading.download_track

    def stop_after_first(track: Track, *args: Any, **kwargs: Any) -> Download:
        result = real(track, *args, **kwargs)
        JobRun.objects.update(status=JobRun.Status.STOPPING)
        return result

    from catalog.tasks import downloading as task

    monkeypatch.setattr(task, "download_track", stop_after_first)
    run = _run(track_ids=[first.pk, second.pk])
    assert run.status == JobRun.Status.STOPPED
    assert Download.objects.count() == 1


def test_requires_track_ids_or_all_pending() -> None:
    run = _run()
    assert run.status == JobRun.Status.FAILED


def test_unsupported_format_fails_the_run() -> None:
    Preference.objects.create(key="download.format", value="wav")
    run = _run(all_pending=True)
    assert run.status == JobRun.Status.FAILED


def test_youtube_failure_without_proxies_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> Path:
        raise YoutubeError("blocked")

    monkeypatch.setattr(downloading, "download_audio", boom)
    run = _run(track_ids=[TrackFactory(duration=200).pk])
    assert run.summary["failed"] == 1
