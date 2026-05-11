from urllib.parse import urlparse

from .youtube import YouTubeEngine
from .instagram import InstagramEngine
from .common import DownloadJob, ProgressEvent, MediaInfo, MediaFormat


def engine_for(url: str):
    """Pick the right engine for a URL. YouTube is the default fallback."""
    host = (urlparse(url).netloc or "").lower()
    if "instagram.com" in host:
        return InstagramEngine()
    return YouTubeEngine()


__all__ = [
    "YouTubeEngine",
    "InstagramEngine",
    "DownloadJob",
    "ProgressEvent",
    "MediaInfo",
    "MediaFormat",
    "engine_for",
]
