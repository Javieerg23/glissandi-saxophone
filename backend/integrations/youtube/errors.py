"""Errores de la integración con YouTube. / YouTube integration errors."""


class YoutubeError(Exception):
    """Fallo al buscar o descargar con yt-dlp.

    Search or download failure reported by yt-dlp. It hides ``yt_dlp`` types so
    callers do not depend on the library.
    """
