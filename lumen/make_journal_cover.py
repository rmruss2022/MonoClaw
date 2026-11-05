#!/usr/bin/env python3
"""Front-cover PDF for The Lumen Journal — full-bleed 6x9in (+0.125in bleed),
print-spec, brand-matched. The final wrap (back + spine) is assembled on Lulu's
exact template once binding/paper are chosen (spine width depends on page count).
"""
import math
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FL = "/usr/share/fonts/truetype/liberation/"
FD = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Serif-Bold", FL + "LiberationSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Italic", FL + "LiberationSerif-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans", FD + "DejaVuSans.ttf"))

BLEED = 0.125 * inch
W, H = 6 * inch + 2 * BLEED, 9 * inch + 2 * BLEED
NAVY = HexColor("#141229")
NAVY2 = HexColor("#1d1740")
GOLD = HexColor("#c79a3a")
GOLDL = HexColor("#e7c877")
CREAM = HexColor("#efe7d4")

c = canvas.Canvas("/root/MonoClaw/lumen/print/lumen-journal-cover-front.pdf", pagesize=(W, H))

# background: deep navy with a soft violet glow toward the top (banded fill)
steps = 120
for i in range(steps):
    t = i / (steps - 1)
    # blend NAVY2 (top) -> NAVY (bottom)
    r = NAVY2.red + (NAVY.red - NAVY2.red) * t
    g = NAVY2.green + (NAVY.green - NAVY2.green) * t
    b = NAVY2.blue + (NAVY.blue - NAVY2.blue) * t
    c.setFillColorRGB(r, g, b)
    c.rect(0, H - (i + 1) * H / steps, W, H / steps + 1, stroke=0, fill=1)

cx = W / 2
# faint concentric mandala rings behind the emblem
c.setStrokeColor(HexColor("#2a2350"))
for rr in (2.2, 1.7, 1.2):
    c.setLineWidth(0.8)
    c.circle(cx, H - 3.0 * inch, rr * inch, stroke=1, fill=0)

# gold sunburst emblem
ex, ey, R = cx, H - 3.0 * inch, 0.62 * inch
c.setStrokeColor(GOLDL); c.setLineWidth(1.6)
for i in range(16):
    a = math.radians(i * 22.5)
    c.line(ex + math.cos(a) * R * 0.52, ey + math.sin(a) * R * 0.52,
           ex + math.cos(a) * R, ey + math.sin(a) * R)
c.setStrokeColor(GOLD); c.setLineWidth(1.4)
c.circle(ex, ey, R * 0.34, stroke=1, fill=0)
c.setFillColor(GOLDL); c.circle(ex, ey, R * 0.1, stroke=0, fill=1)

# title
c.setFillColor(CREAM); c.setFont("Serif-Bold", 33)
c.drawCentredString(cx, H - 4.6 * inch, "The Lumen")
c.drawCentredString(cx, H - 5.18 * inch, "Journal")

# gold rule
c.setStrokeColor(GOLD); c.setLineWidth(1.0)
c.line(cx - 0.6 * inch, H - 5.55 * inch, cx + 0.6 * inch, H - 5.55 * inch)

# subtitle
c.setFillColor(GOLDL); c.setFont("Serif-Italic", 13)
c.drawCentredString(cx, H - 5.95 * inch, "A guided companion for the quiet work")

# bottom wordmark + line
c.setFillColor(HexColor("#9890b8")); c.setFont("Sans", 8.5)
c.drawCentredString(cx, 1.35 * inch, "P I L L A R S   ·   S E A S O N S   ·   D A I L Y   L E T T E R S")
c.setFillColor(GOLDL); c.setFont("Sans", 10)
c.drawCentredString(cx, 0.95 * inch, "L U M E N")

c.save()
print("wrote: /root/MonoClaw/lumen/print/lumen-journal-cover-front.pdf", W / inch, "x", H / inch, "in")
