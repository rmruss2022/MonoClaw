# HighFi landing — image assets

Drop the following image files into this `assets/` folder. The landing page
references them by these exact relative paths. Every `<img>` fails gracefully
if a file is missing (alt text shows, tiles hide themselves, no broken layout),
so the page previews fine before the art lands — but these are what it expects.

| Filename        | Used in            | Suggested content                                             | Aspect |
|-----------------|--------------------|---------------------------------------------------------------|--------|
| `hero.jpg`      | Hero + Gallery     | Beauty shot of the device (anodized body, speaker grille, 510 top) on a dark, warm-lit backdrop | Portrait, ~3:4 |
| `render.jpg`    | Gallery            | Clean studio product render, alternate angle                  | 4:3    |
| `lifestyle.jpg` | Gallery            | Device in hand / on a table during a session, warm ambience   | 4:3    |
| `exploded.jpg`  | Gallery            | Exploded view showing internals (ESP32-S3, amp, 18650, 510)   | 4:3    |
| `app-now.jpg`   | App section + Gallery | Screenshot of the app "Now Playing" screen                | Portrait phone |
| `app-vape.jpg`  | App section        | Screenshot of the app vape panel (battery, coil, session)     | Portrait phone |

Notes:
- Prefer `.jpg` at the exact names above. If you generate `.png`, either convert
  to `.jpg` or update the `src` paths in `index.html`.
- Gallery tiles are cropped to 4:3 via CSS `object-fit: cover`, so exact source
  aspect ratios are forgiving.
- Keep files reasonably sized (long edge ~1600px) for fast loads.
