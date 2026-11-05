#!/usr/bin/env python3
"""Generate professional, photorealistic openhome product + lifestyle imagery."""
import base64, json, os, sys, urllib.request, pathlib

TOKEN = os.environ["GOOGLE_GENAI_TOKEN"]
MODEL = "gemini-2.5-flash-image"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
OUT = pathlib.Path(__file__).resolve().parent.parent / "apps" / "app" / "assets" / "photo"
OUT.mkdir(parents=True, exist_ok=True)

STYLE = (
    " Photorealistic product photography, shot on a full-frame camera with an 85mm lens, soft "
    "natural window light, shallow depth of field, premium minimal Apple-like aesthetic, a subtle "
    "mint-teal (hex 3ddc97) accent light, calm trustworthy mood, ultra high resolution, tack sharp, "
    "no text, no words, no logos, no watermarks."
)

IMAGES = {
    "box-studio": (
        "A minimalist matte charcoal aluminum smart-home hub, a small rounded rectangular box about "
        "the size of a hardcover book, with a single thin glowing mint-teal LED line across the front. "
        "Centered studio product shot on a smooth light-gray seamless background, soft reflection and "
        "gentle shadow beneath." + STYLE
    ),
    "box-lifestyle": (
        "A minimalist matte charcoal smart-home hub with a thin mint LED, sitting on a light oak wood "
        "shelf in a bright modern Scandinavian living room, a trailing green plant beside it, warm "
        "morning sunlight, a cozy blurred interior behind it." + STYLE
    ),
    "pod-hand": (
        "Close-up of a person's hand plugging a small sleek matte-white smart wall pod, with a subtle "
        "speaker grille and a soft glowing mint ring light, into a wall power outlet. Bright natural "
        "side light, very shallow depth of field, premium." + STYLE
    ),
    "app-hand": (
        "A person holding a modern smartphone in a cozy sunlit living room; the phone screen shows a "
        "clean minimal dark home-control app with mint-teal accents and simple rounded cards. Focus on "
        "the phone, warm bokeh behind." + STYLE
    ),
    "camera": (
        "A small minimalist matte-white home security camera with a subtle mint status light, sitting "
        "on a wooden windowsill with soft daylight, a modern home softly blurred behind it." + STYLE
    ),
    "doorbell": (
        "A sleek slim matte-charcoal smart video doorbell with a thin mint accent, mounted beside a "
        "modern front door frame in natural daylight, clean architectural background." + STYLE
    ),
    "home-golden": (
        "A warm inviting modern living room at golden hour conveying calm, safety and ownership, a few "
        "subtle minimalist smart-home devices on shelves, one softly blurred person relaxing, editorial "
        "interior photography, faint mint accent glow." + STYLE
    ),
}

def gen(name, prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json", "x-goog-api-key": TOKEN,
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    for p in (data.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
        blob = p.get("inlineData") or p.get("inline_data")
        if blob and blob.get("data"):
            (OUT / f"{name}.png").write_bytes(base64.b64decode(blob["data"]))
            print(f"  ok {name} ({len(blob['data'])*3//4//1024} KB)")
            return True
    print(f"  ! {name}: no image — {json.dumps(data)[:200]}")
    return False

ok = 0
for name, prompt in IMAGES.items():
    try:
        if gen(name, prompt): ok += 1
    except Exception as e:
        print(f"  ! {name}: {e}")
print(f"done: {ok}/{len(IMAGES)}")
sys.exit(0 if ok else 1)
