"""Tests de las etiquetas. / Tests for tagging."""

import base64
from pathlib import Path

import mutagen
import pytest
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus

from integrations.audio import AudioError, Tags, convert, write_tags

JPEG = b"\xff\xd8\xff\xe0jpeg"
PNG = b"\x89PNG\r\n\x1a\npng"
FULL = Tags(
    title="Song",
    artists=("A", "B"),
    album="Album",
    track_number=3,
    disc_number=2,
    year=1999,
    isrc="USRC17607839",
    cover=JPEG,
)
MINIMAL = Tags(title="Song", artists=("A",))


def _make(wav: Path, tmp_path: Path, fmt: str) -> Path:
    return convert(wav, tmp_path, fmt, stem="t")


def test_mp3_full(wav: Path, tmp_path: Path) -> None:
    path = _make(wav, tmp_path, "mp3")
    write_tags(path, FULL)
    id3 = ID3(path)
    assert id3["TIT2"].text == ["Song"]
    assert id3["TPE1"].text == ["A", "B"]
    assert id3["TALB"].text == ["Album"]
    assert id3["TRCK"].text == ["3"]
    assert id3["TPOS"].text == ["2"]
    assert str(id3["TDRC"].text[0]) == "1999"
    assert id3["TSRC"].text == ["USRC17607839"]
    assert (id3["APIC:Cover"].mime, id3["APIC:Cover"].type, id3["APIC:Cover"].data) == (
        "image/jpeg",
        3,
        JPEG,
    )
    # UTF-8 en todos los marcos de texto: algunos reproductores no leen bien UTF-16.
    assert {frame.encoding for frame in id3.values()} == {3}


def test_mp3_minimal_replaces_previous_cover(wav: Path, tmp_path: Path) -> None:
    path = _make(wav, tmp_path, "mp3")
    write_tags(path, FULL)
    write_tags(path, Tags(title="Song", artists=("A",), cover=PNG))
    id3 = ID3(path)
    assert id3["APIC:Cover"].mime == "image/png"
    assert "TALB" in id3  # no se borra lo anterior de ID3; solo se sustituye la portada


def test_flac_full_and_minimal(wav: Path, tmp_path: Path) -> None:
    path = _make(wav, tmp_path, "flac")
    write_tags(path, FULL)
    flac = FLAC(path)
    assert flac["artist"] == ["A", "B"]
    assert flac["isrc"] == ["USRC17607839"]
    assert flac["tracknumber"] == ["3"] and flac["discnumber"] == ["2"] and flac["date"] == ["1999"]
    assert flac["album"] == ["Album"]
    assert (flac.pictures[0].mime, flac.pictures[0].type) == ("image/jpeg", 3)
    write_tags(path, MINIMAL)
    flac = FLAC(path)
    assert flac["title"] == ["Song"] and "album" not in flac and not flac.pictures
    assert not {"tracknumber", "discnumber", "date", "isrc"} & set(flac.keys())


def test_opus_full_and_minimal(wav: Path, tmp_path: Path) -> None:
    path = _make(wav, tmp_path, "opus")
    write_tags(path, FULL)
    opus = OggOpus(path)
    assert opus["artist"] == ["A", "B"]
    picture = Picture(base64.b64decode(opus["metadata_block_picture"][0]))
    assert picture.data == JPEG
    write_tags(path, MINIMAL)
    assert "metadata_block_picture" not in OggOpus(path)


def test_m4a_full_and_minimal(wav: Path, tmp_path: Path) -> None:
    path = _make(wav, tmp_path, "m4a")
    write_tags(path, Tags(**{**FULL.__dict__, "cover": PNG}))
    mp4 = MP4(path)
    assert mp4["\xa9ART"] == ["A, B"]
    assert mp4["trkn"] == [(3, 0)] and mp4["disk"] == [(2, 0)] and mp4["\xa9day"] == ["1999"]
    assert bytes(mp4["----:com.apple.iTunes:ISRC"][0]) == b"USRC17607839"
    assert mp4["covr"][0].imageformat == mp4["covr"][0].FORMAT_PNG
    write_tags(path, Tags(**{**FULL.__dict__, "cover": JPEG}))
    assert MP4(path)["covr"][0].imageformat == MP4(path)["covr"][0].FORMAT_JPEG
    write_tags(path, MINIMAL)
    assert "covr" not in MP4(path)


def test_untagged_file_gets_tags_without_prior_header(wav: Path, tmp_path: Path) -> None:
    path = _make(wav, tmp_path, "mp3")
    ID3(path).delete()
    write_tags(path, MINIMAL)
    assert mutagen.File(path).tags["TIT2"].text == ["Song"]


def test_unsupported_extension(wav: Path) -> None:
    with pytest.raises(AudioError):
        write_tags(wav, MINIMAL)
    with pytest.raises(AudioError, match="without extension"):
        write_tags(wav.with_suffix(""), MINIMAL)
