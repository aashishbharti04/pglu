"""Entry point used by both `python main.py` (desktop) and Buildozer (Android).

Add `--web` to launch the FastAPI dashboard instead of the Kivy desktop UI:
    python main.py            # desktop Kivy window
    python main.py --web      # local web dashboard at http://127.0.0.1:8765
    python main.py --web --host 0.0.0.0 --port 8765   # phone-on-Wi-Fi access
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path


def _ensure_std_streams() -> None:
    """PyInstaller's windowed mode sets sys.stdout/stderr to None — uvicorn's
    logger then crashes on `None.isatty()`. Wire each missing stream to a
    log file next to the exe so the server can boot and users can see errors.
    """
    needs_patch = sys.stdout is None or sys.stderr is None
    if not needs_patch:
        return
    log_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    try:
        log_path = log_dir / "pglu-web.log"
        f = open(log_path, "a", encoding="utf-8", buffering=1)
    except OSError:
        f = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f


def _run_web() -> None:
    _ensure_std_streams()
    # Filter out the --web flag, leave the rest for the web server's argparse.
    sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--web"]
    from app.web.server import main as web_main
    web_main()


def main() -> None:
    if "--web" in sys.argv:
        _run_web()
        return
    from app.ui.main import main as desktop_main
    desktop_main()


if __name__ == "__main__":
    main()
