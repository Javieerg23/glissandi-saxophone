"""Conversión de audio y etiquetado. / Audio conversion and tagging."""

from .convert import FORMATS, convert
from .errors import AudioError, ConversionError, InvalidAudio
from .naming import DEFAULT_TEMPLATE, render_path
from .tags import Tags, write_tags
from .validate import AudioInfo, validate_audio

__all__ = [
    "DEFAULT_TEMPLATE",
    "FORMATS",
    "AudioError",
    "AudioInfo",
    "ConversionError",
    "InvalidAudio",
    "Tags",
    "convert",
    "render_path",
    "validate_audio",
    "write_tags",
]
