"""Pick a sensible default download folder for the current platform."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _is_android() -> bool:
    """Detect Android without importing Kivy (Kivy steals sys.argv on import)."""
    # python-for-android sets ANDROID_ARGUMENT and ANDROID_PRIVATE.
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ


def _android_download_base() -> Path:
    """Best-effort path to /sdcard/Download. Falls back to the app's private
    storage if the public dir is not writable (Android 11+ scoped storage)."""
    try:
        from android.storage import primary_external_storage_path  # type: ignore
        return Path(primary_external_storage_path()) / "Download"
    except Exception:
        return Path("/sdcard/Download")


def default_download_dir() -> Path:
    """User-Downloads/Pglu on desktop, /sdcard/Download/Pglu on Android.

    Falls back to the app's private storage if the public location can't be
    created (e.g. permission was denied). Never raises — returns *some*
    writable directory so callers don't have to handle errors.
    """
    if _is_android():
        base = _android_download_base() / "Pglu"
        try:
            base.mkdir(parents=True, exist_ok=True)
            return base
        except Exception:
            # Fall through to private storage.
            try:
                from android.storage import app_storage_path  # type: ignore
                fallback = Path(app_storage_path()) / "Pglu"
            except Exception:
                fallback = Path(os.environ.get("ANDROID_PRIVATE", "/data/local/tmp")) / "Pglu"
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    home = Path(os.path.expanduser("~"))
    for candidate in (home / "Downloads", home):
        if candidate.exists():
            base = candidate / "Pglu"
            break
    else:
        base = home / "Pglu"
    base.mkdir(parents=True, exist_ok=True)
    return base


def request_android_permissions() -> None:
    """Ask for storage perms when running on Android. No-op elsewhere.

    Wraps everything in try/except: a missing ``android`` module or a
    permission name that doesn't exist on the running Android version must
    never crash the app — at worst the user just won't see the prompt.
    """
    if not _is_android():
        return
    try:
        from android.permissions import request_permissions, Permission  # type: ignore
    except Exception:
        return

    wanted: list = []
    # INTERNET is install-time only — not requestable at runtime — skip it.
    for name in (
        "WRITE_EXTERNAL_STORAGE",
        "READ_EXTERNAL_STORAGE",
        "READ_MEDIA_VIDEO",
        "READ_MEDIA_IMAGES",
        "READ_MEDIA_AUDIO",
    ):
        perm = getattr(Permission, name, None)
        if perm is not None:
            wanted.append(perm)
    if not wanted:
        return
    try:
        request_permissions(wanted)
    except Exception:
        pass


def write_crash_log(message: str) -> str:
    """Persist a crash traceback somewhere the user can actually find it.

    Returns the path written to (as a string) so callers can show it on
    screen. Never raises — falls back to /tmp-style locations if needed.
    """
    candidates: list[Path] = []
    if _is_android():
        candidates.append(_android_download_base() / "Pglu")
        try:
            from android.storage import app_storage_path  # type: ignore
            candidates.append(Path(app_storage_path()))
        except Exception:
            pass
        candidates.append(Path("/sdcard/Download/Pglu"))
    else:
        candidates.append(Path(os.path.expanduser("~")) / "Pglu")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    payload = f"[{stamp}] Pglu crash\nsys.executable: {sys.executable}\n\n{message}\n"
    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            log_path = d / "crash.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(payload)
                f.write("\n" + "-" * 60 + "\n")
            return str(log_path)
        except Exception:
            continue
    # Last resort — at least print to stderr.
    try:
        sys.stderr.write(payload)
    except Exception:
        pass
    return "(no writable location)"
