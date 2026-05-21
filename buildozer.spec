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
# - openssl/sqlite3/pyjnius/android are listed explicitly so missing recipes
#   surface at build time rather than as a silent runtime crash.
# - setuptools is needed at runtime because instaloader's lxml/PIL fallbacks
#   use pkg_resources on some Python builds.
requirements = python3,kivy==2.3.1,openssl,sqlite3,pyjnius,android,setuptools,certifi,charset-normalizer,idna,urllib3,requests,mutagen,yt-dlp,instaloader

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
