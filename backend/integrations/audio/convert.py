"""Conversión de audio con ffmpeg. / Audio conversion with ffmpeg."""

import subprocess  # noqa: S404  # se llama con lista de argumentos, nunca con shell
from pathlib import Path

from .errors import ConversionError

# Formato -> (extensión, argumentos del códec).
# Format -> (extension, codec arguments).
FORMATS: dict[str, tuple[str, tuple[str, ...]]] = {
    "mp3": ("mp3", ("-c:a", "libmp3lame", "-b:a", "320k")),
    "m4a": ("m4a", ("-c:a", "aac", "-b:a", "256k")),
    "flac": ("flac", ("-c:a", "flac")),
    "opus": ("opus", ("-c:a", "libopus", "-b:a", "160k")),
}

DEFAULT_TIMEOUT = 600.0


def convert(
    source: Path,
    dest_dir: Path,
    fmt: str,
    *,
    stem: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Path:
    """Convierte ``source`` al formato ``fmt`` dentro de ``dest_dir``.

    Converts ``source`` to ``fmt`` inside ``dest_dir``. The original is kept.

    Args:
        source: Fichero de entrada. / Input file.
        dest_dir: Carpeta de salida, debe existir. / Output folder, must exist.
        fmt: Una clave de ``FORMATS``. / A key of ``FORMATS``.
        stem: Nombre sin extensión; por defecto el del origen.
            Name without extension; defaults to the source's.
        timeout: Segundos máximos de ffmpeg. / Maximum seconds for ffmpeg.

    Returns:
        Ruta del fichero convertido. / Path of the converted file.

    Raises:
        ConversionError: Formato desconocido, ffmpeg ausente, fallo o tiempo agotado.
            Unknown format, missing ffmpeg, failure or timeout.
    """
    if fmt not in FORMATS:
        raise ConversionError(f"unsupported format: {fmt}")
    extension, codec = FORMATS[fmt]
    dest = dest_dir / f"{stem or source.stem}.{extension}"
    if dest == source:
        raise ConversionError("source and destination are the same file")
    # -vn y -map_metadata -1: solo el audio, sin portadas ni etiquetas heredadas del origen.
    # -vn and -map_metadata -1: audio only, no cover or tags inherited from the source.
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(source), "-vn",
           "-map_metadata", "-1", *codec, str(dest)]  # fmt: skip
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ConversionError(str(exc)) from exc
    if result.returncode != 0:
        dest.unlink(missing_ok=True)
        raise ConversionError(result.stderr.strip() or f"ffmpeg exited with {result.returncode}")
    return dest
