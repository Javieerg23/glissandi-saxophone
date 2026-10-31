"""Tests de la plantilla de nombres. / Tests for the naming template."""

from pathlib import PurePosixPath

import pytest

from integrations.audio import DEFAULT_TEMPLATE, Tags, render_path

TAGS = Tags(
    title="Song", artists=("A", "B"), album="Album", track_number=3, disc_number=1, year=2001
)


def test_default_template() -> None:
    assert render_path(DEFAULT_TEMPLATE, TAGS, "mp3") == PurePosixPath("A, B/Album/1-03 Song.mp3")


def test_year_and_custom_template() -> None:
    assert render_path("{year}/{title}", TAGS, "flac") == PurePosixPath("2001/Song.flac")


def test_missing_optionals() -> None:
    tags = Tags(title="Song", artists=("A",))
    assert render_path(DEFAULT_TEMPLATE, tags, "mp3") == PurePosixPath("A/Unknown Album/Song.mp3")


def test_tags_cannot_add_or_escape_folders() -> None:
    tags = Tags(title="../../etc/passwd", artists=("AC/DC",), album="..")
    path = render_path("{artist}/{album}/{title}", tags, "mp3")
    assert path.parts == ("AC_DC", "_", "_.._etc_passwd.mp3")


def test_empty_value_and_empty_template_parts() -> None:
    tags = Tags(title="???", artists=("A",))
    assert render_path("//{title}", tags, "mp3") == PurePosixPath("___.mp3")
    assert render_path("{title}", Tags(title=" . ", artists=("A",)), "mp3") == PurePosixPath(
        "_.mp3"
    )


def test_long_names_are_cut_without_splitting_characters() -> None:
    tags = Tags(title="ñ" * 200, artists=("A",))
    name = render_path("{title}", tags, "mp3").stem
    assert len(name.encode()) <= 120 and set(name) == {"ñ"}


def test_unknown_placeholder() -> None:
    with pytest.raises(KeyError):
        render_path("{nope}", TAGS, "mp3")


@pytest.mark.parametrize(("length", "kept"), [(120, 120), (121, 120)])
def test_names_are_cut_at_exactly_120_bytes(length: int, kept: int) -> None:
    name = render_path("{title}", Tags(title="a" * length, artists=("A",)), "mp3").stem
    assert name == "a" * kept


def test_only_spaces_and_dots_are_trimmed() -> None:
    tags = Tags(title="Malcolm X", artists=("A",))
    assert render_path("{title}", tags, "mp3") == PurePosixPath("Malcolm X.mp3")
