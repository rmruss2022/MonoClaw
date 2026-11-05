#!/usr/bin/env python3
"""
Lumen — App Store screenshot set generator.
Pixel-exact 1290x2796 (iPhone 6.7") marketing screenshots, rendered via rsvg-convert.
Voice + palette pulled from the app itself (NARRATOR.md, server.py, icon.svg).

Positioning: "the meditation app you'll actually keep doing" — a daily habit built
like a game, for the 18-30 audience that bounces off Calm/Headspace. Lead with the
two unique scroll-stoppers (living map + journey timelapse).
Story flow (hook -> map -> timelapse -> sit -> retention -> depth -> reflection):
  01 hook      Meditation you'll actually keep.
  02 map       Every breath lights up the world.
  03 journey   Watch your sit travel the earth.   (timelapse replay)
  04 meditate  Press play. Just breathe.
  05 progress  The streak that brings you back.
  06 journeys  Sit with the Stoics. Or with yourself.
  07 journal   End each sit with a letter to yourself.
"""
import base64, math, os, random, subprocess

W, H = 1290, 2796
HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), "art")
OUT = HERE

# ---- Lumen palette (from server.py / icon.svg) ----
GOLD   = "#f5c977"
GOLD_L = "#ffe9b8"
GOLD_D = "#e0953a"
VIOLET = "#c084fc"
VIO_D  = "#7c3aed"
PURPLE = "#a855f7"
PINK   = "#ec4899"
PINK_L = "#f5a9d0"
TEAL   = "#5fd0c8"
GREEN  = "#6ee7b7"
BLUE   = "#5fb0fa"
INK    = "#0b0a12"
PANEL  = "#140f24"
PANEL2 = "#1a1330"
TXT    = "#ece9f5"
MUT    = "#9a93b8"
FAINT  = "#cbbfe6"

SERIF = "Liberation Serif, DejaVu Serif, serif"
SANS  = "DejaVu Sans, sans-serif"

# Phone geometry (frames 2-6)
PX, PY, PW, PH, BEZ, RAD = 225, 912, 840, 1770, 26, 96
SX, SY = PX + BEZ, PY + BEZ
SW, SH = PW - 2 * BEZ, PH - 2 * BEZ
SRAD = RAD - BEZ


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def b64img(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def defs():
    return f'''
  <defs>
    <radialGradient id="bg" cx="50%" cy="30%" r="85%">
      <stop offset="0%" stop-color="#1d1636"/>
      <stop offset="55%" stop-color="#120e22"/>
      <stop offset="100%" stop-color="{INK}"/>
    </radialGradient>
    <radialGradient id="orb" cx="50%" cy="38%" r="62%">
      <stop offset="0%" stop-color="{GOLD_L}"/>
      <stop offset="42%" stop-color="{GOLD}"/>
      <stop offset="76%" stop-color="{VIOLET}"/>
      <stop offset="100%" stop-color="#6d28d9"/>
    </radialGradient>
    <linearGradient id="head" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{GOLD_L}"/>
      <stop offset="55%" stop-color="{GOLD}"/>
      <stop offset="100%" stop-color="{PINK_L}"/>
    </linearGradient>
    <linearGradient id="screenbg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#17112b"/>
      <stop offset="100%" stop-color="{INK}"/>
    </linearGradient>
    <radialGradient id="softorb" cx="50%" cy="45%" r="60%">
      <stop offset="0%" stop-color="{GOLD_L}"/>
      <stop offset="50%" stop-color="{GOLD}"/>
      <stop offset="100%" stop-color="{VIO_D}"/>
    </radialGradient>
    <filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="16" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glowS" x="-120%" y="-120%" width="340%" height="340%">
      <feGaussianBlur stdDeviation="7"/>
    </filter>
    <filter id="softsh" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="30"/>
    </filter>
    <clipPath id="screen"><rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="{SRAD}"/></clipPath>
  </defs>'''


def background(seed=1):
    r = random.Random(seed)
    dots = []
    for _ in range(90):
        x, y = r.uniform(0, W), r.uniform(0, H)
        rad = r.uniform(1.2, 3.6)
        op = r.uniform(0.05, 0.4)
        col = r.choice([GOLD, GOLD, VIOLET, "#ffffff", PINK_L])
        dots.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad:.1f}" fill="{col}" opacity="{op:.2f}"/>')
    return f'<rect width="{W}" height="{H}" fill="url(#bg)"/>\n<g>{"".join(dots)}</g>'


