"""Pglu web dashboard — FastAPI server + single-page UI.

Run with:
    py -3.12 -m app.web.server  [--host 0.0.0.0] [--port 8765]

Then open http://localhost:8765 in any browser. If you bind 0.0.0.0 you can also
hit it from your phone on the same Wi-Fi.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles

from app.engine import DownloadJob, ProgressEvent, MediaInfo, engine_for
from app.ui.storage import default_download_dir


STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# In-memory job tracking. Each download gets a job_id; clients subscribe to
# its progress via SSE. Buffered events are kept in a deque so a late
# subscriber (e.g. from a tab refresh) still gets recent updates.
# -----------------------------------------------------------------------------

class JobTracker:
    def __init__(self) -> None:
        self.events: dict[str, deque[ProgressEvent]] = defaultdict(lambda: deque(maxlen=512))
        self.subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self.completed: dict[str, str] = {}  # job_id -> file path
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def emit(self, job_id: str, ev: ProgressEvent) -> None:
        """Called from a worker thread — schedules fan-out on the event loop."""
        with self._lock:
            self.events[job_id].append(ev)
            if ev.kind == "done" and ev.file_path:
                self.completed[job_id] = ev.file_path
            subs = list(self.subscribers[job_id])

        if self._loop is None:
            return

        def _fanout():
            for q in subs:
                try:
                    q.put_nowait(ev)
                except asyncio.QueueFull:
                    pass

        try:
            self._loop.call_soon_threadsafe(_fanout)
        except RuntimeError:
            # Loop closed (e.g. server shutdown) - drop the event.
            pass

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        with self._lock:
            # Replay buffered events so the client doesn't miss "start" / progress.
            for ev in list(self.events[job_id]):
                await q.put(ev)
            self.subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        with self._lock:
            try:
                self.subscribers[job_id].remove(q)
            except ValueError:
                pass
            # Drop buffered state once a finished job has no more listeners,
            # so a long-running server doesn't grow unbounded.
            if not self.subscribers[job_id]:
                last = self.events[job_id][-1] if self.events[job_id] else None
                if last and last.kind in ("done", "error"):
                    self.events.pop(job_id, None)
                    self.subscribers.pop(job_id, None)


tracker = JobTracker()


# -----------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    tracker.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Pglu", version="0.1.0", lifespan=_lifespan)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


# Static for any future assets (icons, css extracted, etc.)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------- API ----------------

@app.post("/api/info")
async def api_info(payload: dict) -> JSONResponse:
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")
    engine = engine_for(url)
    try:
        info: MediaInfo = await asyncio.to_thread(engine.fetch_info, url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))
    return JSONResponse(info.to_dict())


@app.post("/api/download")
async def api_download(payload: dict) -> JSONResponse:
    url = (payload.get("url") or "").strip()
    format_id = payload.get("format_id") or None
    audio_only = bool(payload.get("audio_only"))
    if not url:
        raise HTTPException(status_code=400, detail="Missing 'url'")

    job_id = uuid.uuid4().hex[:12]
    out_dir = default_download_dir()

    def _runner() -> None:
        try:
            engine = engine_for(url)
            info = engine.fetch_info(url)
            job = DownloadJob(
                url=url,
                output_dir=out_dir,
                format_id=format_id,
                audio_only=audio_only,
            )
            engine.download(
                job,
                info=info,
                on_progress=lambda ev: tracker.emit(job_id, ev),
            )
        except Exception as e:  # noqa: BLE001
            tracker.emit(job_id, ProgressEvent(kind="error", message=str(e)))

    threading.Thread(target=_runner, daemon=True).start()
    return JSONResponse({"job_id": job_id})


@app.get("/api/progress/{job_id}")
async def api_progress(job_id: str, request: Request) -> StreamingResponse:
    """Server-Sent Events stream of progress for a job."""
    queue = await tracker.subscribe(job_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(asdict(ev), ensure_ascii=False)}\n\n"
                if ev.kind in ("done", "error"):
                    break
        finally:
            tracker.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/downloads")
async def api_downloads() -> JSONResponse:
    out = default_download_dir()
    items = []
    for p in sorted(out.rglob("*"), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
        if not p.is_file() or p.suffix.lower() == ".part":
            continue
        rel = p.relative_to(out)
        items.append({
            "name": p.name,
            "rel": str(rel).replace("\\", "/"),
            "size": p.stat().st_size,
            "mtime": int(p.stat().st_mtime),
        })
    return JSONResponse({"dir": str(out), "files": items[:500]})


@app.get("/api/file")
async def api_file(rel: str = Query(..., min_length=1)) -> FileResponse:
    out = default_download_dir().resolve()
    target = (out / rel).resolve()
    # Path-traversal guard: must stay inside the downloads dir.
    if not str(target).startswith(str(out)):
        raise HTTPException(status_code=400, detail="Bad path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target), filename=target.name)


# -----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Pglu web dashboard")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind address. Use 0.0.0.0 to allow phone-on-same-Wi-Fi access.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev).")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "app.web.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
