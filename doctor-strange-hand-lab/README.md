# Arcane Hand Lab

Interactive hand-tracking demo inspired by Doctor Strange-style spell circles.

## Features

- MediaPipe hand tracking in-browser (no backend)
- Two-hand tracking with responsive "magic ring" rendering
- Pinch (thumb + index) controls ring intensity/size
- Wrist orientation influences ring rotation
- Two-hand proximity triggers particle burst effects
- Optional landmark overlay for debugging

## Run

```bash
cd /Users/matthew/.openclaw/workspace/doctor-strange-hand-lab
npm install
npm run dev
```

Open the local Vite URL and allow camera access.

## Controls

- **Pinch** to focus energy (brighter/tighter ring)
- **Rotate wrist** to spin the sigil
- **Bring both hands together** for resonance burst
- Use toggles in the HUD for mirror mode and landmark visibility
