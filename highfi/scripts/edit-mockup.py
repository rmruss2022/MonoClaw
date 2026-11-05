#!/usr/bin/env python3
"""Image-conditioned HighFi mockups: edit a base render via Gemini (keeps the look).
Usage: python3 edit-mockup.py <base.jpg> <name> "<prompt>"  [aspect]
"""
import base64, json, os, sys, urllib.request, pathlib

KEY = pathlib.Path(os.path.expanduser("~/.gemini/imagekey")).read_text().strip()
MODEL = "gemini-3-pro-image"
OUT = pathlib.Path(__file__).resolve().parent.parent / "hardware" / "mockups"
OUT.mkdir(parents=True, exist_ok=True)

base, name, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
ar = sys.argv[4] if len(sys.argv) > 4 else "1:1"
img_b64 = base64.b64encode(pathlib.Path(base).read_bytes()).decode()

url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"
body = {
    "contents": [{"parts": [
        {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}},
        {"text": prompt},
    ]}],
    "generationConfig": {"responseModalities": ["IMAGE"],
                          "imageConfig": {"aspectRatio": ar, "imageSize": "4K"}},
}
req = urllib.request.Request(url, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=200) as r:
    data = json.load(r)
for part in data["candidates"][0]["content"]["parts"]:
    if "inlineData" in part:
        out = OUT / f"{name}.jpg"
        out.write_bytes(base64.b64decode(part["inlineData"]["data"]))
        print(f"OK {name} -> {out} ({out.stat().st_size//1024} KB)")
        break
else:
    print("ERR no image:", json.dumps(data)[:400])
