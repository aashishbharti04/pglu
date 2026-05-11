"""Pick a sensible default download folder for the current platform."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_android() -> bool:
    """Detect Android without importing Kivy (Kivy steals sys.argv on import)."""
    # python-for-android sets ANDROID_ARGUMENT and ANDROID_PRIVATE.
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ


def default_download_dir() -> Path:
    """User-Downloads/Pglu on desktop, /sdcard/Download/Pglu on Android."""
    if _is_android():
        try:
            from android.storage import primary_external_storage_path  # type: ignore
            base = Path(primary_external_storage_path()) / "Download" / "Pglu"
        except Exception:
            base = Path("/sdcard/Download/Pglu")
    else:
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
    """Ask for storage perms when running on Android. No-op elsewhere."""
    if not _is_android():
        return
    try:
        from android.permissions import request_permissions, Permission  # type: ignore
        request_permissions([
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.INTERNET,
        ])
    except Exception:
        pass
