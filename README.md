# Pglu

YouTube + Instagram downloader — videos, audio, images in any quality, with
full metadata (title, description, tags, thumbnail). Three frontends, one
engine.

## What's in here

| Frontend | Where | Run with |
|---|---|---|
| **Windows .exe** | `dist/Pglu/Pglu.exe` | Double-click |
| **Web dashboard** | browser at `http://localhost:8765` | `Pglu.exe --web`, or the `.bat` shortcuts |
| **Android APK** | (built via WSL or GitHub Actions) | sideload onto phone |
| **Engine CLI** | `app/cli.py` | `py -3.14 -m app.cli info <url>` |

| Layer | Where | What it does |
|---|---|---|
| Engine | `app/engine/` | yt-dlp + instaloader wrappers, returns format ladder + metadata |
| Desktop UI | `app/ui/` | Kivy app (also the basis for the Android APK) |
| Web UI | `app/web/` | FastAPI + single-page HTML dashboard with SSE progress |
| Build | `pglu.spec`, `buildozer.spec`, `scripts/`, `.github/workflows/` | PyInstaller exe + Buildozer APK + GitHub Actions cloud build |

Downloads land in `~/Downloads/Pglu/` on desktop and
`/sdcard/Download/Pglu/` on Android. Each download writes:

- the media file (`Title.mp4`, `Title.mp3`, `Title.jpg`, ...)
- a thumbnail JPG next to it
- a `.json` sidecar with the full metadata

## Run on Windows

### Option 1: prebuilt .exe (recommended)

Unzip `builds/Pglu-Windows.zip` anywhere, then double-click one of:

- `Pglu - Desktop.bat` — opens the Kivy GUI window.
- `Pglu - Web Dashboard.bat` — starts the web server on `127.0.0.1:8765`. Open the URL in any browser.
- `Pglu - Web Dashboard (LAN).bat` — starts on `0.0.0.0:8765`. Find your PC's IP with `ipconfig` and open `http://<your-ip>:8765` from your phone on the same Wi-Fi.

ffmpeg is bundled, so any quality (including 4K with merged audio) works out of the box.

### Option 2: from source

```powershell
# Engine + CLI work on Python 3.14:
py -3.14 -m pip install -r requirements.txt
py -3.14 -m app.cli info "https://www.youtube.com/watch?v=..."

# Kivy desktop UI needs Python 3.12 (no Kivy wheels for 3.14 yet):
py -3.12 -m pip install -r requirements.txt kivy
py -3.12 main.py

# Web dashboard:
py -3.12 main.py --web              # localhost only
py -3.12 main.py --web --host 0.0.0.0  # accessible from your LAN
```

You also need ffmpeg on `PATH` (`winget install Gyan.FFmpeg`) for >720p
YouTube downloads and MP3 conversion.

## Build the Android APK

See [BUILD_APK.md](BUILD_APK.md). Two paths:

- **GitHub Actions (cloud, ~25 min)** — push the repo to a new GitHub repo; the workflow at `.github/workflows/build-apk.yml` builds the APK and uploads it as an artifact.
- **WSL + Ubuntu (local, ~60 min)** — `wsl --install -d Ubuntu`, then `bash scripts/setup_wsl.sh && bash scripts/build_apk.sh`.

## Web dashboard API

If you want to script against it:

| Method | Path | What |
|---|---|---|
| `GET` | `/` | Dashboard HTML |
| `POST` | `/api/info` | Body: `{"url": "..."}`. Returns full `MediaInfo` JSON. |
| `POST` | `/api/download` | Body: `{"url": "...", "format_id": "...", "audio_only": false}`. Returns `{"job_id": "..."}`. |
| `GET` | `/api/progress/{job_id}` | Server-Sent Events stream — `start`, `progress` (with %, speed, eta), `done`, `error`. |
| `GET` | `/api/downloads` | List of saved files in the downloads folder. |
| `GET` | `/api/file?rel=<path>` | Download a saved file. |

## Notes

- YouTube occasionally rate-limits rapid repeat requests from the same IP. On a phone with normal usage this isn't a problem.
- Instagram private accounts and stories need session cookies — login flow is a planned follow-up. Public posts/reels/IGTV/carousels work without login.
