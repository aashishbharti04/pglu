"""Generate every flavor of icon Pglu needs from a single source image.

Run:
    py -3.12 scripts/generate_icons.py

Outputs:
    app/assets/icon.png      (1024x1024 — Kivy + Buildozer launcher icon)
    app/assets/icon.ico      (multi-size — PyInstaller .exe icon)
    app/assets/banner.png    (1280x400 — README / web dashboard hero)
    app/web/static/favicon.ico
    app/web/static/favicon.png    (256x256, for modern browsers)
    app/web/static/logo.png       (512x512, used as web header avatar + bg)
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "logo.png"

ASSETS = ROOT / "app" / "assets"
WEB = ROOT / "app" / "web" / "static"

ASSETS.mkdir(parents=True, exist_ok=True)
WEB.mkdir(parents=True, exist_ok=True)


def square_crop(im: Image.Image, focus: str = "upper") -> Image.Image:
    """Crop the image to a square. `focus='upper'` keeps the face centered."""
    w, h = im.size
    s = min(w, h)
    if w > h:
        left = (w - s) // 2
        top = 0
    else:
        left = 0
        # For a tall portrait, bias toward the top so the face stays visible.
        top = (h - s) // 4 if focus == "upper" else (h - s) // 2
    return im.crop((left, top, left + s, top + s))


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Source image not found: {SRC}")

    print(f"Source: {SRC}  ->  loading...")
    src = Image.open(SRC).convert("RGBA")
    print(f"  size = {src.size}, mode = {src.mode}")

    # ---- Square master at 1024x1024 (icon master) ----
    sq = square_crop(src, focus="upper")
    icon_master = sq.resize((1024, 1024), Image.LANCZOS)
    icon_master.save(ASSETS / "icon.png", "PNG", optimize=True)
    print(f"  wrote {ASSETS/'icon.png'}  ({icon_master.size})")

    # ---- Multi-size .ico for Windows .exe ----
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    icon_master.save(
        ASSETS / "icon.ico",
        format="ICO",
        sizes=ico_sizes,
    )
    print(f"  wrote {ASSETS/'icon.ico'}  ({len(ico_sizes)} sizes)")

    # ---- Web favicon ----
    icon_master.resize((256, 256), Image.LANCZOS).save(WEB / "favicon.png", "PNG", optimize=True)
    icon_master.save(WEB / "favicon.ico", format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
    print(f"  wrote {WEB/'favicon.png'} and {WEB/'favicon.ico'}")

    # ---- Web logo (used in header) ----
    icon_master.resize((512, 512), Image.LANCZOS).save(WEB / "logo.png", "PNG", optimize=True)
    print(f"  wrote {WEB/'logo.png'}")

    # ---- Banner (wide, for the README hero + Kivy / dashboard background) ----
    banner_w, banner_h = 1280, 400
    # Resize keeping aspect, then center-crop horizontally.
    ratio = banner_h / src.height
    scaled = src.resize((int(src.width * ratio), banner_h), Image.LANCZOS)
    if scaled.width >= banner_w:
        left = (scaled.width - banner_w) // 2
        banner = scaled.crop((left, 0, left + banner_w, banner_h))
    else:
        # Pad with mirror so we always hit target width.
        banner = Image.new("RGBA", (banner_w, banner_h), (12, 14, 18, 255))
        banner.paste(scaled, ((banner_w - scaled.width) // 2, 0), scaled)
    banner.save(ASSETS / "banner.png", "PNG", optimize=True)
    print(f"  wrote {ASSETS/'banner.png'}  ({banner.size})")

    # ---- Web background (heavily darkened + blurred so UI stays readable) ----
    bg_master = src.resize((1600, int(src.height * 1600 / src.width)), Image.LANCZOS)
    bg_master = bg_master.filter(ImageFilter.GaussianBlur(radius=18))
    # Compose with a dark overlay so foreground UI text is legible.
    overlay = Image.new("RGBA", bg_master.size, (8, 10, 14, 215))
    bg_composed = Image.alpha_composite(bg_master, overlay)
    bg_composed.convert("RGB").save(WEB / "bg.jpg", "JPEG", quality=82, optimize=True)
    print(f"  wrote {WEB/'bg.jpg'}  ({bg_composed.size})")

    print("Done.")


if __name__ == "__main__":
    main()