def logo_mark(cx, cy, r, rays=True):
    """The Lumen orb mark."""
    s = f'<g filter="url(#glow)"><circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#orb)"/>'
    if rays:
        rl, ro = r * 1.32, r * 1.68
        s += f'<g stroke="{GOLD}" stroke-width="{max(3,r*0.05):.0f}" stroke-linecap="round" opacity="0.9">'
        for i in range(8):
            a = math.radians(i * 45)
            x1, y1 = cx + math.cos(a) * rl, cy + math.sin(a) * rl
            x2, y2 = cx + math.cos(a) * ro, cy + math.sin(a) * ro
            s += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"/>'
        s += '</g>'
    s += '</g>'
    return s


def headline(lines, sub_lines, y0=236, size=92, align="middle", x=W / 2, color="url(#head)"):
    lh = size * 1.06
    tspans = "".join(
        f'<tspan x="{x:.0f}" dy="{0 if i==0 else lh:.0f}">{esc(t)}</tspan>' for i, t in enumerate(lines))
    s = (f'<text x="{x:.0f}" y="{y0}" font-family="{SERIF}" font-weight="bold" '
         f'font-size="{size}" fill="{color}" text-anchor="{align}" '
         f'letter-spacing="-1">{tspans}</text>')
    sy = y0 + lh * (len(lines) - 1) + 86
    subt = "".join(
        f'<tspan x="{x:.0f}" dy="{0 if i==0 else 54:.0f}">{esc(t)}</tspan>' for i, t in enumerate(sub_lines))
    s += (f'<text x="{x:.0f}" y="{sy}" font-family="{SANS}" font-size="38" fill="{MUT}" '
          f'text-anchor="{align}" letter-spacing="0.3">{subt}</text>')
    return s


def phone(inner):
    """Device frame + clipped screen content (screen-local coords, origin SX,SY)."""
    return f'''
  <g filter="url(#softsh)"><rect x="{PX}" y="{PY+18}" width="{PW}" height="{PH}" rx="{RAD}" fill="#000" opacity="0.55"/></g>
  <rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="{RAD}" fill="#05040a" stroke="#2a2342" stroke-width="2"/>
  <rect x="{PX+6}" y="{PY+6}" width="{PW-12}" height="{PH-12}" rx="{RAD-6}" fill="none" stroke="#3a3356" stroke-width="2" opacity="0.6"/>
  <rect x="{SX}" y="{SY}" width="{SW}" height="{SH}" rx="{SRAD}" fill="url(#screenbg)"/>
  <g clip-path="url(#screen)"><g transform="translate({SX},{SY})">
  {inner}
  </g></g>
  <rect x="{W/2-62:.0f}" y="{PY+30}" width="124" height="34" rx="17" fill="#000"/>'''


def statusbar():
    return (f'<text x="46" y="60" font-family="{SANS}" font-weight="bold" font-size="30" fill="{TXT}">9:41</text>'
            f'<g fill="{TXT}"><rect x="{SW-120}" y="40" width="34" height="18" rx="4"/>'
            f'<rect x="{SW-78}" y="40" width="26" height="18" rx="4"/>'
            f'<rect x="{SW-44}" y="38" width="40" height="22" rx="5" opacity="0.5"/>'
            f'<rect x="{SW-42}" y="40" width="30" height="18" rx="3"/></g>')


def chip(x, y, w, h, text, fill, tcol, fs=28, icon=""):
    return (f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}"/>'
            f'<text x="{x+w/2}" y="{y+h/2+fs*0.36:.0f}" font-family="{SANS}" font-weight="bold" '
            f'font-size="{fs}" fill="{tcol}" text-anchor="middle">{icon}{esc(text)}</text></g>')


# =================== SCENES ===================

