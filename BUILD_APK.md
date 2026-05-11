# Building the APK

The desktop app (Windows) is fully working. To turn it into an `.apk` you need
a Linux environment with Buildozer. The official path on Windows is **WSL +
Ubuntu**.

## One-time setup (about 15-20 minutes, mostly waiting)

### Step 1 — Install Ubuntu in WSL

Open **PowerShell as Administrator** and run:

```powershell
wsl --install -d Ubuntu
```

This installs the WSL2 kernel (if missing) and the Ubuntu distribution.
**Restart Windows** if it tells you to.

After restart, launch **Ubuntu** from the Start menu. It will:
1. Finish unpacking on first launch.
2. Ask you to **create a Linux username and password** — pick anything; only
   you will use it. Write them down.

### Step 2 — Run the WSL setup script

Still inside the **Ubuntu** terminal:

```bash
cd "/mnt/c/Users/DELL/Desktop/AI Manager/Insta & YT Video,image, shorts, reels Downloader"
bash scripts/setup_wsl.sh
```

This installs the OpenJDK, build tools, Buildozer, and Cython. Takes ~5 min.

### Step 3 — Build the APK

```bash
source ~/.aiodl-venv/bin/activate
bash scripts/build_apk.sh
```

**Heads up:** the *first* build downloads the Android SDK + NDK (~3 GB) and
compiles all the Python dependencies for ARM. This takes **30-60 minutes**
depending on your internet and CPU. Subsequent builds are 1-3 min.

When it finishes, the APK will be at:

```
bin/pglu-0.1.0-arm64-v8a_armeabi-v7a-debug.apk
```

## Installing on your phone

### Option A — USB cable (easiest)

1. On your phone: **Settings -> About phone -> tap "Build number" 7 times** to
   unlock Developer options.
2. **Settings -> Developer options -> turn on "USB debugging"**.
3. Plug the phone into the PC. Accept the "Allow USB debugging" prompt.
4. From WSL, in the project root:

   ```bash
   buildozer android deploy run
   ```

   This installs the APK and launches it on the phone.

### Option B — Manual sideload

1. Copy `bin/pglu-*.apk` to your phone (email, Drive, USB transfer).
2. On the phone, tap the file. Android will prompt "Allow installs from this
   source" — accept.
3. Open the app from the launcher.

## After the first build

To rebuild after code changes:

```bash
source ~/.aiodl-venv/bin/activate
buildozer android debug
```

To wipe everything and start fresh (rare):

```bash
buildozer android clean
```

## Known limitations of the first APK

1. **No bundled ffmpeg.** YouTube formats above 720p are split into separate
   video and audio streams that need ffmpeg to merge. Without ffmpeg the app
   will fall back to combined formats (max 720p). Bundling ffmpeg for Android
   is a follow-up task — the engine is already wired up to use it as soon as
   it's on `PATH`.
2. **Instagram private content** needs login (your IG session). Public posts,
   reels, and IGTV work without login.
3. **First launch on the phone** asks for storage permission — accept it so
   downloads can save to `/sdcard/Download/Pglu/`.

## Troubleshooting

- **`No matching distribution found for ...` during build**: a recipe is
  missing. Open `buildozer.spec`, remove the offending package from
  `requirements`, run `buildozer android clean`, rebuild.
- **`SDK license not accepted`**: re-run, Buildozer will prompt and accept.
- **APK installs but crashes on open**: in WSL, run
  `adb logcat | grep python` while launching the app on the phone — this
  surfaces the Python traceback.
