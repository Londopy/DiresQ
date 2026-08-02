"""Draws the social preview card.

The image people see when the repo, the docs site or the demo gets linked in
Discord, Slack or a Devpost embed. Generated rather than hand-drawn so it can
be regenerated when the wording changes, and so it lives in version control as
code instead of as a file somebody made once in Figma and lost.

    python tools/make_og.py

Writes 1200x630 PNGs — the size every platform crops to — into
static/images/ and site/public/.

The design is one idea: an accountability board with a red row on it, which is
the only screenshot in the project that explains what it does without words.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

W, H = 1200, 630

# Catppuccin Mocha, same as the app.
BASE = (30, 30, 46)
MANTLE = (24, 24, 37)
SURFACE = (49, 50, 68)
OVERLAY = (69, 71, 90)
TEXT = (205, 214, 244)
SUBTEXT = (166, 173, 200)
BLUE = (137, 180, 250)
GREEN = (166, 227, 161)
RED = (243, 139, 168)
PEACH = (250, 179, 135)

FONTS = "/usr/share/fonts/truetype/dejavu"


def font(name: str, size: int):
    try:
        return ImageFont.truetype(f"{FONTS}/{name}", size)
    except OSError:
        # Better a plain card than no card. Only bites on a machine without
        # DejaVu, which is most of them outside Linux.
        return ImageFont.load_default()


def row(draw, y, name, state, colour, detail, dim=False):
    """One line of the accountability board."""
    draw.rounded_rectangle([70, y, W - 70, y + 62], 8,
                           fill=MANTLE if dim else SURFACE)
    # The status stripe. This is the whole visual argument.
    draw.rounded_rectangle([70, y, 76, y + 62], 3, fill=colour)

    draw.text((100, y + 12), name, font=font("DejaVuSansMono-Bold.ttf", 21),
              fill=SUBTEXT if dim else TEXT)
    draw.text((100, y + 38), detail, font=font("DejaVuSans.ttf", 14),
              fill=OVERLAY if dim else SUBTEXT)

    label = font("DejaVuSans-Bold.ttf", 15)
    width = draw.textlength(state, font=label)
    draw.text((W - 100 - width, y + 22), state, font=label, fill=colour)


def build() -> Image.Image:
    card = Image.new("RGB", (W, H), BASE)
    draw = ImageDraw.Draw(card)

    # A wash behind the board, so it doesn't read as a flat rectangle.
    for i in range(220):
        shade = tuple(int(b + (m - b) * i / 220) for b, m in zip(BASE, MANTLE))
        draw.line([(0, H - 220 + i), (W, H - 220 + i)], fill=shade)

    draw.text((70, 58), "DiresQ", font=font("DejaVuSans-Bold.ttf", 64),
              fill=GREEN)

    draw.text((70, 140),
              "Every disaster app tells you where the disaster is.",
              font=font("DejaVuSans.ttf", 27), fill=TEXT)
    draw.text((70, 178), "DiresQ tracks the people going into it.",
              font=font("DejaVuSans-Bold.ttf", 27), fill=RED)

    # The board. Ordered worst-first, exactly as the real one is.
    row(draw, 250, "s.reyes", "OVERDUE", RED,
        "Roof peeled back, family of four  ·  last contact 47 min ago")
    row(draw, 326, "m.torres", "ON SCENE", GREEN,
        "Car in the water at Mayde Creek  ·  said overstaffed")
    row(draw, 402, "skythe", "EN ROUTE", BLUE,
        "Elderly man, oxygen concentrator  ·  ETA 25 min", dim=True)

    draw.text((70, 500), "3 reports with nobody going",
              font=font("DejaVuSans-Bold.ttf", 19), fill=PEACH)

    small = font("DejaVuSans.ttf", 16)
    footer = "Katy Youth Hacks 2026  ·  STEMist Hacks IV  ·  Apache-2.0"
    draw.text((70, 552), footer, font=small, fill=OVERLAY)

    return card


def main() -> int:
    card = build()
    targets = [
        ROOT / "static" / "images" / "og.png",
        ROOT / "site" / "public" / "og.png",
    ]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        card.save(path, "PNG", optimize=True)
        print(f"wrote {path.relative_to(ROOT)} "
              f"({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
