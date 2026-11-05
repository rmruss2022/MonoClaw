#!/usr/bin/env python3
"""Generate open-home hero images via Gemini image model (AI Studio). Zero pip deps."""
import base64, json, os, sys, urllib.request, pathlib

TOKEN = os.environ["GOOGLE_GENAI_TOKEN"]
MODEL = "gemini-2.5-flash-image"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
OUT = pathlib.Path(__file__).resolve().parent.parent / "apps" / "app" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

STYLE = (
    "Cinematic product concept art, widescreen 16:9 composition, dark moody background of deep "
    "charcoal and near-black, a single luminous mint-teal accent color (hex 3ddc97), soft "
    "volumetric glow, clean minimal modern industrial design, subtle rim lighting, high detail, "
    "no text, no words, no logos, no watermarks."
)

IMAGES = {
    "hero-box": (
        "A sleek compact home server / NAS box on a wooden shelf in a cozy modern living room at "
        "dusk, a softly glowing mint-teal status light on its front, faint holographic light-lines "
        "reaching out to a small wifi security camera, a smart door lock, and a smart light bulb "
        "nearby. Mood: you truly own this device, it lives in your home, private and local. " + STYLE
    ),
    "ecosystem": (
        "A central glowing orb representing a local private AI hub, with clean thin light-lines "
        "orbiting outward to minimal icons of a security camera, a deadbolt smart lock, a light "
        "bulb, and a temperature sensor, arranged as an elegant constellation on a dark background. "
        "Represents an open self-owned smart-home network with no cloud dependence. " + STYLE
    ),
    "agent": (
        "An abstract friendly AI presence made of soft mint-teal light quietly watching over a calm "
        "dark home at night, a glowing gentle neural silhouette above a tidy living room, a small "
        "shield motif suggesting privacy and protection, warm and trustworthy, not surveillance. " + STYLE
    ),
}

def gen(name, prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json",
        "x-goog-api-key": TOKEN,
    })
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    for p in parts:
        blob = p.get("inlineData") or p.get("inline_data")
        if blob and blob.get("data"):
            img = base64.b64decode(blob["data"])
            path = OUT / f"{name}.png"
            path.write_bytes(img)
            print(f"  ok {name} -> {path.name} ({len(img)//1024} KB)")
            return True
    print(f"  ! {name}: no image in response: {json.dumps(data)[:300]}")
    return False

ok = 0
for name, prompt in IMAGES.items():
    try:
        if gen(name, prompt):
            ok += 1
    except Exception as e:
        print(f"  ! {name}: {e}")
print(f"done: {ok}/{len(IMAGES)} images")
sys.exit(0 if ok else 1)
