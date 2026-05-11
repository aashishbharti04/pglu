"""YouTube engine — wraps yt-dlp for info fetch and download."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import yt_dlp

from .common import (
    MediaInfo,
    MediaFormat,
    DownloadJob,
    ProgressEvent,
    ProgressCallback,
    sanitize_filename,
    write_metadata_sidecar,
    human_size,
)


def _find_bundled_ffmpeg() -> Optional[str]:
    """Look for ffmpeg shipped next to the PyInstaller exe (Windows build)."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.extend([
            exe_dir,
            exe_dir / "_internal",
        ])
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass))
    # Also check `bin/` next to the project root (useful in dev).
    candidates.append(Path(__file__).resolve().parent.parent.parent / "bin")
    for d in candidates:
        ff = d / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if ff.exists():
            return str(ff)
    return None


def _classify_format(f: dict) -> Optional[MediaFormat]:
    """Convert a raw yt-dlp format dict into our MediaFormat, or None to skip."""
    vcodec = f.get("vcodec") or "none"
    acodec = f.get("acodec") or "none"
    ext = f.get("ext") or ""
    fmt_id = f.get("format_id") or ""
    if not fmt_id:
        return None

    height = f.get("height")
    fps = f.get("fps")
    abr = f.get("abr")
    size = f.get("filesize") or f.get("filesize_approx")

    if vcodec != "none" and acodec != "none":
        kind = "video"
        label = f"{height or '?'}p {ext.upper()} (video+audio)"
    elif vcodec != "none":
        kind = "video"
        label = f"{height or '?'}p {ext.upper()} (video only)"
    elif acodec != "none":
        kind = "audio"
        label = f"{int(abr) if abr else '?'}k {ext.upper()} (audio only)"
    else:
        return None

    if size:
        label += f" ~ {human_size(size)}"
    if fps and fps > 30 and kind == "video":
        label += f" {fps}fps"

    return MediaFormat(
        format_id=fmt_id,
        label=label,
        kind=kind,
        ext=ext,
        height=height,
        fps=int(fps) if fps else None,
        abr=abr,
        filesize=size,
        note=f.get("format_note", "") or "",
    )


class YouTubeEngine:
    """Fetch info + download from YouTube (and any yt-dlp-supported site)."""

    def __init__(self, cookies_file: Optional[Path] = None):
        self.cookies_file = cookies_file

    def _base_opts(self) -> dict:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # Don't fail info extraction if a particular client returned no
            # streams — we still want the merged metadata + format list.
            "ignore_no_formats_error": True,
        }
        if self.cookies_file and self.cookies_file.exists():
            opts["cookiefile"] = str(self.cookies_file)
        return opts

    def fetch_info(self, url: str) -> MediaInfo:
        with yt_dlp.YoutubeDL(self._base_opts()) as ydl:
            raw = ydl.extract_info(url, download=False)

        if raw is None:
            raise RuntimeError("yt-dlp returned no info for this URL")

        # Playlist → represent as the first entry plus a note (downloads handle list separately)
        if raw.get("_type") == "playlist":
            entries = raw.get("entries") or []
            if not entries:
                raise RuntimeError("Playlist is empty")
            primary = entries[0]
            media_type = "playlist"
        else:
            primary = raw
            media_type = "video"

        formats = []
        for f in primary.get("formats") or []:
            mf = _classify_format(f)
            if mf:
                formats.append(mf)

        # Sort: video desc by height, then audio desc by abr
        formats.sort(
            key=lambda f: (
                0 if f.kind == "video" else 1,
                -(f.height or 0),
                -(f.abr or 0),
            )
        )

        return MediaInfo(
            source="youtube",
            url=url,
            media_type=media_type,
            title=primary.get("title", "") or "",
            description=primary.get("description", "") or "",
            tags=list(primary.get("tags") or []),
            uploader=primary.get("uploader") or primary.get("channel") or "",
            duration=primary.get("duration"),
            thumbnail_url=primary.get("thumbnail") or "",
            upload_date=primary.get("upload_date", "") or "",
            view_count=primary.get("view_count"),
            like_count=primary.get("like_count"),
            formats=formats,
            raw_id=primary.get("id", "") or "",
            extra={
                "categories": primary.get("categories") or [],
                "channel_url": primary.get("channel_url") or "",
                "webpage_url": primary.get("webpage_url") or url,
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

        safe_title = sanitize_filename(info.title or info.raw_id or "youtube_download")
        outtmpl = str(job.output_dir / f"{safe_title}.%(ext)s")

        def _hook(d: dict) -> None:
            if not on_progress:
                return
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total * 100.0) if total else 0.0
                on_progress(ProgressEvent(
                    kind="progress",
                    percent=pct,
                    speed=d.get("_speed_str", "") or "",
                    eta=d.get("_eta_str", "") or "",
                ))
            elif status == "finished":
                on_progress(ProgressEvent(
                    kind="progress",
                    percent=100.0,
                    message="Merging / post-processing...",
                ))

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "outtmpl": outtmpl,
            "progress_hooks": [_hook],
            "writethumbnail": job.write_thumbnail,
            "postprocessors": [],
            "merge_output_format": "mp4",
        }
        bundled_ffmpeg = _find_bundled_ffmpeg()
        if bundled_ffmpeg:
            opts["ffmpeg_location"] = bundled_ffmpeg
        if self.cookies_file and self.cookies_file.exists():
            opts["cookiefile"] = str(self.cookies_file)

        if job.audio_only:
            opts["format"] = job.format_id or "bestaudio/best"
            opts["postprocessors"].append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })
        else:
            if job.format_id:
                # If user picked a video-only format, ensure audio gets merged in.
                opts["format"] = f"{job.format_id}+bestaudio/best"
            else:
                opts["format"] = "bestvideo+bestaudio/best"

        if job.write_thumbnail:
            opts["postprocessors"].append({
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg",
            })

        if on_progress:
            on_progress(ProgressEvent(kind="start", message=f"Downloading: {info.title}"))

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.extract_info(job.url, download=True)
            final_path = self._guess_final_path(job.output_dir, safe_title, job.audio_only)
        except Exception as e:
            if on_progress:
                on_progress(ProgressEvent(kind="error", message=str(e)))
            raise

        if final_path and job.write_metadata_sidecar:
            write_metadata_sidecar(info, final_path)

        if on_progress:
            on_progress(ProgressEvent(
                kind="done",
                percent=100.0,
                file_path=str(final_path) if final_path else "",
                message="Done",
            ))
        return final_path

    @staticmethod
    def _guess_final_path(out_dir: Path, stem: str, audio_only: bool) -> Optional[Path]:
        # Prefer mp3 for audio, then mp4 for video, otherwise any matching stem.
        prefs = [".mp3"] if audio_only else [".mp4", ".mkv", ".webm"]
        for ext in prefs:
            p = out_dir / f"{stem}{ext}"
            if p.exists():
                return p
        # Fallback: any file starting with the stem
        for p in out_dir.glob(f"{stem}.*"):
            if p.suffix.lower() not in {".json", ".jpg", ".webp", ".png", ".part"}:
                return p
        return None
