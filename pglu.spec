# PyInstaller spec for Pglu (Windows .exe).
# Build with:
#   py -3.12 -m PyInstaller pglu.spec
from kivy_deps import sdl2, glew, angle  # type: ignore
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = [
    ("app/ui/app.kv", "app/ui"),
    ("app/web/static/index.html", "app/web/static"),
]
# Bundle yt-dlp's extractor + crypto data files so it works inside the .exe
datas += collect_data_files("yt_dlp")
datas += collect_data_files("instaloader")

hiddenimports = [
    "yt_dlp",
    "yt_dlp.extractor",
    "yt_dlp.extractor.youtube",
    "yt_dlp.extractor.instagram",
    "instaloader",
    "app.web.server",
    "uvicorn",
    "uvicorn.loops",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL"],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Pglu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # hide console window for the GUI build
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins + angle.dep_bins)],
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Pglu",
)
