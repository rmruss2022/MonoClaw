#!/usr/bin/env python3
"""Generate Series-A-quality openhome app UI redesign mockups via Gemini."""
import base64, json, os, sys, urllib.request, pathlib
KEY = pathlib.Path(os.path.expanduser("~/.gemini/imagekey")).read_text().strip()
MODEL = "gemini-3-pro-image"
OUT = pathlib.Path("/root/.openclaw/workspace/media/redesign"); OUT.mkdir(parents=True, exist_ok=True)

SYS = ("A pixel-perfect iPhone app UI screenshot (no phone frame, just the screen), portrait, "
       "for a premium local-first smart-home app called 'openhome'. Design language: sophisticated "
       "dark theme (near-black charcoal #0d0f13 background with subtle depth), crisp modern sans-serif "
       "typography with clear hierarchy, generous whitespace, soft rounded cards (18px radius) with very "
       "subtle 1px borders and gentle shadows, a refined emerald-green accent (#35d996) used sparingly for "
       "emphasis, tasteful use of color. Quality bar: Linear, Sonos, and Nest apps — clean, calm, confident, "
       "Series-A startup polish. A sleek iOS-style bottom tab bar with 5 tabs (Home, Music, Lights, Speakers, "
       "Climate) with minimal line icons, the active tab in emerald. Realistic status bar at top. Ultra sharp, "
       "high fidelity, real product UI, not a wireframe.")

SHOTS = {
  "home": (SYS + " THIS SCREEN — Home: a warm greeting 'Good evening, Matthew', a large elegant circular "
           "control dial in the center, and a row of small status pills (lights, locked, playing, 72°). Calm and iconic."),
  "lights": (SYS + " THIS SCREEN — Lights: rooms as sections, each light on a card with a name, an on/off toggle, "
             "a brightness slider, and a small color swatch; one card glowing to show a bulb that's on. A 'Scenes' row of chips."),
  "music": (SYS + " THIS SCREEN — Music: a now-playing card with large album art, track title/artist, a scrubber and "
            "transport controls, a prominent 'Play in: Living Room ▾' room selector, and below it a tidy grid of playlists."),
}
def gen(n):
    prompt = SHOTS[n]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
    body = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"responseModalities":["IMAGE"],"imageConfig":{"aspectRatio":"9:16","imageSize":"2K"}}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=180) as r: data = json.load(r)
    for p in data["candidates"][0]["content"]["parts"]:
        if "inlineData" in p:
            out = OUT / f"{n}.jpg"; out.write_bytes(base64.b64decode(p["inlineData"]["data"]))
            print(f"OK {n} -> {out} ({out.stat().st_size//1024}KB)"); return True
    print("ERR", n, json.dumps(data)[:300]); return False
for n in (sys.argv[1:] or list(SHOTS)):
    try: gen(n)
    except Exception as e: print("ERR", n, e)
