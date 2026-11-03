#!/usr/bin/env python3
"""
Foreman avatar pipeline.

Turns each app's icon into a circular avatar for the Foreman board. Run it
whenever an app's icon changes:  python3 foreman/make_avatars.py

Output: portfolio/avatars/<slug>.png (128px circle). The dash serves these at
/avatars/<slug>.png and falls back to a coloured initial when a slug has none.
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "portfolio", "avatars")

# slug -> source icon path. Only apps with a real icon; the rest fall back to
# the coloured-initial avatar on the board.
ICONS = {
    "recilia": "/root/MonoClaw/recilia/assets/icon.png",
    "travelog": "/root/MonoClaw/travelog/icon-512.png",
    "open-home": "/root/MonoClaw/open-home/apps/mobile/assets/icon.png",
    "inkling": "/root/MonoClaw/inkling/icon-512.png",
    "favorly": "/root/MonoClaw/favorly/apps/mobile/assets/icon.png",
    "lumen": "/root/MonoClaw/lumen/icon-512.png",
}

SIZE = 128


def circle(src, dst):
    img = Image.open(src).convert("RGBA")
    # center-crop to square, then resize
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((SIZE, SIZE), Image.LANCZOS)
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, SIZE, SIZE), fill=255)
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    out.save(dst)


def main():
    os.makedirs(OUT, exist_ok=True)
    made = []
    for slug, src in ICONS.items():
        if not os.path.exists(src):
            print("skip (no icon):", slug)
            continue
        dst = os.path.join(OUT, slug + ".png")
        circle(src, dst)
        made.append(slug)
    print("avatars written:", ", ".join(made), "->", os.path.realpath(OUT))


if __name__ == "__main__":
    main()
