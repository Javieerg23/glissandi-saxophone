"""Nombres de fichero y carpetas desde una plantilla. / File and folder names from a template."""

import re
from pathlib import PurePosixPath

from .tags import Tags

DEFAULT_TEMPLATE = "{artist}/{album}/{disc}{track} {title}"
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_PART = 120  # bytes de nombre bien por debajo del límite de 255 de los sistemas de ficheros


def _clean(value: str) -> str:
    """Deja un valor seguro como nombre de una sola carpeta o fichero.

    Makes a value safe as a single folder or file name.
    """
    cleaned = _FORBIDDEN.sub("_", value).strip(" .")
    # Cortar por caracteres, no por bytes, para no partir un carácter multibyte.
    # Cut by characters, not bytes, so a multibyte character is never split.
    while len(cleaned.encode()) > _MAX_PART:
        cleaned = cleaned[:-1]
    return cleaned or "_"


def render_path(template: str, tags: Tags, extension: str) -> PurePosixPath:
    """Construye la ruta relativa de un fichero.

    Builds a file's relative path. Placeholders: ``{artist}``, ``{album}``, ``{title}``,
    ``{track}`` (two digits), ``{disc}`` (``"<n>-"`` only when the disc number is set) and
    ``{year}``. Each value is sanitized, so tags can never add or escape folders.

    Args:
        template: Plantilla con ``/`` entre carpetas. / Template with ``/`` between folders.
        tags: Etiquetas de la canción. / Tags of the track.
        extension: Extensión sin punto. / Extension without the dot.

    Returns:
        Ruta relativa, sin ``..`` ni raíz. / Relative path with no ``..`` or root.

    Raises:
        KeyError: La plantilla usa un marcador desconocido. / Unknown placeholder.
    """
    values = {
        "artist": _clean(", ".join(tags.artists)),
        "album": _clean(tags.album or "Unknown Album"),
        "title": _clean(tags.title),
        "track": f"{tags.track_number:02d}" if tags.track_number else "",
        "disc": f"{tags.disc_number}-" if tags.disc_number else "",
        "year": str(tags.year or ""),
    }
    parts = [_clean(part.format_map(values)) for part in template.split("/") if part]
    parts[-1] = f"{parts[-1]}.{extension}"
    return PurePosixPath(*parts)
