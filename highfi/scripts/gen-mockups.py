#!/usr/bin/env python3
"""Generate HighFi product mockups via the Gemini image API.

Key: ~/.gemini/imagekey (Matthew's AQ. key; may be rotated).
Model: gemini-3-pro-image (Nano Banana Pro). Outputs JPEG into hardware/mockups/.
Usage: python3 gen-mockups.py [name ...]   # omit args = all
"""
import base64, json, os, sys, urllib.request, pathlib

KEY = pathlib.Path(os.path.expanduser("~/.gemini/imagekey")).read_text().strip()
MODEL = "gemini-3-pro-image"
OUT = pathlib.Path(__file__).resolve().parent.parent / "hardware" / "mockups"
OUT.mkdir(parents=True, exist_ok=True)

BRAND = ("HighFi is a premium 510-thread vape cart battery that is also an MP3 music "
         "player with a built-in speaker. A sleek CNC-anodized aluminum cylindrical "
         "body about the size of a fat 18650 flashlight (~92mm tall, 26mm diameter), "
         "with a small round speaker grille of tiny holes, a subtle warm-amber status "
         "LED, a USB-C port, and a spring-loaded 510 threaded connector on top where a "
         "translucent amber cannabis oil cartridge screws in. Modern industrial design, "
         "matte deep-charcoal body with a warm amber-to-violet gradient accent ring.")

SHOTS = {
    "hero": ("Premium studio product hero shot. " + BRAND + " A translucent amber cart is "
             "screwed into the top and the status LED glows. Dramatic soft studio lighting on "
             "a dark charcoal-to-violet gradient seamless background, subtle reflection, faint "
             "musical soundwave motif in the background bokeh. Ultra sharp, photoreal, "
             "advertising quality, centered, lots of negative space.", "4:3"),
    "render": ("Clean floating studio product render, no background clutter. " + BRAND +
               " Device shown at a 3/4 angle with no cart attached so the 510 threads are "
               "visible on top. Soft amber and violet rim lighting on a near-black background. "
               "Photoreal, crisp, e-commerce hero render.", "1:1"),
    "lifestyle": ("Cozy evening lifestyle shot. " + BRAND + " The device rests on a wooden "
                  "coffee table next to headphones and a plant, warm string lights bokeh, a "
                  "relaxed dim living room at night, faint glowing soundwaves implying music "
                  "playing. Shallow depth of field, warm cinematic color grade, photoreal.", "3:2"),
    "exploded": ("Technical exploded-view render of the device internals, floating stacked "
                 "components separated vertically: the anodized aluminum tube body, a green "
                 "PCB with an ESP32 module, a small round speaker driver, a cylindrical 18650 "
                 "lithium battery, and the brass 510 threaded connector on top. Clean light-grey "
                 "studio background, thin annotation leader lines, engineering marketing render, "
                 "photoreal, crisp.", "4:3"),
    "app-now": ("A modern smartphone held in hand showing a sleek dark music-player app UI with a "
                "large album art, play/pause transport controls, a volume slider and a small "
                "battery indicator, warm amber and violet accent colors. Beside the phone on the "
                "table sits the HighFi cylindrical vape-battery-speaker device. Photoreal product "
                "lifestyle shot, shallow depth of field.", "3:2"),
    "apple-modern": (
        "Premium product photograph of a portable music player designed by Apple in the current "
        "modern minimalist Jony Ive industrial-design language. It is HighFi — a device that is "
        "BOTH a pocket MP3 music player AND a 510-thread vape cart battery. A slim machined "
        "aluminum unibody in space grey, a small crisp rectangular color screen on the front "
        "showing album art with clean minimal playback controls, one elegant machined control "
        "button, precise chamfered edges, seamless construction. On the TOP edge sits a "
        "spring-loaded 510 threaded connector holding a small translucent amber cartridge. "
        "Clearly reads as a music player first. Shot on a bright soft-lit white seamless studio "
        "background with a soft shadow, Apple.com-style product photography, ultra sharp, "
        "photoreal, centered, lots of negative space.", "1:1"),
    "apple-2000s": (
        "Nostalgic early-2000s Apple product photograph in the classic iPod-classic and iPod-mini "
        "design era. It is HighFi — a pocket MP3 music player that is ALSO a 510-thread vape cart "
        "battery. Glossy white polycarbonate front with a polished mirror-chrome stainless-steel "
        "back, a classic circular click-wheel below a small early color LCD screen showing a music "
        "menu list, rounded-rectangle body in candy-colored anodized aluminum. On the TOP edge, a "
        "spring-loaded 510 threaded connector holds a small translucent amber cartridge. Y2K Apple "
        "advertising aesthetic, glossy plastic reflections, shot on a pure white seamless "
        "background, photoreal, high detail, centered.", "1:1"),
}


def gen(name):
    prompt, ar = SHOTS[name]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                              "imageConfig": {"aspectRatio": ar, "imageSize": "4K"}},
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    for part in data["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            out = OUT / f"{name}.jpg"
            out.write_bytes(base64.b64decode(part["inlineData"]["data"]))
            print(f"OK  {name} -> {out} ({out.stat().st_size//1024} KB)")
            return True
    print(f"ERR {name}: no image in response: {json.dumps(data)[:400]}")
    return False


if __name__ == "__main__":
    names = sys.argv[1:] or list(SHOTS)
    ok = 0
    for n in names:
        try:
            ok += gen(n)
        except Exception as e:
            print(f"ERR {n}: {e}")
    print(f"done {ok}/{len(names)}")
