# Pglu

<p align="center"><img src="app/assets/banner.png" alt="Pglu" width="100%"></p>

Download YouTube + Instagram videos, audio, images — any quality, with full
metadata (title, description, tags, thumbnail). One engine, three ways to use it:

| | Platform | What you get |
|---|---|---|
| 📱 | **Android** | A native `.apk` you sideload on your phone. |
| 🪟 | **Windows** | A double-clickable `.exe` (Kivy desktop GUI **or** local web dashboard). |
| 🌐 | **Web dashboard** | Run the server on your PC, use it from any browser — including your phone on the same Wi-Fi. |

Built with `yt-dlp` + `instaloader` under the hood, Kivy for the native UI,
FastAPI for the web dashboard.

> **Status:** v0.1.0. The Android APK and Windows `.exe` are both produced
> automatically by the GitHub Actions workflow on every push.

---

## Download

Latest builds are attached to the **[Releases](https://github.com/aashishbharti04/pglu/releases/latest)** page.

| File | Use for | Size |
|---|---|---|
| `pglu-<version>-arm64-v8a_armeabi-v7a-debug.apk` | Android phones | ~30 MB |
| `Pglu-Windows.zip` | Windows 10/11 (64-bit) | ~205 MB |

No release yet? It will appear after the first successful Actions run.
You can also grab the latest APK from the **[Actions tab](https://github.com/aashishbharti04/pglu/actions)** → click the most recent green run → scroll to **Artifacts** → download `pglu-debug-apk`.

---

## Install — Android

1. **Download** the `.apk` to your phone (Drive, email, USB, whatever).
2. **Tap the .apk file** in your Files app. Android will ask:
   - *"For your security, your phone is not allowed to install unknown apps from this source."* → tap **Settings** → enable **Allow from this source** (one-time, per app).
3. **Tap Install** → **Open** when it's done.
4. On first launch, accept the **storage permission** prompt.

Downloads land in **`/sdcard/Download/Pglu/`** — open the Files app or Gallery to find them. Each download includes the media file, a JPG thumbnail, and a `.json` sidecar with the full metadata (title, description, tags, view count, etc.).

### Using the Android app

1. Copy a YouTube or Instagram link in any app (browser, YouTube app, Instagram).
2. Open **Pglu** → tap **Paste** → **Fetch info**.
3. Pick a quality from the dropdown (4K, 1080p, 720p, audio-only MP3, etc.).
4. Tap **Download** → wait for the progress bar → done.

---

## Install — Windows

1. **Download** [`Pglu-Windows.zip`](https://github.com/aashishbharti04/pglu/releases/latest) from the Releases page.
2. **Right-click → Extract All** anywhere (Desktop, Documents, USB stick).
3. **Open the extracted folder** — you'll see three shortcuts:

   | Shortcut | What it does |
   |---|---|
   | `Pglu - Desktop.bat` | Opens the native GUI (looks like the Android app). |
   | `Pglu - Web Dashboard.bat` | Starts a server on this PC. Open `http://127.0.0.1:8765` in any browser. |
   | `Pglu - Web Dashboard (LAN).bat` | Same, but also accessible from your phone on the same Wi-Fi. |

4. **Double-click** whichever you want.
5. The first time you run the LAN version, Windows Firewall will pop up — click **Allow access**.

ffmpeg is bundled inside the zip, so all qualities (including 4K with merged audio) work out of the box. No Python install needed.

Downloads land in **`C:\Users\<You>\Downloads\Pglu\`**.

### Using the web dashboard from your phone

1. Run `Pglu - Web Dashboard (LAN).bat` on your PC.
2. Open PowerShell on your PC, type `ipconfig`, look for the **IPv4 Address** under your Wi-Fi adapter (e.g. `192.168.1.42`).
3. On your phone (same Wi-Fi network), open any browser → go to `http://192.168.1.42:8765`.
4. Paste a URL, pick quality, hit Download. The file saves on your PC. Tap the **Save** button next to it in "My downloads" to also copy it to your phone.

---

## What it can download

### From YouTube
- Videos at any resolution offered (144p → 4K → 8K, depending on the source)
- Audio-only as MP3 (192 kbps)
- Thumbnails as JPG
- Full metadata: title, description, tags, channel, duration, view/like count, upload date

### From Instagram
- Reels (video)
- Posts (single image or carousel of multiple images/videos)
- IGTV
- Caption, hashtags, mentions, upload date, like count

Currently supports **public** Instagram content (no login required). Private accounts and stories need session cookies — planned for v0.2.

### Everywhere
- A `.json` sidecar is written next to every download containing the full metadata as structured data — useful if you want to script over your library later.

---

## Build it yourself

Anyone can build the Windows `.exe` and the Android APK from source.

### Prerequisites
- **For Windows**: Python 3.12, [ffmpeg](https://www.gyan.dev/ffmpeg/builds/) on `PATH`, `pip install -r requirements.txt kivy pyinstaller`.
- **For Android**: A Linux environment (WSL on Windows works), `python3`, `openjdk-17`, `buildozer`, `cython==0.29.36`. See [BUILD_APK.md](BUILD_APK.md) for the WSL setup script.
- **For just the engine / CLI**: Any Python 3.9+, `pip install -r requirements.txt`.

### Quick commands

```bash
# Run from source — desktop GUI
py -3.12 main.py

# Run from source — web dashboard
py -3.12 main.py --web                      # localhost only
py -3.12 main.py --web --host 0.0.0.0       # accessible from your LAN

# Run from source — CLI (engine smoke test)
python -m app.cli info "https://www.youtube.com/watch?v=..."
python -m app.cli download "<url>" --out=downloads          # best quality
python -m app.cli download "<url>" --audio --out=downloads  # MP3
python -m app.cli download "<url>" --format=137 --out=downloads  # specific format

# Build Windows .exe (Python 3.12 only)
py -3.12 -m PyInstaller pglu.spec
# .exe lands at dist/Pglu/Pglu.exe — copy ffmpeg.exe + ffprobe.exe into dist/Pglu/_internal/ to bundle it.

# Build Android APK (Linux/WSL only)
bash scripts/setup_wsl.sh        # one-time setup
bash scripts/build_apk.sh        # produces bin/pglu-*.apk
```

### Project layout
```
app/
├── engine/      # yt-dlp + instaloader wrappers (the brains)
│   ├── common.py        # MediaInfo, MediaFormat, ProgressEvent dataclasses
│   ├── youtube.py       # YouTubeEngine — wraps yt-dlp
│   └── instagram.py     # InstagramEngine — wraps instaloader
├── ui/          # Kivy desktop UI (also the basis for the Android APK)
│   ├── main.py
│   ├── app.kv
│   └── storage.py
├── web/         # FastAPI server + single-page HTML dashboard
│   ├── server.py
│   └── static/index.html
└── cli.py       # Headless CLI

main.py                # Entry point. Pass --web for the dashboard.
pglu.spec              # PyInstaller config for the Windows .exe
buildozer.spec         # Buildozer config for the Android APK
.github/workflows/     # Cloud CI that builds the APK on every push
```

### Web dashboard API

If you want to script against the server:

| Method | Path | What |
|---|---|---|
| `GET` | `/` | Dashboard HTML |
| `POST` | `/api/info` | Body: `{"url": "..."}` → returns `MediaInfo` JSON (formats, metadata, thumbnail). |
| `POST` | `/api/download` | Body: `{"url": "...", "format_id": "...", "audio_only": false}` → returns `{"job_id": "..."}`. |
| `GET` | `/api/progress/{job_id}` | Server-Sent Events stream: `start`, `progress` (%, speed, ETA), `done`, `error`. |
| `GET` | `/api/downloads` | List of saved files. |
| `GET` | `/api/file?rel=<path>` | Stream a saved file for browser download. |

---

## FAQ

**Q: Is this legal?**
Pglu is a thin wrapper around `yt-dlp` and `instaloader` — open-source tools widely used for personal offline use, accessibility, and archival. YouTube's and Instagram's Terms of Service forbid using third-party downloaders for redistribution of copyrighted content. **Use this for personal viewing of content you have a right to access.** Don't redistribute. Don't pirate. The maintainer accepts no responsibility for misuse.

**Q: Why is the Windows zip 200 MB?**
Most of it is `ffmpeg.exe` + `ffprobe.exe` (~430 MB uncompressed, ~200 MB zipped). Bundling them means *any* quality works out of the box — no separate ffmpeg install. If you already have ffmpeg on `PATH`, delete `_internal/ffmpeg.exe` and `_internal/ffprobe.exe` and the app falls back to the system one.

**Q: Why does the Android APK not have ffmpeg?**
Android packages ARM64 binaries and ffmpeg for Android is a separate ~80 MB blob. Pglu v0.1 ships without it, which means YouTube formats above 720p that need merging won't work yet — single-stream formats (incl. 720p combined, audio-only MP3) work fine. ffmpeg-for-Android bundling is planned for v0.2.

**Q: YouTube says "Sign in to confirm you're not a bot."**
YouTube's rate limit for the IP making the request. Wait 10-15 minutes, or use a different URL first. On a real phone using normal home Wi-Fi this is rare.

**Q: Instagram downloads fail with a connection error.**
Check whether your DNS or `hosts` file blocks `instagram.com`. Some adblockers and parental-control filters block it.

**Q: Can I run the web dashboard 24/7 as a home media server?**
Yes — `python main.py --web --host 0.0.0.0`. Put it behind a reverse proxy (Caddy, nginx) if you want HTTPS and a domain name.

---

## Contributing

PRs welcome. Suggested directions:
- Instagram login flow (Stories, private accounts)
- ffmpeg-for-Android bundling
- Twitter/X, TikTok, SoundCloud support (yt-dlp already supports them — just thread them through the engine layer)
- Concurrent/queued downloads in the UI
- Dark/light theme toggle on the web dashboard

Open an issue first for anything large.

## License

MIT — see [LICENSE](LICENSE).

The bundled `ffmpeg.exe` / `ffprobe.exe` binaries (in the Windows release zip) are distributed under their own LGPL/GPL terms; full license text is in `_internal/LICENSE.*` inside the zip.
