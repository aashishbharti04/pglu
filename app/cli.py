"""Tiny CLI for smoke-testing the engine on Windows before the GUI.

Usage:
    python -m app.cli info <url>
    python -m app.cli download <url> [--audio] [--format=ID] [--out=DIR]
"""
from __future__ import annotations

import sys
from pathlib import Path

# Force UTF-8 on Windows so we can print emojis & non-Latin titles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.engine import DownloadJob, ProgressEvent, engine_for


def _print_progress(ev: ProgressEvent) -> None:
    if ev.kind == "start":
        print(f"[start] {ev.message}")
    elif ev.kind == "progress":
        bar = "#" * int(ev.percent / 5)
        print(f"\r[{bar:<20}] {ev.percent:5.1f}% {ev.speed} ETA {ev.eta} {ev.message}",
              end="", flush=True)
    elif ev.kind == "done":
        print(f"\n[done] {ev.file_path}")
    elif ev.kind == "error":
        print(f"\n[error] {ev.message}")


def cmd_info(url: str) -> int:
    eng = engine_for(url)
    info = eng.fetch_info(url)
    print(f"Source     : {info.source}")
    print(f"Type       : {info.media_type}")
    print(f"Title      : {info.title}")
    print(f"Uploader   : {info.uploader}")
    print(f"Duration   : {info.duration}")
    print(f"Thumbnail  : {info.thumbnail_url}")
    print(f"Tags       : {', '.join(info.tags[:10])}{'...' if len(info.tags) > 10 else ''}")
    print(f"Description: {(info.description or '')[:200]}")
    print(f"Formats ({len(info.formats)}):")
    for f in info.formats[:25]:
        print(f"  - [{f.format_id:>6}] {f.label}")
    if len(info.formats) > 25:
        print(f"  ... and {len(info.formats) - 25} more")
    return 0


def cmd_download(url: str, *, audio: bool, format_id: str | None, out: Path) -> int:
    eng = engine_for(url)
    info = eng.fetch_info(url)
    print(f"-> {info.title}")
    job = DownloadJob(url=url, output_dir=out, audio_only=audio, format_id=format_id)
    final = eng.download(job, info=info, on_progress=_print_progress)
    print(f"Saved: {final}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, url, *rest = argv[1:] + [""]
    if cmd == "info":
        return cmd_info(url)
    if cmd == "download":
        audio = "--audio" in rest
        fmt = next((a.split("=", 1)[1] for a in rest if a.startswith("--format=")), None)
        out = Path(next((a.split("=", 1)[1] for a in rest if a.startswith("--out=")), "downloads"))
        return cmd_download(url, audio=audio, format_id=fmt, out=out)
    print(f"Unknown command: {cmd}")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
