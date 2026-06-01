[app]

# Display name shown to the user.
title = Pglu

# Package name and domain (must be a valid Java identifier).
package.name = pglu
package.domain = com.pglu.app

# Source directory and which files to include.
source.dir = .
source.include_exts = py,kv,png,jpg,jpeg,atlas,json,txt,html,css,js,ico
source.include_patterns = app/*,app/ui/*,app/engine/*,app/web/*,app/web/static/*,app/assets/*,assets/*

# App version.
version = 0.1.0

# Python deps. python3 + kivy + our download stack.
# - python3/hostpython3 are PINNED to 3.13.9. Without a pin, python-for-android
#   builds against the newest CPython it knows about (3.14), which Kivy 2.3.1
#   does not support — the app then crashes the instant `import kivy` runs, before
#   any on-screen error handler can fire. 3.13 is the highest Python that Kivy
#   2.3.1 supports, and it stays one minor below p4a's native 3.14 so the host
#   build/venv (pip, ensurepip) remains internally consistent — pinning further
#   back (e.g. 3.11) made p4a's venv bootstrap a mismatched vendored resolvelib
#   and the build died. Keep both pins in lock-step.
# - openssl/sqlite3/pyjnius/android are listed explicitly so missing recipes
#   surface at build time rather than as a silent runtime crash.
# - setuptools is needed at runtime because instaloader's lxml/PIL fallbacks
#   use pkg_resources on some Python builds.
requirements = python3==3.13.9,hostpython3==3.13.9,kivy==2.3.1,openssl,sqlite3,pyjnius,android,setuptools,certifi,charset-normalizer,idna,urllib3,requests,mutagen,yt-dlp,instaloader

# App icon (shown on the launcher and in Settings -> Apps).
icon.filename = app/assets/icon.png

# Orientation: portrait phone-only.
orientation = portrait

# Disable the splash for now; can add later.
# presplash.filename = assets/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1

[android]

# API levels.
android.minapi = 24
android.api = 34
android.ndk_api = 24

# Permissions the app needs at runtime.
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,READ_MEDIA_VIDEO,READ_MEDIA_IMAGES,READ_MEDIA_AUDIO

# Architectures to build for. arm64-v8a covers modern phones; add armeabi-v7a if you also want older devices.
android.archs = arm64-v8a,armeabi-v7a

# Allow http (some IG/YT redirects use mixed content during processing).
android.allow_backup = True

# Kivy bootstrap.
p4a.bootstrap = sdl2