def scene_hook():
    s = background(7)
    s += headline(["Meditation you'll", "actually keep."],
                  ["A daily practice built like a game —", "not a library you feel guilty about."],
                  y0=360, size=118)
    cx, cy = W / 2, 1760
    # halo
    s += f'<circle cx="{cx}" cy="{cy}" r="560" fill="{GOLD}" opacity="0.06" filter="url(#softsh)"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="360" fill="{VIOLET}" opacity="0.08" filter="url(#softsh)"/>'
    s += logo_mark(cx, cy, 300)
    # teaser ring of world-pins at the base
    r = random.Random(3)
    pins = ""
    for i in range(26):
        a = math.radians(188 + i * (164 / 25))
        rr = 520 + r.uniform(-18, 18)
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr * 0.62 + 120
        br = r.uniform(0.4, 1)
        pins += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{4+br*7:.1f}" fill="{GOLD}" opacity="{0.25+br*0.6:.2f}" filter="url(#glowS)"/>'
    s += f'<g>{pins}</g>'
    s += (f'<text x="{cx}" y="2660" font-family="{SANS}" font-size="34" fill="{MUT}" '
          f'text-anchor="middle" letter-spacing="2">LUMEN &#183; LIGHT MEDITATION</text>')
    return s


def world_pins(n, seed):
    """Glowing globe of lights for the map scene."""
    cx, cy, R = SW / 2, 560, 300
    r = random.Random(seed)
    g = f'<circle cx="{cx}" cy="{cy}" r="{R+40}" fill="{BLUE}" opacity="0.06" filter="url(#softsh)"/>'
    g += f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#0c1430" stroke="#20325f" stroke-width="2"/>'
    # meridians / parallels
    for k in range(1, 4):
        rx = R * k / 4
        g += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.0f}" ry="{R}" fill="none" stroke="#24407a" stroke-width="1.4" opacity="0.5"/>'
        ry = R * k / 4
        g += f'<ellipse cx="{cx}" cy="{cy}" rx="{R}" ry="{ry:.0f}" fill="none" stroke="#24407a" stroke-width="1.4" opacity="0.5"/>'
    g += f'<line x1="{cx}" y1="{cy-R}" x2="{cx}" y2="{cy+R}" stroke="#24407a" stroke-width="1.4" opacity="0.5"/>'
    g += f'<line x1="{cx-R}" y1="{cy}" x2="{cx+R}" y2="{cy}" stroke="#24407a" stroke-width="1.4" opacity="0.5"/>'
    pins = ""
    placed = 0
    while placed < n:
        a = r.uniform(0, 2 * math.pi)
        rad = R * math.sqrt(r.uniform(0, 1)) * 0.94
        x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad * 0.98
        br = r.uniform(0.35, 1)
        col = r.choice([GOLD, GOLD, GOLD, TEAL, PINK_L, BLUE])
        pins += (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{10+br*10:.0f}" fill="{col}" opacity="{br*0.5:.2f}" filter="url(#glowS)"/>'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{3+br*3.5:.1f}" fill="{col}"/>')
        placed += 1
    return g + pins


def scene_map():
    s = statusbar()
    s += (f'<text x="{SW/2}" y="150" font-family="{SERIF}" font-weight="bold" font-size="52" '
          f'fill="{TXT}" text-anchor="middle">The world, lit tonight</text>')
    s += world_pins(70, 11)
    # count card
    cw, cy0 = 520, 1000
    cx = (SW - cw) / 2
    s += f'<rect x="{cx}" y="{cy0}" width="{cw}" height="150" rx="34" fill="{PANEL2}" stroke="#2e2747" stroke-width="2"/>'
    s += logo_mark(cx + 86, cy0 + 75, 34)
    s += (f'<text x="{cx+150}" y="{cy0+66}" font-family="{SANS}" font-weight="bold" font-size="56" fill="{GOLD}">2,418</text>'
          f'<text x="{cx+150}" y="{cy0+116}" font-family="{SANS}" font-size="30" fill="{MUT}">lights today &#183; 112 cities</text>')
    # a popup pin label
    s += f'<g><rect x="{SW/2-170}" y="300" width="340" height="96" rx="22" fill="#14101f" stroke="{GOLD}" stroke-width="2" opacity="0.96"/>'
    s += (f'<text x="{SW/2}" y="342" font-family="{SANS}" font-weight="bold" font-size="30" fill="{TXT}" text-anchor="middle">Kyoto &#183; just now</text>'
          f'<text x="{SW/2}" y="378" font-family="{SANS}" font-size="26" fill="{TEAL}" text-anchor="middle">forest &#183; 20 min</text></g>')
    # tab bar hint
    s += nav_bar(active=1)
    return s


def nav_bar(active=0):
    labels = ["Meditate", "Map", "Journeys", "Journal", "Collect"]
    y = SH - 118
    s = f'<rect x="0" y="{y}" width="{SW}" height="118" fill="#0c0a16"/><line x1="0" y1="{y}" x2="{SW}" y2="{y}" stroke="#241d3a" stroke-width="1.5"/>'
    n = len(labels)
    for i, lab in enumerate(labels):
        cx = SW * (i + 0.5) / n
        col = GOLD if i == active else MUT
        s += f'<circle cx="{cx:.0f}" cy="{y+40}" r="7" fill="{col}"/>'
        s += f'<text x="{cx:.0f}" y="{y+88}" font-family="{SANS}" font-size="23" fill="{col}" text-anchor="middle">{lab}</text>'
    return s


def scene_meditate():
    s = statusbar()
    s += (f'<text x="{SW/2}" y="150" font-family="{SERIF}" font-weight="bold" font-size="52" '
          f'fill="{TXT}" text-anchor="middle">Breathe</text>')
    s += (f'<text x="{SW/2}" y="202" font-family="{SANS}" font-size="30" fill="{MUT}" '
          f'text-anchor="middle">Ki, your fox, is sitting with you</text>')
    cx, cy, R = SW / 2, 560, 250
    # progress ring
    s += f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#241d3a" stroke-width="22"/>'
    # arc ~70%
    frac = 0.68
    a0 = -math.pi / 2
    a1 = a0 + 2 * math.pi * frac
    large = 1 if frac > 0.5 else 0
    x0, y0 = cx + R * math.cos(a0), cy + R * math.sin(a0)
    x1, y1 = cx + R * math.cos(a1), cy + R * math.sin(a1)
    s += (f'<path d="M {x0:.1f} {y0:.1f} A {R} {R} 0 {large} 1 {x1:.1f} {y1:.1f}" '
          f'fill="none" stroke="{GOLD}" stroke-width="22" stroke-linecap="round" filter="url(#glow)"/>')
    s += f'<circle cx="{cx}" cy="{cy}" r="{R-54}" fill="url(#softorb)" opacity="0.9" filter="url(#glow)"/>'
    s += (f'<text x="{cx}" y="{cy+6}" font-family="{SANS}" font-weight="bold" font-size="104" fill="#1a1330" text-anchor="middle">8:12</text>'
          f'<text x="{cx}" y="{cy+66}" font-family="{SANS}" font-size="30" fill="#4a3d6b" text-anchor="middle">of 12:00</text>')
    # companion dot
    s += logo_mark(cx + 150, cy - 210, 26)
    # soundscape pills
    scenes = [("Ocean", TEAL, 1), ("Rain", BLUE, 0), ("Forest", GREEN, 0), ("Space", VIOLET, 0)]
    pw, gap = 168, 20
    total = pw * len(scenes) + gap * (len(scenes) - 1)
    x = (SW - total) / 2
    for lab, col, act in scenes:
        fill = col if act else PANEL2
        tcol = "#10121a" if act else MUT
        s += chip(x, 920, pw, 76, lab, fill, tcol, 30)
        x += pw + gap
    # light earned card
    cw = 640
    cx2 = (SW - cw) / 2
    s += f'<rect x="{cx2}" y="1050" width="{cw}" height="150" rx="34" fill="{PANEL}" stroke="#2e2747" stroke-width="2"/>'
    s += (f'<text x="{cx2+40}" y="1118" font-family="{SANS}" font-size="30" fill="{MUT}">Light earned today</text>'
          f'<text x="{cx2+40}" y="1172" font-family="{SANS}" font-weight="bold" font-size="48" fill="{GOLD}">+480 &#9728;</text>')
    s += (f'<text x="{cx2+cw-40}" y="1118" font-family="{SANS}" font-size="30" fill="{MUT}" text-anchor="end">Streak</text>'
          f'<text x="{cx2+cw-40}" y="1172" font-family="{SANS}" font-weight="bold" font-size="48" fill="{PINK_L}" text-anchor="end">41 &#128293;</text>')
    s += nav_bar(active=0)
    return s


def scene_journeys():
    s = statusbar()
    s += (f'<text x="48" y="150" font-family="{SERIF}" font-weight="bold" font-size="54" fill="{TXT}">Guided journeys</text>')
    s += (f'<text x="48" y="206" font-family="{SANS}" font-size="30" fill="{MUT}">One teacher. Breath, and the old paths.</text>')
    cards = [
        ("lesson_breath.png", "Breath &amp; the Nervous System", "Foundations &#183; the physiological sigh", GREEN, "New"),
        ("lesson_vishnu.png", "Vishnu, the Preserver", "Devotion &#183; sustenance &amp; true change", GOLD, "3 lessons"),
        ("lesson_shiva.png", "Shiva, the Transformer", "Devotion &#183; stillness &amp; the long exhale", VIOLET, "5 lessons"),
        ("lesson_lakshmi.png", "Lakshmi, the Abundant", "Devotion &#183; the heart in coherence", PINK_L, "4 lessons"),
    ]
    y = 260
    ch = 318
    for fn, title, sub, col, tag in cards:
        p = os.path.join(ART, fn)
        s += f'<g><rect x="40" y="{y}" width="{SW-80}" height="{ch-26}" rx="34" fill="{PANEL}" stroke="#241d3a" stroke-width="2"/>'
        # thumb
        tw = 250
        s += f'<clipPath id="c{y}"><rect x="40" y="{y}" width="{tw}" height="{ch-26}" rx="34"/></clipPath>'
        if os.path.exists(p):
            s += f'<image x="40" y="{y}" width="{tw}" height="{ch-26}" href="{b64img(p)}" preserveAspectRatio="xMidYMid slice" clip-path="url(#c{y})"/>'
        s += f'<rect x="40" y="{y}" width="{tw}" height="{ch-26}" rx="34" fill="none" clip-path="url(#c{y})"/>'
        tx = 40 + tw + 36
        s += (f'<text x="{tx}" y="{y+86}" font-family="{SERIF}" font-weight="bold" font-size="40" fill="{TXT}">{title}</text>'
              f'<text x="{tx}" y="{y+140}" font-family="{SANS}" font-size="28" fill="{MUT}">{sub}</text>')
        s += chip(tx, y + 178, 180, 56, tag, "#241d3a", col, 26)
        s += '</g>'
        y += ch
    s += nav_bar(active=2)
    return s


def mandala(cx, cy, R, lit=9, total=12):
    cats = [GOLD, VIOLET, PINK, TEAL, BLUE, GREEN]
    s = f'<circle cx="{cx}" cy="{cy}" r="{R+24}" fill="{GOLD}" opacity="0.07" filter="url(#softsh)"/>'
    for i in range(total):
        a0 = math.radians(i * 360 / total - 90)
        a1 = math.radians((i + 1) * 360 / total - 90)
        am = (a0 + a1) / 2
        tip = R
        base = R * 0.30
        wq = R * 0.52
        x0, y0 = cx + math.cos(am) * tip, cy + math.sin(am) * tip
        xb1, yb1 = cx + math.cos(a0) * base, cy + math.sin(a0) * base
        xb2, yb2 = cx + math.cos(a1) * base, cy + math.sin(a1) * base
        xw1, yw1 = cx + math.cos(a0) * wq, cy + math.sin(a0) * wq
        xw2, yw2 = cx + math.cos(a1) * wq, cy + math.sin(a1) * wq
        col = cats[i % len(cats)]
        on = i < lit
        fill = col if on else "#241d3a"
        op = "0.95" if on else "0.5"
        flt = ' filter="url(#glow)"' if on else ''
        s += (f'<path d="M {xb1:.1f} {yb1:.1f} Q {xw1:.1f} {yw1:.1f} {x0:.1f} {y0:.1f} '
              f'Q {xw2:.1f} {yw2:.1f} {xb2:.1f} {yb2:.1f} Z" fill="{fill}" opacity="{op}" '
              f'stroke="#0b0a12" stroke-width="3"{flt}/>')
    s += f'<circle cx="{cx}" cy="{cy}" r="{R*0.30}" fill="url(#softorb)" filter="url(#glow)"/>'
    return s


def scene_progress():
    s = statusbar()
    s += (f'<text x="{SW/2}" y="150" font-family="{SERIF}" font-weight="bold" font-size="52" '
          f'fill="{TXT}" text-anchor="middle">Your light, gathering</text>')
    s += mandala(SW / 2, 470, 280, lit=9)
    # stat row
    stats = [("41", "day streak", PINK_L), ("Lv 12", "9,240 Light", GOLD), ("Flare", "league", VIOLET)]
    cw, gap = 230, 24
    total = cw * 3 + gap * 2
    x = (SW - total) / 2
    for big, small, col in stats:
        s += f'<rect x="{x}" y="820" width="{cw}" height="150" rx="28" fill="{PANEL}" stroke="#241d3a" stroke-width="2"/>'
        s += (f'<text x="{x+cw/2}" y="892" font-family="{SANS}" font-weight="bold" font-size="52" fill="{col}" text-anchor="middle">{big}</text>'
              f'<text x="{x+cw/2}" y="938" font-family="{SANS}" font-size="27" fill="{MUT}" text-anchor="middle">{small}</text>')
        x += cw + gap
    # league ladder
    leagues = [("Ember", 0), ("Spark", 0), ("Glow", 0), ("Flare", 1), ("Beacon", 0), ("Nova", 0)]
    s += f'<rect x="40" y="1010" width="{SW-80}" height="200" rx="30" fill="{PANEL2}" stroke="#2e2747" stroke-width="2"/>'
    s += f'<text x="70" y="1070" font-family="{SANS}" font-weight="bold" font-size="30" fill="{TXT}">This week\'s league</text>'
    n = len(leagues)
    bx = 70
    bw = (SW - 80 - 60) / n
    for i, (lab, act) in enumerate(leagues):
        cx = bx + bw * (i + 0.5)
        col = GOLD if act else MUT
        rr = 20 if act else 12
        s += f'<circle cx="{cx:.0f}" cy="1130" r="{rr}" fill="{col}" {"filter=" + chr(34) + "url(#glow)" + chr(34) if act else ""}/>'
        s += f'<text x="{cx:.0f}" y="1190" font-family="{SANS}" font-size="24" fill="{col}" text-anchor="middle" font-weight="{"bold" if act else "normal"}">{lab}</text>'
        if i < n - 1:
            s += f'<line x1="{cx+rr+6:.0f}" y1="1130" x2="{bx+bw*(i+1.5)-rr-6:.0f}" y2="1130" stroke="#3a3356" stroke-width="3"/>'
    s += nav_bar(active=4)
    return s


def scene_journal():
    s = statusbar()
    s += (f'<text x="{SW/2}" y="150" font-family="{SERIF}" font-weight="bold" font-size="52" '
          f'fill="{TXT}" text-anchor="middle">A letter to yourself</text>')
    # parchment letter
    lx, ly, lw, lh = 60, 230, SW - 120, 1120
    s += f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="26" fill="#f4ecd8"/>'
    s += f'<rect x="{lx}" y="{ly}" width="{lw}" height="{lh}" rx="26" fill="none" stroke="#d8c9a0" stroke-width="3"/>'
    s += (f'<text x="{lx+54}" y="{ly+96}" font-family="{SERIF}" font-style="italic" font-size="40" fill="#6b5a3a">Tuesday, after the sit &#8212;</text>')
    prompt = [
        "What did the quiet show you today",
        "that the noise had been hiding?",
    ]
    yy = ly + 190
    for ln in prompt:
        s += f'<text x="{lx+54}" y="{yy}" font-family="{SERIF}" font-size="46" fill="#2c2416">{esc(ln)}</text>'
        yy += 66
    # handwritten-ish answer lines
    yy += 40
    ans = [
        "That I'd been holding my shoulders",
        "like they were load-bearing. They",
        "aren't. The breath did the carrying,",
        "the way it always has.",
    ]
    for ln in ans:
        s += f'<text x="{lx+54}" y="{yy}" font-family="{SERIF}" font-style="italic" font-size="42" fill="#4a3d6b">{esc(ln)}</text>'
        yy += 72
    # ruled lines
    for k in range(3):
        s += f'<line x1="{lx+54}" y1="{yy+k*72-18}" x2="{lx+lw-54}" y2="{yy+k*72-18}" stroke="#ddd0ad" stroke-width="2"/>'
    # wax seal
    sx, sy = lx + lw - 150, ly + lh - 150
    s += f'<circle cx="{sx}" cy="{sy}" r="76" fill="{PINK}" opacity="0.9" filter="url(#glow)"/>'
    s += f'<circle cx="{sx}" cy="{sy}" r="60" fill="none" stroke="#fff" stroke-width="3" opacity="0.7"/>'
    s += logo_mark(sx, sy, 30, rays=False)
    s += f'<text x="{sx}" y="{sy+120}" font-family="{SANS}" font-weight="bold" font-size="28" fill="#8a7a55" text-anchor="middle" letter-spacing="3">SEALED</text>'
    # Keeper prompt bar
    ky = ly + lh + 60
    s += f'<rect x="60" y="{ky}" width="{SW-120}" height="120" rx="60" fill="{PANEL2}" stroke="{GOLD}" stroke-width="2"/>'
    s += logo_mark(140, ky + 60, 30)
    s += (f'<text x="210" y="{ky+56}" font-family="{SANS}" font-weight="bold" font-size="32" fill="{TXT}">Talk with the Keeper</text>'
          f'<text x="210" y="{ky+96}" font-family="{SANS}" font-size="27" fill="{MUT}">&#8220;Help me find the words.&#8221;</text>')
    s += nav_bar(active=3)
    return s


def scene_replay():
    """Journey timelapse: your sit replays as a glowing arc sweeping the globe."""
    s = statusbar()
    s += (f'<text x="{SW/2}" y="150" font-family="{SERIF}" font-weight="bold" font-size="52" '
          f'fill="{TXT}" text-anchor="middle">Today’s journey, replayed</text>')
    cx, cy, R = SW / 2, 560, 300
    # faint globe
    s += f'<circle cx="{cx}" cy="{cy}" r="{R+40}" fill="{BLUE}" opacity="0.06" filter="url(#softsh)"/>'
    s += f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#0c1430" stroke="#20325f" stroke-width="2"/>'
    for k in range(1, 4):
        rx = R * k / 4
        s += f'<ellipse cx="{cx}" cy="{cy}" rx="{rx:.0f}" ry="{R}" fill="none" stroke="#24407a" stroke-width="1.2" opacity="0.4"/>'
        ry = R * k / 4
        s += f'<ellipse cx="{cx}" cy="{cy}" rx="{R}" ry="{ry:.0f}" fill="none" stroke="#24407a" stroke-width="1.2" opacity="0.4"/>'
    s += f'<line x1="{cx}" y1="{cy-R}" x2="{cx}" y2="{cy+R}" stroke="#24407a" stroke-width="1.2" opacity="0.4"/>'
    s += f'<line x1="{cx-R}" y1="{cy}" x2="{cx+R}" y2="{cy}" stroke="#24407a" stroke-width="1.2" opacity="0.4"/>'
    # dim ambient lights
    r = random.Random(23)
    for _ in range(24):
        a = r.uniform(0, 2 * math.pi)
        rad = R * math.sqrt(r.uniform(0, 1)) * 0.92
        x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad * 0.98
        s += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3" fill="{GOLD}" opacity="0.22"/>'
    # comet trail (transparent -> bright) tracing the journey across the globe
    s += ('<defs><linearGradient id="trail" x1="0" y1="0" x2="1" y2="0">'
          f'<stop offset="0%" stop-color="{GOLD}" stop-opacity="0"/>'
          f'<stop offset="55%" stop-color="{GOLD}" stop-opacity="0.45"/>'
          f'<stop offset="100%" stop-color="{GOLD_L}" stop-opacity="1"/></linearGradient></defs>')
    x0, y0 = cx - R * 0.82, cy + R * 0.34
    x1, y1 = cx + R * 0.80, cy - R * 0.30
    cxx, cyy = cx, cy - R * 1.15
    s += (f'<path d="M {x0:.0f} {y0:.0f} Q {cxx:.0f} {cyy:.0f} {x1:.0f} {y1:.0f}" '
          f'fill="none" stroke="url(#trail)" stroke-width="12" stroke-linecap="round" filter="url(#glow)"/>')
    for t in (0.0, 0.5):
        bx = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cxx + t ** 2 * x1
        by = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cyy + t ** 2 * y1
        s += f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="9" fill="{GOLD}" opacity="0.85" filter="url(#glowS)"/>'
    # bright comet head (the "now" of the replay)
    s += f'<circle cx="{x1:.0f}" cy="{y1:.0f}" r="28" fill="{GOLD_L}" filter="url(#glow)"/>'
    s += f'<circle cx="{x1:.0f}" cy="{y1:.0f}" r="12" fill="#fff"/>'
    # replay control + finale card
    s += chip(SW / 2 - 120, 880, 240, 72, "Replay", PANEL2, GOLD, 32, icon="▶  ")
    cw = 640
    cx2 = (SW - cw) / 2
    s += f'<rect x="{cx2}" y="1000" width="{cw}" height="170" rx="34" fill="{PANEL2}" stroke="#2e2747" stroke-width="2"/>'
    s += logo_mark(cx2 + 92, 1085, 34)
    s += (f'<text x="{cx2+156}" y="1070" font-family="{SANS}" font-weight="bold" font-size="46" fill="{GOLD}">Forest &#183; 20:00</text>'
          f'<text x="{cx2+156}" y="1120" font-family="{SANS}" font-size="30" fill="{MUT}">+480 Light &#183; reached 6 cities</text>')
    s += nav_bar(active=1)
    return s


FRAMES = [
    ("01_hook", scene_hook, None, None, True),
    ("02_map", scene_map, ["Every breath", "lights up the world."],
     ["Join a living map of people", "meditating right now."]),
    ("03_journey", scene_replay, ["Watch your sit", "travel the earth."],
     ["Every session replays as a glowing", "arc across the globe."]),
    ("04_meditate", scene_meditate, ["Press play.", "Just breathe."],
     ["A guided timer, a soundscape,", "and a companion beside you."]),
    ("05_progress", scene_progress, ["The streak that", "brings you back."],
     ["Light, streaks, and weekly leagues", "turn day 1 into day 66."]),
    ("06_journeys", scene_journeys, ["Sit with the Stoics.", "Or with yourself."],
     ["Spoken journeys with real wisdom —", "and a guide who actually answers."]),
    ("07_journal", scene_journal, ["End each sit with a", "letter to yourself."],
     ["The Keeper helps you", "find the words."]),
]


def build():
    os.makedirs(OUT, exist_ok=True)
    made = []
    for item in FRAMES:
        name, fn = item[0], item[1]
        full_bleed = len(item) == 5 and item[4] is True
        body = f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        body += defs()
        if full_bleed:
            body += fn()
        else:
            _, _, hl, sub = item[0], item[1], item[2], item[3]
            body += background(hash(name) % 97 + 1)
            body += headline(hl, sub, y0=236, size=92)
            body += phone(fn())
        body += '</svg>'
        svgp = os.path.join(OUT, name + ".svg")
        pngp = os.path.join(OUT, name + ".png")
        with open(svgp, "w") as f:
            f.write(body)
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H), "-o", pngp, svgp], check=True)
        made.append(pngp)
    return made


if __name__ == "__main__":
    for p in build():
        print(p)
