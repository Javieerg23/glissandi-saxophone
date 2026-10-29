"""Errores del paquete de audio. / Errors of the audio package."""


class AudioError(Exception):
    """Error base de audio. / Base audio error."""


class ConversionError(AudioError):
    """ffmpeg falló o no está disponible. / ffmpeg failed or is not available."""


class InvalidAudio(AudioError):
    """El fichero no es un audio aceptable. / The file is not acceptable audio."""
