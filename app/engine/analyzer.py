"""Video explainer — sends a short clip to Google Gemini and returns a
plain-language description of what happens in it.

Why a cloud API: vision models are far too large to run on a phone, so the
clip is uploaded to Gemini's REST Files API (generous free tier) and the answer
is shown in the app. Only ``requests`` is used here (already a project
dependency), so there are no extra python-for-android recipes to build — the
APK stays buildable.

Heavy backends (yt_dlp / instaloader) are imported lazily inside the acquisition
helpers, matching the rest of the engine package, so importing this module can
never crash the UI on its own.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable, Optional

import requests

from .common import MediaInfo


GENAI = "https://generativelanguage.googleapis.com"
StatusCallback = Callable[[str], None]

# Fallback model if the live model list can't be fetched. The code prefers the
# newest "flash" model the key actually has access to (see _pick_model).
_DEFAULT_MODEL = "gemini-2.5-flash"

_PROMPT = (
    "You are describing a short social-media video to someone who cannot watch "
    "it. Watch the clip carefully and explain, in simple clear language:\n"
    "1. What is actually happening (the main action or events).\n"
    "2. Who or what is shown, and the setting/location.\n"
    "3. Any important on-screen text, captions, or spoken words.\n"
    "4. The overall point, message, or why someone would share it.\n\n"
    "Keep it to about 120-160 words. Do not invent details you cannot see or "
    "hear. If it is an image rather than a video, describe the image instead."
)


class AnalysisError(Exception):
    """Raised for any failure while explaining a clip (network, API, no key)."""


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def explain_url(
    info: MediaInfo,
    url: str,
    api_key: str,
    cache_dir: Path,
    model: Optional[str] = None,
    on_status: Optional[StatusCallback] = None,
) -> str:
    """Fetch a compact clip for ``url`` and return Gemini's explanation of it.

    ``cache_dir`` is a writable scratch directory; the downloaded clip is
    removed afterwards. Raises AnalysisError on any failure.
    """
    if not (api_key or "").strip():
        raise AnalysisError("No Gemini API key set.")

    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    status("Fetching a clip to analyze...")
    clip_path, mime = _acquire_media(info, url, cache_dir, status)
    try:
        size = clip_path.stat().st_size
        if size > 100 * 1024 * 1024:
            raise AnalysisError(
                "Clip is larger than 100 MB — try a shorter video."
            )

        chosen = _pick_model(api_key, model)
        status("Uploading to Gemini...")
        file_uri, up_mime = _upload_file(clip_path, mime, api_key, status)

        context = _context_text(info)
        status("Analyzing...")
        text = _generate(chosen, file_uri, up_mime, context, api_key)
        return text.strip()
    finally:
        try:
            clip_path.unlink(missing_ok=True)
        except Exception:
            pass


def _context_text(info: MediaInfo) -> str:
    """Append the title/caption so the model has textual context too."""
    bits = [_PROMPT]
    extra = []
    if info.title:
        extra.append(f"Title/caption: {info.title}")
    if info.uploader:
        extra.append(f"Posted by: {info.uploader}")
    if info.description and info.description.strip() != (info.title or "").strip():
        extra.append(f"Description: {info.description[:500]}")
    if extra:
        bits.append("\n\nContext (may help, but rely mainly on the video):\n" + "\n".join(extra))
    return "".join(bits)


# -----------------------------------------------------------------------------
# Media acquisition (no ffmpeg — single progressive stream / direct image)
# -----------------------------------------------------------------------------

def _acquire_media(
    info: MediaInfo,
    url: str,
    cache_dir: Path,
    status: StatusCallback,
) -> tuple[Path, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Images (and carousels we treat via their cover) → send the picture.
    if info.media_type == "image":
        dest = cache_dir / "clip.jpg"
        _download(info.thumbnail_url, dest)
        return dest, "image/jpeg"

    if info.source == "youtube":
        return _youtube_clip(url, cache_dir, status), "video/mp4"

    if info.source == "instagram":
        if info.media_type == "video":
            return _instagram_clip(info, cache_dir), "video/mp4"
        # carousel / anything else → fall back to the cover image
        dest = cache_dir / "clip.jpg"
        _download(info.thumbnail_url, dest)
        return dest, "image/jpeg"

    raise AnalysisError(f"Don't know how to fetch media for source: {info.source}")


def _youtube_clip(url: str, cache_dir: Path, status: StatusCallback) -> Path:
    """Download a single progressive (muxed) stream so no ffmpeg merge is
    needed — keeps it working on Android where ffmpeg isn't bundled. Capped at
    480p to keep the upload small and fast."""
    import yt_dlp  # lazy

    outtmpl = str(cache_dir / "yt_clip.%(ext)s")
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # Prefer a muxed (video+audio in one file) format so we never need to
        # merge. Step down gracefully if a capped one isn't available.
        "format": (
            "best[vcodec!=none][acodec!=none][height<=480]/"
            "best[vcodec!=none][acodec!=none][height<=720]/"
            "best[vcodec!=none][acodec!=none]/best"
        ),
        "outtmpl": outtmpl,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:  # noqa: BLE001
        raise AnalysisError(f"Could not fetch the video: {e}")

    for p in sorted(cache_dir.glob("yt_clip.*")):
        if p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov"):
            return p
    raise AnalysisError("Could not fetch a playable clip for analysis.")


def _instagram_clip(info: MediaInfo, cache_dir: Path) -> Path:
    """Grab the IG video file directly (it's already a single mp4 URL)."""
    from .instagram import InstagramEngine  # lazy

    try:
        eng = InstagramEngine()
        post = _ig_post(eng, info.raw_id)
        dest = cache_dir / "ig_clip.mp4"
        _download(post.video_url, dest)
        return dest
    except AnalysisError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AnalysisError(f"Could not fetch the Instagram video: {e}")


def _ig_post(engine, shortcode: str):
    import instaloader  # lazy
    L = engine._loader()  # reuse the configured loader
    return instaloader.Post.from_shortcode(L.context, shortcode)


def _download(src_url: str, dest: Path) -> Path:
    if not src_url:
        raise AnalysisError("No media URL available to analyze.")
    with requests.get(src_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=256 * 1024):
                if chunk:
                    f.write(chunk)
    return dest


# -----------------------------------------------------------------------------
# Gemini REST: model pick, file upload, generate
# -----------------------------------------------------------------------------

def _pick_model(api_key: str, override: Optional[str]) -> str:
    """Pick the newest 'flash' model the key can use, so we don't hardcode a
    name that may have been retired. Falls back to a sane default offline."""
    if override:
        return override
    try:
        r = requests.get(
            f"{GENAI}/v1beta/models",
            headers={"x-goog-api-key": api_key},
            timeout=30,
        )
        r.raise_for_status()
        names = []
        for m in r.json().get("models", []):
            name = (m.get("name") or "").split("/")[-1]
            methods = m.get("supportedGenerationMethods") or []
            if not name or "generateContent" not in methods:
                continue
            if "flash" in name and "vision" not in name and "thinking" not in name:
                names.append(name)

        def ver(n: str) -> tuple:
            mt = re.search(r"(\d+)\.(\d+)", n)
            base = (int(mt.group(1)), int(mt.group(2))) if mt else (0, 0)
            # Prefer plain "-flash" over "-flash-lite"/"-8b" variants.
            penalty = 1 if re.search(r"flash$", n) else 0
            return (base[0], base[1], penalty)

        names.sort(key=ver, reverse=True)
        if names:
            return names[0]
    except Exception:
        pass
    return _DEFAULT_MODEL


def _upload_file(path: Path, mime: str, api_key: str, status: StatusCallback) -> tuple[str, str]:
    num_bytes = path.stat().st_size

    start = requests.post(
        f"{GENAI}/upload/v1beta/files",
        headers={
            "x-goog-api-key": api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(num_bytes),
            "X-Goog-Upload-Header-Content-Type": mime,
            "Content-Type": "application/json",
        },
        json={"file": {"display_name": "pglu_clip"}},
        timeout=60,
    )
    _raise_for_api(start, "starting upload")
    upload_url = start.headers.get("x-goog-upload-url") or start.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        raise AnalysisError("Gemini did not return an upload URL (check your API key).")

    with open(path, "rb") as f:
        up = requests.post(
            upload_url,
            headers={
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
                "Content-Length": str(num_bytes),
            },
            data=f,
            timeout=600,
        )
    _raise_for_api(up, "uploading file")
    fobj = (up.json() or {}).get("file", {})
    name = fobj.get("name") or ""
    uri = fobj.get("uri") or ""
    up_mime = fobj.get("mimeType") or mime
    state = fobj.get("state") or ""
    if not uri or not name:
        raise AnalysisError("Gemini upload response was missing the file reference.")

    # Videos need processing before they can be used — poll until ACTIVE.
    deadline = time.monotonic() + 180
    while state not in ("ACTIVE", "FAILED") and time.monotonic() < deadline:
        status("Processing the clip on Gemini...")
        time.sleep(2.0)
        g = requests.get(f"{GENAI}/v1beta/{name}", headers={"x-goog-api-key": api_key}, timeout=30)
        if g.status_code == 200:
            state = (g.json() or {}).get("state") or state
    if state == "FAILED":
        raise AnalysisError("Gemini failed to process the clip.")
    if state != "ACTIVE":
        raise AnalysisError("Timed out waiting for Gemini to process the clip.")
    return uri, up_mime


def _generate(model: str, file_uri: str, mime: str, prompt: str, api_key: str) -> str:
    body = {
        "contents": [{
            "parts": [
                {"file_data": {"mime_type": mime, "file_uri": file_uri}},
                {"text": prompt},
            ]
        }],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 800},
    }
    r = requests.post(
        f"{GENAI}/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=300,
    )
    _raise_for_api(r, "analyzing the clip")
    data = r.json() or {}

    candidates = data.get("candidates") or []
    if not candidates:
        fb = data.get("promptFeedback") or {}
        block = fb.get("blockReason")
        if block:
            raise AnalysisError(f"Gemini blocked this content ({block}).")
        raise AnalysisError("Gemini returned no explanation.")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        reason = candidates[0].get("finishReason") or "no text"
        raise AnalysisError(f"Gemini returned an empty answer ({reason}).")
    return text


def _raise_for_api(resp: requests.Response, doing: str) -> None:
    if resp.status_code == 200:
        return
    detail = ""
    try:
        err = resp.json().get("error", {})
        detail = err.get("message", "") or ""
    except Exception:
        detail = (resp.text or "")[:300]
    if resp.status_code in (401, 403):
        raise AnalysisError(f"API key rejected while {doing}: {detail or 'unauthorized'}")
    if resp.status_code == 429:
        raise AnalysisError("Gemini rate limit / quota reached. Try again shortly.")
    raise AnalysisError(f"Gemini error {resp.status_code} while {doing}: {detail}")
