"""Etiquetas de audio con mutagen. / Audio tags with mutagen."""

import base64
from dataclasses import dataclass
from pathlib import Path

from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPOS, TRCK, TSRC, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm
from mutagen.oggopus import OggOpus

from .errors import AudioError

_PNG = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class Tags:
    """Etiquetas de una canción. / Tags of a track."""

    title: str
    artists: tuple[str, ...]
    album: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    isrc: str | None = None
    cover: bytes | None = None  # JPEG o PNG / JPEG or PNG


def _mime(cover: bytes) -> str:
    return "image/png" if cover.startswith(_PNG) else "image/jpeg"


def _picture(cover: bytes) -> Picture:
    picture = Picture()
    picture.type = 3  # portada frontal / front cover
    picture.mime = _mime(cover)
    picture.data = cover
    return picture


def _vorbis(tags: Tags) -> dict[str, list[str]]:
    """Campos de Vorbis comment, comunes a FLAC y Opus. / Vorbis comment fields."""
    fields = {
        "title": [tags.title],
        "artist": list(tags.artists),
        "album": [tags.album] if tags.album else [],
        "tracknumber": [str(tags.track_number)] if tags.track_number else [],
        "discnumber": [str(tags.disc_number)] if tags.disc_number else [],
        "date": [str(tags.year)] if tags.year else [],
        "isrc": [tags.isrc] if tags.isrc else [],
    }
    return {key: value for key, value in fields.items() if value}


def _write_mp3(path: Path, tags: Tags) -> None:
    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()
    id3.delall("APIC")
    id3.add(TIT2(encoding=3, text=[tags.title]))
    id3.add(TPE1(encoding=3, text=list(tags.artists)))
    if tags.album:
        id3.add(TALB(encoding=3, text=[tags.album]))
    if tags.track_number:
        id3.add(TRCK(encoding=3, text=[str(tags.track_number)]))
    if tags.disc_number:
        id3.add(TPOS(encoding=3, text=[str(tags.disc_number)]))
    if tags.year:
        id3.add(TDRC(encoding=3, text=[str(tags.year)]))
    if tags.isrc:
        id3.add(TSRC(encoding=3, text=[tags.isrc]))
    if tags.cover:
        id3.add(APIC(encoding=3, mime=_mime(tags.cover), type=3, desc="Cover", data=tags.cover))
    id3.save(path)


def _write_flac(path: Path, tags: Tags) -> None:
    flac = FLAC(path)
    flac.clear()
    flac.clear_pictures()
    flac.update(_vorbis(tags))
    if tags.cover:
        flac.add_picture(_picture(tags.cover))
    flac.save()


def _write_opus(path: Path, tags: Tags) -> None:
    opus = OggOpus(path)
    opus.clear()
    opus.update(_vorbis(tags))
    if tags.cover:
        # Ogg no tiene bloque de imagen propio: va en base64 dentro del comentario.
        # Ogg has no picture block: it travels base64-encoded inside a comment.
        opus["metadata_block_picture"] = [
            base64.b64encode(_picture(tags.cover).write()).decode("ascii")
        ]
    opus.save()


def _write_m4a(path: Path, tags: Tags) -> None:
    mp4 = MP4(path)
    mp4.clear()
    mp4["\xa9nam"] = [tags.title]
    mp4["\xa9ART"] = [", ".join(tags.artists)]
    if tags.album:
        mp4["\xa9alb"] = [tags.album]
    if tags.track_number:
        mp4["trkn"] = [(tags.track_number, 0)]
    if tags.disc_number:
        mp4["disk"] = [(tags.disc_number, 0)]
    if tags.year:
        mp4["\xa9day"] = [str(tags.year)]
    if tags.isrc:
        mp4["----:com.apple.iTunes:ISRC"] = [MP4FreeForm(tags.isrc.encode("utf-8"))]
    if tags.cover:
        fmt = MP4Cover.FORMAT_PNG if tags.cover.startswith(_PNG) else MP4Cover.FORMAT_JPEG
        mp4["covr"] = [MP4Cover(tags.cover, imageformat=fmt)]
    mp4.save()


_WRITERS = {".mp3": _write_mp3, ".flac": _write_flac, ".opus": _write_opus, ".m4a": _write_m4a}


def write_tags(path: Path, tags: Tags) -> None:
    """Sustituye las etiquetas del fichero por ``tags``.

    Replaces the file's tags with ``tags``.

    Args:
        path: Fichero mp3, flac, opus o m4a. / An mp3, flac, opus or m4a file.
        tags: Etiquetas a escribir. / Tags to write.

    Raises:
        AudioError: Extensión no soportada. / Unsupported extension.
    """
    writer = _WRITERS.get(path.suffix.lower())
    if writer is None:
        raise AudioError(f"cannot tag {path.suffix or 'a file without extension'}")
    writer(path, tags)
