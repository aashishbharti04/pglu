"""Instagram engine — uses instaloader for posts/reels/IGTV/carousels.

Public posts work without login. Private accounts and stories require a
session file (we'll wire up login in a later phase).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import instaloader
import requests

from .common import (
    MediaInfo,
    MediaFormat,
    DownloadJob,
    ProgressEvent,
    ProgressCallback,
    sanitize_filename,
    write_metadata_sidecar,
)


_SHORTCODE_RE = re.compile(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


def extract_shortcode(url: str) -> str:
    """Pull the post shortcode out of any IG post/reel/tv URL."""
    parsed = urlparse(url)
    if "instagram.com" not in (parsed.netloc or ""):
        raise ValueError(f"Not an Instagram URL: {url}")
    m = _SHORTCODE_RE.search(parsed.path or "")
    if not m:
        raise ValueError(f"Could not find a post shortcode in: {url}")
    return m.group(1)


class InstagramEngine:
    """Fetch + download Instagram posts, reels, IGTV, and image carousels."""

    def __init__(self, session_file: Optional[Path] = None, username: Optional[str] = None):
        self.session_file = session_file
        self.username = username
        self._L: Optional[instaloader.Instaloader] = None

    def _loader(self) -> instaloader.Instaloader:
        if self._L is not None:
            return self._L
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
        )
        if self.session_file and self.username and self.session_file.exists():
            try:
                L.load_session_from_file(self.username, str(self.session_file))
            except Exception:
                pass  # Continue anonymously
        self._L = L
        return L

    def fetch_info(self, url: str) -> MediaInfo:
        shortcode = extract_shortcode(url)
        L = self._loader()
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        if post.typename == "GraphSidecar":
            media_type = "carousel"
        elif post.is_video:
            media_type = "video"
        else:
            media_type = "image"

        # Build a single "format" entry — IG gives one source per item.
        formats: list[MediaFormat] = []
        if media_type == "video":
            formats.append(MediaFormat(
                format_id="ig-video",
                label="Original quality MP4 (video)",
                kind="video",
                ext="mp4",
            ))
        elif media_type == "image":
            formats.append(MediaFormat(
                format_id="ig-image",
                label="Original quality JPG (image)",
                kind="image",
                ext="jpg",
            ))
        else:  # carousel — count items
            n_video = 0
            n_image = 0
            for node in post.get_sidecar_nodes():
                if node.is_video:
                    n_video += 1
                else:
                    n_image += 1
            formats.append(MediaFormat(
                format_id="ig-carousel-all",
                label=f"Download all {n_image} image(s) + {n_video} video(s)",
                kind="image" if n_image and not n_video else "video",
                ext="zip",
            ))

        caption = post.caption or ""
        return MediaInfo(
            source="instagram",
            url=url,
            media_type=media_type,
            title=(caption.split("\n", 1)[0][:120] if caption else f"IG post {shortcode}"),
            description=caption,
            tags=list(post.caption_hashtags or []),
            uploader=post.owner_username or "",
            duration=post.video_duration if post.is_video else None,
            thumbnail_url=post.url,  # IG's preview image (works for video & image)
            upload_date=post.date_utc.strftime("%Y%m%d") if post.date_utc else "",
            view_count=getattr(post, "video_view_count", None),
            like_count=post.likes,
            formats=formats,
            raw_id=shortcode,
            extra={
                "typename": post.typename,
                "is_video": post.is_video,
                "comments": post.comments,
                "mentions": list(post.caption_mentions or []),
            },
        )

    def download(
        self,
        job: DownloadJob,
        info: Optional[MediaInfo] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Path:
        info = info or self.fetch_info(job.url)
        job.output_dir.mkdir(parents=True, exist_ok=True)
        L = self._loader()
        post = instaloader.Post.from_shortcode(L.context, info.raw_id)

        safe_title = sanitize_filename(f"{info.uploader}_{info.raw_id}")
        if on_progress:
            on_progress(ProgressEvent(kind="start", message=f"Downloading: {info.title}"))

        final_path: Optional[Path] = None

        if info.media_type == "video":
            final_path = self._download_url(post.video_url, job.output_dir / f"{safe_title}.mp4", on_progress)
        elif info.media_type == "image":
            final_path = self._download_url(post.url, job.output_dir / f"{safe_title}.jpg", on_progress)
        else:  # carousel
            folder = job.output_dir / safe_title
            folder.mkdir(parents=True, exist_ok=True)
            saved = []
            for idx, node in enumerate(post.get_sidecar_nodes(), start=1):
                if on_progress:
                    on_progress(ProgressEvent(
                        kind="progress",
                        percent=0.0,
                        message=f"Item {idx}...",
                    ))
                if node.is_video:
                    p = self._download_url(node.video_url, folder / f"{idx:02d}.mp4", None)
                else:
                    p = self._download_url(node.display_url, folder / f"{idx:02d}.jpg", None)
                if p:
                    saved.append(p)
            final_path = folder
            if on_progress:
                on_progress(ProgressEvent(
                    kind="progress",
                    percent=100.0,
                    message=f"Saved {len(saved)} item(s)",
                ))

        # Always grab the cover thumbnail too (post.url for video posts).
        if job.write_thumbnail and info.thumbnail_url and info.media_type == "video":
            try:
                self._download_url(
                    info.thumbnail_url,
                    job.output_dir / f"{safe_title}.thumb.jpg",
                    None,
                )
            except Exception:
                pass

        if final_path and job.write_metadata_sidecar:
            if final_path.is_file():
                write_metadata_sidecar(info, final_path)
            else:
                # Carousel — drop a single metadata.json inside the folder.
                (final_path / "metadata.json").write_text(
                    json.dumps(info.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

        if on_progress:
            on_progress(ProgressEvent(
                kind="done",
                percent=100.0,
                file_path=str(final_path) if final_path else "",
                message="Done",
            ))
        return final_path

    @staticmethod
    def _download_url(url: str, dest: Path, on_progress: Optional[ProgressCallback]) -> Path:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            written = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    written += len(chunk)
                    if on_progress and total:
                        on_progress(ProgressEvent(
                            kind="progress",
                            percent=written / total * 100.0,
                        ))
        return dest
