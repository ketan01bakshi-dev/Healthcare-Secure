"""Generate Android launcher icons from the home-screen logo."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "frontend" / "public" / "aarogya-one-connect-logo.png"
RES = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res"

# Launcher foreground sizes (px) per density
SIZES = {
    "mipmap-mdpi": 108,
    "mipmap-hdpi": 162,
    "mipmap-xhdpi": 216,
    "mipmap-xxhdpi": 324,
    "mipmap-xxxhdpi": 432,
}


def _square_logo(src: Image.Image, size: int) -> Image.Image:
    """Center logo on transparent square with padding (~18% safe zone)."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img = src.convert("RGBA")
    # Keep aspect; fit inside ~72% of canvas (adaptive icon safe zone)
    max_side = int(size * 0.72)
    img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def main() -> None:
    if not LOGO.exists():
        raise SystemExit(f"Missing logo: {LOGO}")
    src = Image.open(LOGO)
    for folder, size in SIZES.items():
        out_dir = RES / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        fg = _square_logo(src, size)
        fg.save(out_dir / "ic_launcher_foreground.png", format="PNG")
        # Legacy full icons (same artwork)
        fg.save(out_dir / "ic_launcher.png", format="PNG")
        fg.save(out_dir / "ic_launcher_round.png", format="PNG")
        print(f"wrote {folder} ({size}px)")

    # Solid brand-tint background for adaptive icon
    values = RES / "values"
    values.mkdir(parents=True, exist_ok=True)
    colors = values / "ic_launcher_background.xml"
    # Soft clinic teal matching product UI
    colors.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        '    <color name="ic_launcher_background">#E8F4F1</color>\n'
        "</resources>\n",
        encoding="utf-8",
    )
    print("wrote ic_launcher_background color")


if __name__ == "__main__":
    main()
