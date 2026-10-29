"""Integración con YouTube (yt-dlp). / YouTube (yt-dlp) integration."""

from integrations.youtube.client import (
    DownloadProgress,
    VideoMatch,
    download_audio,
    find_best_video,
    preview_embed_url,
)
from integrations.youtube.errors import YoutubeError
from integrations.youtube.proxies import NoProxyAvailable, ProxyPool

__all__ = [
    "DownloadProgress",
    "NoProxyAvailable",
    "ProxyPool",
    "VideoMatch",
    "YoutubeError",
    "download_audio",
    "find_best_video",
    "preview_embed_url",
]
