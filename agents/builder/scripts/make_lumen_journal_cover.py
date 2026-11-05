#!/usr/bin/env python3
"""Render 'The Lumen Journal' anchor-product cover without an image model.
Pure Pillow: midnight navy/violet linen hardcover, gold sunburst emblem,
LUMEN wordmark, gold ribbon + gilded page edge, moody bokeh backdrop.
Supersampled 2x then downscaled for smooth edges.
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2  # supersample
W, H = 1200 * S, 1500 * S
GOLD = (229, 190, 110)
GOLD_HI = (248, 224, 158)
GOLD_LO = (176, 134, 66)

random.seed(7)

def font(path, size):
    return ImageFont.truetype(path, size)

SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF_R = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"

# ---------- background: moody radial + gold bokeh ----------
bg = Image.new("RGB", (W, H), (6, 6, 12))
bgd = ImageDraw.Draw(bg)
cx, cy = W * 0.5, H * 0.42
maxr = math.hypot(W, H)
for y in range(0, H, 2 * S):
    for x in range(0, W, 2 * S):
        d = math.hypot(x - cx, y - cy) / maxr
        v = max(0.0, 1.0 - d * 1.7)
        r = int(14 + 26 * v); g = int(12 + 18 * v); b = int(26 + 40 * v)
        bgd.rectangle([x, y, x + 2 * S, y + 2 * S], fill=(r, g, b))
# soft gold bokeh orbs
bok = Image.new("RGBA", (W, H), (0, 0, 0, 0))
bd = ImageDraw.Draw(bok)
for _ in range(14):
    bx = random.randint(0, W); by = random.randint(int(H * 0.55), H)
    br = random.randint(30 * S, 95 * S)
    a = random.randint(10, 38)
    bd.ellipse([bx - br, by - br, bx + br, by + br], fill=(236, 196, 120, a))
bok = bok.filter(ImageFilter.GaussianBlur(28 * S))
bg = Image.alpha_composite(bg.convert("RGBA"), bok).convert("RGB")

# ---------- the book ----------
bw, bh = int(W * 0.60), int(H * 0.74)
bx = (W - bw) // 2 + int(0.01 * W)
by = int(H * 0.12)

# drop shadow
sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
shd = ImageDraw.Draw(sh)
shd.rounded_rectangle([bx - 12 * S, by + 34 * S, bx + bw + 30 * S, by + bh + 46 * S],
                      radius=26 * S, fill=(0, 0, 0, 170))
sh = sh.filter(ImageFilter.GaussianBlur(34 * S))
bg = Image.alpha_composite(bg.convert("RGBA"), sh).convert("RGB")

# gilded page edge (right side, behind cover) — soft warm band
edge = ImageDraw.Draw(bg)
EW = 11 * S
for i in range(EW):
    t = i / EW
    # brightest in the middle of the band, fading at both sides -> reads as gilt pages
    k = 1.0 - abs(t - 0.45) * 1.6
    k = max(0.0, k)
    col = tuple(int(a + (b - a) * k) for a, b in zip(GOLD_LO, GOLD_HI))
    edge.rectangle([bx + bw + i, by + 12 * S, bx + bw + i + 1, by + bh + 6 * S], fill=col)

# cover with navy->violet gradient
cover = Image.new("RGB", (bw, bh), (20, 22, 48))
cd = ImageDraw.Draw(cover)
top = (18, 20, 46); bot = (46, 28, 70)
for y in range(bh):
    t = y / bh
    cd.line([(0, y), (bw, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)))
# linen texture: fine threads + noise
lin = Image.new("L", (bw, bh), 0)
ld = ImageDraw.Draw(lin)
for y in range(0, bh, 3 * S):
    ld.line([(0, y), (bw, y)], fill=random.randint(6, 16))
for x in range(0, bw, 3 * S):
    ld.line([(x, 0), (x, bh)], fill=random.randint(4, 12))
lin = lin.filter(ImageFilter.GaussianBlur(0.6 * S))
cover = Image.composite(Image.new("RGB", (bw, bh), (120, 110, 150)), cover, lin.point(lambda v: v))
# vignette on cover
vg = Image.new("L", (bw, bh), 0)
vgd = ImageDraw.Draw(vg)
vgd.rectangle([0, 0, bw, bh], fill=0)
vgd.rounded_rectangle([int(bw*0.06), int(bh*0.05), int(bw*0.94), int(bh*0.95)], radius=20*S, fill=60)
vg = vg.filter(ImageFilter.GaussianBlur(40 * S))
cover = Image.composite(Image.new("RGB", (bw, bh), (255, 255, 255)), cover, vg).convert("RGB")
cover = Image.blend(cover, Image.new("RGB", (bw, bh), (18, 18, 40)), 0.0)

# spine shade (left)
spine = Image.new("L", (bw, bh), 0)
spd = ImageDraw.Draw(spine)
for x in range(int(bw * 0.10)):
    spd.line([(x, 0), (x, bh)], fill=int(120 * (1 - x / (bw * 0.10))))
cover = Image.composite(Image.new("RGB", (bw, bh), (0, 0, 0)), cover, spine)

cdraw = ImageDraw.Draw(cover)

# ---------- gold sunburst / mandala emblem ----------
ecx, ecy = bw // 2, int(bh * 0.40)
R = int(bw * 0.26)
# radiating tapered rays
n = 48
for i in range(n):
    ang = (i / n) * 2 * math.pi
    long = (i % 2 == 0)
    r2 = R * (1.0 if long else 0.72)
    r1 = R * 0.30
    wgt = 3 * S if long else 2 * S
    x1 = ecx + r1 * math.cos(ang); y1 = ecy + r1 * math.sin(ang)
    x2 = ecx + r2 * math.cos(ang); y2 = ecy + r2 * math.sin(ang)
    cdraw.line([(x1, y1), (x2, y2)], fill=GOLD, width=wgt)
# concentric rings
for rr, wd in [(R * 0.30, 3 * S), (R * 0.20, 2 * S), (R * 1.02, 2 * S)]:
    cdraw.ellipse([ecx - rr, ecy - rr, ecx + rr, ecy + rr], outline=GOLD, width=wd)
# inner filled sun
ir = int(R * 0.14)
cdraw.ellipse([ecx - ir, ecy - ir, ecx + ir, ecy + ir], fill=GOLD_HI)
# little dots around inner ring
for i in range(24):
    ang = (i / 24) * 2 * math.pi
    dx = ecx + R * 0.24 * math.cos(ang); dy = ecy + R * 0.24 * math.sin(ang)
    cdraw.ellipse([dx - 2 * S, dy - 2 * S, dx + 2 * S, dy + 2 * S], fill=GOLD_HI)

# ---------- wordmark ----------
try:
    fL = font(SERIF, int(bw * 0.17))
except Exception:
    fL = ImageFont.load_default()
word = "LUMEN"
# letter-spaced manual draw
sizes = [cdraw.textlength(ch, font=fL) for ch in word]
spacing = int(bw * 0.035)
total = sum(sizes) + spacing * (len(word) - 1)
wx = ecx - total / 2
wy = int(bh * 0.66)
for ch, sw in zip(word, sizes):
    cdraw.text((wx, wy), ch, font=fL, fill=GOLD)
    wx += sw + spacing
# subtitle
fS = font(SERIF_R, int(bw * 0.052))
sub = "THE GUIDED JOURNAL"
sl = cdraw.textlength(sub, font=fS)
# fake tracking by scaling spaces: draw char by char
tracking = int(bw * 0.012)
tsizes = [cdraw.textlength(c, font=fS) for c in sub]
ttotal = sum(tsizes) + tracking * (len(sub) - 1)
tx = ecx - ttotal / 2
ty = int(bh * 0.80)
for c, sw in zip(sub, tsizes):
    cdraw.text((tx, ty), c, font=fS, fill=GOLD_LO)
    tx += sw + tracking
# thin rule lines flanking subtitle
cdraw.line([(ecx - ttotal/2 - 40*S, ty + fS.size*0.5), (ecx - ttotal/2 - 14*S, ty + fS.size*0.5)], fill=GOLD_LO, width=1*S)
cdraw.line([(ecx + ttotal/2 + 14*S, ty + fS.size*0.5), (ecx + ttotal/2 + 40*S, ty + fS.size*0.5)], fill=GOLD_LO, width=1*S)

# cover highlight sheen
sheen = Image.new("L", (bw, bh), 0)
shd2 = ImageDraw.Draw(sheen)
shd2.polygon([(0, 0), (int(bw*0.5), 0), (int(bw*0.15), bh), (0, bh)], fill=22)
sheen = sheen.filter(ImageFilter.GaussianBlur(30 * S))
cover = Image.composite(Image.new("RGB", (bw, bh), (255, 255, 255)), cover, sheen).convert("RGB")

# rounded corners on cover
mask = Image.new("L", (bw, bh), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([0, 0, bw, bh], radius=22 * S, fill=255)
bg.paste(cover, (bx, by), mask)

# ---------- gold ribbon bookmark ----------
rib = ImageDraw.Draw(bg)
rx = bx + int(bw * 0.88)
rw = int(bw * 0.034)
rib.rectangle([rx, by + 6 * S, rx + rw, by + bh + int(bh * 0.10)], fill=GOLD)
# notched tail
ty2 = by + bh + int(bh * 0.10)
rib.polygon([(rx, ty2), (rx + rw, ty2), (rx + rw, ty2 + 26 * S),
             (rx + rw // 2, ty2 + 10 * S), (rx, ty2 + 26 * S)], fill=GOLD_LO)
# ribbon shading
rib.rectangle([rx, by + 6 * S, rx + 3 * S, ty2], fill=GOLD_HI)

# ---------- downscale ----------
out = bg.resize((W // S, H // S), Image.LANCZOS)
out.save("/root/MonoClaw/lumen/art/lumen-journal.png", "PNG")
# also a smaller web copy
out.resize((int(W/S*0.8), int(H/S*0.8)), Image.LANCZOS)
print("saved", out.size)
