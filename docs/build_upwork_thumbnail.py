"""Crisp Upwork portfolio thumbnail — large type, few details."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
LOGO = ROOT.parent / "frontend" / "public" / "aarogya-one-connect-logo.png"
OUT = ROOT / "handbook_assets" / "upwork-portfolio-aarogya-thumbnail.png"

W, H = 1200, 800
NAVY = (11, 31, 58, 255)
NAVY_2 = (18, 48, 86, 255)
TEAL = (46, 196, 182, 255)
WHITE = (255, 255, 255, 255)
PHONE = (236, 244, 248, 255)
SCREEN = (15, 42, 74, 255)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(fr"C:\Windows\Fonts\{name}", size)


def rounded_paste(base: Image.Image, overlay: Image.Image, xy: tuple[int, int], radius: int) -> None:
    mask = Image.new("L", overlay.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *overlay.size), radius=radius, fill=255)
    base.paste(overlay, xy, mask)


def main() -> None:
    img = Image.new("RGBA", (W, H), NAVY)
    draw = ImageDraw.Draw(img)

    draw.ellipse((820, -180, 1380, 380), fill=(20, 90, 110, 70))
    draw.ellipse((-220, 520, 280, 1020), fill=(14, 70, 90, 55))
    draw.line((40, 40, 220, 40), fill=(46, 196, 182, 90), width=6)
    draw.line((40, 40, 40, 160), fill=(46, 196, 182, 90), width=6)

    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.resize((200, 200), Image.Resampling.LANCZOS)
    badge = Image.new("RGBA", (228, 228), (8, 24, 46, 255))
    ImageDraw.Draw(badge).rounded_rectangle((0, 0, 227, 227), radius=32, fill=(8, 24, 46, 255), outline=TEAL, width=5)
    badge.paste(logo, (14, 14), logo)
    rounded_paste(img, badge, (56, 200), 32)

    title_font = font(58, bold=True)
    sub_font = font(30, bold=True)
    draw.text((56, 460), "Aarogya One Connect", font=title_font, fill=WHITE)
    draw.text((56, 540), "Multi-clinic OPD", font=sub_font, fill=TEAL)

    # Simple phone — silhouette only, no tiny UI text
    px, py, pw, ph = 840, 110, 280, 580
    phone = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    pd = ImageDraw.Draw(phone)
    pd.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=42, fill=PHONE)
    pd.rounded_rectangle((16, 16, pw - 17, ph - 17), radius=32, fill=SCREEN)
    pd.rounded_rectangle((pw // 2 - 40, 28, pw // 2 + 40, 42), radius=8, fill=(11, 31, 58, 255))
    cx, cy, r = pw // 2, ph // 2, 78
    pd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=TEAL)
    # mic
    pd.rounded_rectangle((cx - 16, cy - 36, cx + 16, cy + 12), radius=16, fill=WHITE)
    pd.arc((cx - 28, cy - 8, cx + 28, cy + 40), start=0, end=180, fill=WHITE, width=7)
    pd.line((cx, cy + 40, cx, cy + 58), fill=WHITE, width=7)
    pd.line((cx - 18, cy + 58, cx + 18, cy + 58), fill=WHITE, width=7)
    img.paste(phone, (px, py), phone)

    # Soft drop shadow behind phone
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((px + 18, py + 22, px + pw + 18, py + ph + 22), radius=42, fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(shadow, img)

    out = img.convert("RGB")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT, "PNG", optimize=True)
    print(f"Wrote {OUT} {out.size}")


if __name__ == "__main__":
    main()
