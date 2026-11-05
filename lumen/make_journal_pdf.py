#!/usr/bin/env python3
"""Generate the print-ready interior PDF for The Lumen Journal, straight from the
app's own guided content (the 8 pillar lesson plans, the Season program, and the
daily prompts). Output is a 6x9in book ready to upload to Lulu (or any POD that
takes a custom interior PDF).

Usage: python3 make_journal_pdf.py            -> writes print/lumen-journal-interior.pdf
"""
import os, importlib.util
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---- pull the live content out of the app ---------------------------------
os.environ.setdefault("LUMEN_DB", "/tmp/lumen_pdf_build.db")
_spec = importlib.util.spec_from_file_location("lsrv", "/root/MonoClaw/lumen/server.py")
L = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(L)
PILLARS, PLANS, SEASON, PROMPTS = L.PILLARS, L.PILLAR_PLANS, L.SEASON_PLAN, L.PROMPTS

# ---- fonts -----------------------------------------------------------------
FD = "/usr/share/fonts/truetype/dejavu/"
FL = "/usr/share/fonts/truetype/liberation/"
pdfmetrics.registerFont(TTFont("Serif", FL + "LiberationSerif-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Bold", FL + "LiberationSerif-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Serif-Italic", FL + "LiberationSerif-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans", FD + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", FD + "DejaVuSans-Bold.ttf"))

# ---- page + palette --------------------------------------------------------
PW, PH = 6 * inch, 9 * inch
MT, MB, ML, MR = 0.78 * inch, 0.72 * inch, 0.8 * inch, 0.62 * inch
INK = HexColor("#1b1626")
GOLD = HexColor("#b2862f")
MUT = HexColor("#6f6886")
DOT = HexColor("#d8d3e1")
LINE = HexColor("#e7e3ee")

c = canvas.Canvas("/root/MonoClaw/lumen/print/lumen-journal-interior.pdf", pagesize=(PW, PH))
_page = {"n": 0}


def emblem(cx, cy, r, col=GOLD, w=1.0):
    import math
    c.setStrokeColor(col); c.setLineWidth(w)
    for i in range(12):
        a = math.radians(i * 30)
        c.line(cx + math.cos(a) * r * 0.55, cy + math.sin(a) * r * 0.55,
               cx + math.cos(a) * r, cy + math.sin(a) * r)
    c.circle(cx, cy, r * 0.34, stroke=1, fill=0)
    c.setFillColor(col); c.circle(cx, cy, r * 0.1, stroke=0, fill=1)


def newpage(folio=True):
    if _page["n"] > 0:
        c.showPage()
    _page["n"] += 1
    if folio and _page["n"] > 2:
        c.setFont("Sans", 7.5); c.setFillColor(MUT)
        c.drawCentredString(PW / 2, 0.42 * inch, str(_page["n"]))


def wrap(text, font, size, maxw):
    c.setFont(font, size)
    out, line = [], ""
    for word in text.split():
        t = (line + " " + word).strip()
        if pdfmetrics.stringWidth(t, font, size) <= maxw:
            line = t
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def para(x, y, text, font, size, color, maxw, leading=None, align="l"):
    leading = leading or size * 1.42
    c.setFillColor(color)
    for ln in wrap(text, font, size, maxw):
        c.setFont(font, size)
        if align == "c":
            c.drawCentredString(x + maxw / 2, y, ln)
        else:
            c.drawString(x, y, ln)
        y -= leading
    return y


def dotgrid(x0, y_top, y_bot, step=0.26 * inch):
    c.setFillColor(DOT)
    yy = y_top
    while yy > y_bot:
        xx = x0
        while xx < PW - MR + 1:
            c.circle(xx, yy, 0.6, stroke=0, fill=1)
            xx += step
        yy -= step


def ruled(y_top, y_bot, step=0.34 * inch):
    c.setStrokeColor(LINE); c.setLineWidth(0.6)
    yy = y_top
    while yy > y_bot:
        c.line(ML, yy, PW - MR, yy)
        yy -= step


CONTENT_W = PW - ML - MR

# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------
newpage(folio=False)  # title
emblem(PW / 2, PH - 2.4 * inch, 0.5 * inch, GOLD, 1.3)
c.setFillColor(INK); c.setFont("Serif-Bold", 30)
c.drawCentredString(PW / 2, PH - 3.5 * inch, "The Lumen Journal")
c.setFillColor(MUT); c.setFont("Serif-Italic", 13)
c.drawCentredString(PW / 2, PH - 3.95 * inch, "A guided companion for the quiet work")
c.setStrokeColor(GOLD); c.setLineWidth(0.8)
c.line(PW / 2 - 0.5 * inch, PH - 4.3 * inch, PW / 2 + 0.5 * inch, PH - 4.3 * inch)
c.setFillColor(MUT); c.setFont("Sans", 9)
c.drawCentredString(PW / 2, 1.1 * inch, "LUMEN")

newpage(folio=False)  # belongs to
y = PH - 3.2 * inch
c.setFillColor(MUT); c.setFont("Sans", 9)
c.drawCentredString(PW / 2, y, "THIS JOURNAL BELONGS TO")
c.setStrokeColor(LINE); c.setLineWidth(0.8)
c.line(ML + 0.3 * inch, y - 0.5 * inch, PW - MR - 0.3 * inch, y - 0.5 * inch)
c.setFillColor(MUT); c.setFont("Serif-Italic", 11)
y2 = para(ML, 2.4 * inch,
          "The practice is simple: show up for yourself on the page, a few honest "
          "lines, most days. Not for anyone else — for the quiet it gives back.",
          "Serif-Italic", 11, MUT, CONTENT_W, 17, "c")

# How to use
newpage()
c.setFillColor(GOLD); c.setFont("Sans-Bold", 9.5)
c.drawString(ML, PH - MT, "HOW TO USE THIS JOURNAL")
c.setFillColor(INK); c.setFont("Serif-Bold", 20)
c.drawString(ML, PH - MT - 0.42 * inch, "Three ways to meet yourself")
y = PH - MT - 1.0 * inch
for t, d in [
    ("The Pillars", "Eight areas of a life. Each is a short course of guided sittings — "
     "work them in order, one chapter at a time, at whatever pace is yours."),
    ("The Season", "Six sittings to name and tend the chapter of life you're living "
     "through right now, and to keep returning to it as it changes."),
    ("Daily Letters", "A short, honest letter to today. A prompt to begin, then the "
     "page is yours."),
]:
    c.setFillColor(GOLD); c.setFont("Serif-Bold", 13); c.drawString(ML, y, t)
    y -= 0.28 * inch
    y = para(ML, y, d, "Serif", 10.5, INK, CONTENT_W, 15.5) - 0.28 * inch


def section_divider(kicker, title, blurb=""):
    newpage(folio=False)
    emblem(PW / 2, PH - 3.0 * inch, 0.42 * inch, GOLD, 1.1)
    c.setFillColor(GOLD); c.setFont("Sans-Bold", 9.5)
    c.drawCentredString(PW / 2, PH - 3.9 * inch, kicker)
    c.setFillColor(INK); c.setFont("Serif-Bold", 26)
    c.drawCentredString(PW / 2, PH - 4.45 * inch, title)
    if blurb:
        para(ML + 0.3 * inch, PH - 5.0 * inch, blurb, "Serif-Italic", 11.5, MUT,
             CONTENT_W - 0.6 * inch, 17, "c")


def sitting(kicker, title, invitation, steps, writing_pages=2):
    # heading page: title + invitation + the steps
    newpage()
    c.setFillColor(GOLD); c.setFont("Sans-Bold", 9)
    c.drawString(ML, PH - MT, kicker.upper())
    c.setFillColor(INK); c.setFont("Serif-Bold", 19)
    yy = PH - MT - 0.44 * inch
    for ln in wrap(title, "Serif-Bold", 19, CONTENT_W):
        c.drawString(ML, yy, ln); yy -= 0.32 * inch
    yy -= 0.04 * inch
    yy = para(ML, yy, invitation, "Serif-Italic", 12, MUT, CONTENT_W, 17.5)
    yy -= 0.14 * inch
    c.setStrokeColor(GOLD); c.setLineWidth(0.8); c.line(ML, yy, ML + 0.6 * inch, yy)
    yy -= 0.34 * inch
    for i, s in enumerate(steps):
        c.setFillColor(GOLD); c.setFont("Serif-Bold", 12)
        c.drawString(ML, yy, str(i + 1))
        yy = para(ML + 0.32 * inch, yy, s, "Serif", 11, INK, CONTENT_W - 0.32 * inch, 15.8)
        yy -= 0.22 * inch
    # writing pages (dot grid)
    for _ in range(writing_pages):
        newpage()
        dotgrid(ML, PH - MT, MB)


# ---------------------------------------------------------------------------
# Part I — the pillars
# ---------------------------------------------------------------------------
section_divider("Part One", "The Eight Pillars",
                "The areas of a life worth tending. Work each as a path, one honest sitting at a time.")
for pillar in PILLARS:
    arc, chapters = PLANS[pillar]
    section_divider(pillar.upper(), pillar, arc)
    for i, (title, invitation, steps) in enumerate(chapters):
        sitting("%s · Chapter %d of %d" % (pillar, i + 1, len(chapters)),
                title, invitation, steps, writing_pages=2)

# ---------------------------------------------------------------------------
# Part II — the season
# ---------------------------------------------------------------------------
section_divider("Part Two", "The Season You're In",
                "Name the chapter of life you're living through — and keep returning to tend it.")
for i, (title, invitation, steps) in enumerate(SEASON):
    sitting("The Season · Chapter %d of %d" % (i + 1, len(SEASON)),
            title, invitation, steps, writing_pages=2)

# ---------------------------------------------------------------------------
# Part III — daily letters (prompts cycle; plenty of dated pages)
# ---------------------------------------------------------------------------
section_divider("Part Three", "Daily Letters",
                "A short, honest letter to today. Begin with the prompt, then the page is yours.")
DAILY_PAGES = 60
for i in range(DAILY_PAGES):
    newpage()
    c.setFillColor(MUT); c.setFont("Sans", 8.5)
    c.drawString(ML, PH - MT, "DATE")
    c.setStrokeColor(LINE); c.setLineWidth(0.7)
    c.line(ML + 0.5 * inch, PH - MT - 1, ML + 2.0 * inch, PH - MT - 1)
    c.drawString(ML + 2.4 * inch, PH - MT, "")
    c.setFont("Sans", 8.5); c.drawString(ML + 2.3 * inch, PH - MT, "FELT")
    c.line(ML + 2.9 * inch, PH - MT - 1, PW - MR, PH - MT - 1)
    q = PROMPTS[i % len(PROMPTS)]
    c.setFillColor(INK)
    yy = para(ML, PH - MT - 0.42 * inch, "“" + q + "”", "Serif-Italic", 12.5,
              INK, CONTENT_W, 17.5)
    yy -= 0.1 * inch
    ruled(yy, MB + 0.1 * inch)

# closing
newpage(folio=False)
emblem(PW / 2, PH / 2 + 0.3 * inch, 0.4 * inch, GOLD, 1.1)
para(ML + 0.3 * inch, PH / 2 - 0.3 * inch,
     "Keep returning. The practice is only ever returning.",
     "Serif-Italic", 13, MUT, CONTENT_W - 0.6 * inch, 19, "c")

c.save()
print("pages:", _page["n"])
print("wrote: /root/MonoClaw/lumen/print/lumen-journal-interior.pdf")
