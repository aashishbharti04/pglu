"""Shared types and helpers for the download engine."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Literal, Optional
import json
import re

ProgressKind = Literal["start", "progress", "done", "error"]


@dataclass
class ProgressEvent:
    kind: ProgressKind
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    message: str = ""
    file_path: Optional[str] = None


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass
class MediaFormat:
    """One selectable quality option shown to the user."""
    format_id: str
    label: str             # human-readable, e.g. "1080p MP4 (video)" or "128k MP3 (audio)"
    kind: Literal["video", "audio", "image"]
    ext: str
    height: Optional[int] = None
    fps: Optional[int] = None
    abr: Optional[float] = None
    filesize: Optional[int] = None
    note: str = ""


@dataclass
class MediaInfo:
    """Everything we know about a URL before download."""
    source: Literal["youtube", "instagram"]
    url: str
    media_type: Literal["video", "image", "carousel", "audio", "playlist"]
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    uploader: str = ""
    duration: Optional[float] = None
    thumbnail_url: str = ""
    upload_date: str = ""
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    formats: list[MediaFormat] = field(default_factory=list)
    raw_id: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class DownloadJob:
    """A request to download something."""
    url: str
    output_dir: Path
    format_id: Optional[str] = None      # picked from MediaInfo.formats
    audio_only: bool = False
    write_metadata_sidecar: bool = True
    write_thumbnail: bool = True


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Make a string safe for use as a filename on Windows + Android."""
    name = _INVALID_FILENAME_CHARS.sub("_", name).strip()
    name = re.sub(r"\s+", " ", name)
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or "download"


def write_metadata_sidecar(info: MediaInfo, file_path: Path) -> Path:
    """Write a .json file next to the downloaded media with all metadata."""
    sidecar = file_path.with_suffix(file_path.suffix + ".json")
    payload = info.to_dict()
    payload["downloaded_file"] = file_path.name
    sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return sidecar


def human_size(n: Optional[int]) -> str:
    if not n:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f} {u}"
        f /= 1024
    return f"{n} B"
