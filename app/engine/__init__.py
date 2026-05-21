"""Engine package — picks the right backend for a given URL.

Top-level imports are kept light on purpose: importing this package must NOT
pull in yt-dlp or instaloader. On Android those imports can fail (transitive
deps that aren't compiled by python-for-android) and we don't want that to
crash the whole UI before the user sees anything. Engines are loaded lazily
inside ``engine_for`` instead.
"""
from urllib.parse import urlparse

from .common import DownloadJob, ProgressEvent, MediaInfo, MediaFormat


def engine_for(url: str):
    """Pick the right engine for a URL. YouTube is the default fallback."""
    host = (urlparse(url).netloc or "").lower()
    if "instagram.com" in host:
        from .instagram import InstagramEngine
        return InstagramEngine()
    from .youtube import YouTubeEngine
    return YouTubeEngine()


__all__ = [
    "DownloadJob",
    "ProgressEvent",
    "MediaInfo",
    "MediaFormat",
    "engine_for",
]
