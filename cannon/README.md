# 🎉 Cannon Celebration System

A standalone celebration cannon that can be triggered from anywhere!

## What It Does

- Opens **quarter-size popup window** (centered on screen)
- Click overlay to start (ensures sound plays)
- Animated cannon fires with recoil
- Cannonball flies across screen
- **BOOM!** Explosion with **LOUD** sound effect (3-layer audio synthesis)
- Screen flash
- **BOLD** rainbow "CONGRATS!" text with text-stroke and backdrop
- **250 pieces of confetti** (5x more than before!)
- Auto-closes after 90 seconds

## How to Trigger

### 1. Via CLI

```bash
# Simple way
bash ~/.openclaw/workspace/cannon/fire.sh

# Or make it global (add to ~/.zshrc)
alias cannon="bash ~/.openclaw/workspace/cannon/fire.sh"

# Then just:
cannon
```

### 2. Via Chat (ask Claw)

Just say: "Fire the cannon!" or "Celebrate!" or "BOOM!"

Claw will run the fire.sh script for you.

### 3. Via Browser

Open directly:
```
file:///Users/matthew/.openclaw/workspace/cannon/index.html
```

### 4. Via Vision Project (Future)

The vision project can trigger it by:
- Running the fire.sh script
- Opening the URL directly
- Sending a message to Claw to fire it

## Technical Details

### Sound Effect
Three-layer synthesis using Web Audio API (LOUD volumes):
- **Bass rumble**: 50Hz → 20Hz sawtooth (0.6s, gain 2.5)
- **High crack**: 1500Hz → 80Hz square wave (0.2s, gain 1.5)
- **White noise burst**: Random noise (0.5s, gain 1.2)
- **User interaction required**: Click overlay ensures audio context starts properly

### Animation Sequence
1. Page loads
2. 2-second wait (anticipation)
3. Cannon fires (barrel recoils, ball launches)
4. 0.9s later: Explosion + sound + flash
5. Confetti burst (50 pieces)
6. "CONGRATS!" appears with rainbow gradient
7. 90-second countdown begins
8. Auto-close or press Escape/click Close

### Confetti
- **250 pieces** (5x more!)
- 8 colors: orange, red, pink, purple, blue, green, yellow, orange
- Random sizes (5-20px)
- Random shapes (circles and squares)
- 3-second fall animation with rotation
- Faster spawn rate (20ms intervals)

### Popup Window
- Opens at **50% screen width × 50% screen height** (quarter area)
- Centered on screen
- Resizable if needed
- No toolbars or menu bars

## Files

- `index.html` - The celebration page (standalone, no dependencies)
- `launcher.html` - Popup window launcher (opens index.html in quarter-size window)
- `fire.sh` - CLI launcher script (opens launcher.html)
- `README.md` - This file

## Integration Examples

### From Node.js/JavaScript
```javascript
const { exec } = require('child_process');
exec('bash ~/.openclaw/workspace/cannon/fire.sh');
```

### From Python
```python
import subprocess
subprocess.run(['bash', '/Users/matthew/.openclaw/workspace/cannon/fire.sh'])
```

### From Swift (Vision Project)
```swift
let task = Process()
task.launchPath = "/bin/bash"
task.arguments = ["/Users/matthew/.openclaw/workspace/cannon/fire.sh"]
task.launch()
```

### Via HTTP Server (Optional)
If you want to trigger via HTTP request:

```bash
# Start simple HTTP server
cd ~/.openclaw/workspace/cannon
python3 -m http.server 8888

# Then trigger via:
# http://localhost:8888/index.html
```

## Customization

Want to change the message or timing? Edit `index.html`:

- **Message**: Line 235 - Change "You did it! 🦞"
- **Timer**: Line 243 - Change `timeLeft = 90`
- **Wait before fire**: Line 295 - Change `setTimeout(..., 2000)`
- **Explosion timing**: Line 308 - Change `setTimeout(..., 900)`

## Notes

- Works completely offline (no external dependencies)
- No CDN or internet required
- Pure HTML/CSS/JavaScript
- Responsive to keyboard (Escape to close)
- Auto-closes windows on timer

---

🦞 **Created by Claw** - Feb 13, 2026
