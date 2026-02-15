# Combo Detector - Quick Start Guide

Get started with gesture combos in 5 minutes! 🚀

## 1. Add a Combo Definition

Edit `/Users/matthew/Desktop/vision-controller/config/gestures.json`:

```json
{
  "peace": { ... },
  "fist": { ... },
  "combos": [
    {
      "name": "my_combo",
      "sequence": ["peace", "fist"],
      "action": "applescript",
      "script": "display notification \"Combo!\"",
      "description": "Peace + Fist = notification"
    }
  ]
}
```

## 2. That's It! 🎉

The combo detector:
- ✅ Automatically loads on server startup
- ✅ Tracks gestures as they're detected
- ✅ Sends `combo_detected` events when matched
- ✅ No code changes needed!

## 3. Listen for Combos (Frontend)

```javascript
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'combo_detected') {
    console.log(`🎯 Combo: ${data.combo_name}`);
    // Do something cool!
  }
};
```

## Common Combos

### Quick Notification
```json
{
  "name": "notify",
  "sequence": ["peace", "thumbs_up"],
  "action": "applescript",
  "script": "display notification \"Hello!\"",
  "description": "Peace + Thumbs = Hello"
}
```

### Close Window
```json
{
  "name": "close",
  "sequence": ["point", "stop"],
  "action": "keyboard",
  "keys": ["cmd", "w"],
  "description": "Point + Stop = Close"
}
```

### Send Message
```json
{
  "name": "celebrate",
  "sequence": ["thumbs_up", "thumbs_up"],
  "action": "openclaw_rpc",
  "method": "/api/message",
  "params": {
    "action": "send",
    "target": "telegram",
    "message": "🎉 Double thumbs!"
  },
  "description": "2x Thumbs = celebration"
}
```

## Configuration Tips

### Timeout Window
How long between gestures? (default: 2 seconds)

- **Fast**: 1.0-1.5s (quick sequences)
- **Normal**: 2.0-2.5s (comfortable timing)
- **Slow**: 3.0-4.0s (deliberate combos)

Edit in code:
```python
detector = ComboDetector(timeout_window=2.0)
```

### Testing Your Combo

1. Add combo to `gestures.json`
2. Restart the backend: `./run.sh`
3. Perform the gesture sequence
4. Check console for: `[ComboDetector] Combo detected: ...`

## Gesture Names

Available gestures (from GestureClassifier):
- `peace` - ✌️ Peace sign (index + middle finger)
- `thumbs_up` - 👍 Thumbs up
- `fist` - ✊ Closed fist
- `point` - 👉 Pointing (index finger)
- `stop` - ✋ Open hand (all fingers)

## Troubleshooting

**Combo not detected?**
- Perform gestures faster (within 2 seconds)
- Check gesture names match exactly
- Verify combo is in gestures.json under "combos"

**Too many false triggers?**
- Increase timeout cooldown
- Make sequence longer (3+ gestures)

**Server not loading combos?**
- Check JSON syntax (use JSONLint)
- Look for startup message: `[ComboDetector] Loaded X combo(s)`

## Full Documentation

See `COMBO_DETECTOR_README.md` for:
- Architecture details
- WebSocket event format
- Python API reference
- Advanced configuration
- Test suite

## Example Session

```bash
# 1. Edit config
vim config/gestures.json
# Add your combo to "combos" array

# 2. Restart backend
cd backend && ./run.sh

# 3. Perform gestures
# Peace → Fist (within 2 seconds)

# 4. Check console
[ComboDetector] Combo detected: my_combo (peace → fist) confidence: 0.91
```

---

**Need Help?** Check `COMBO_DETECTOR_README.md` or run tests:
```bash
python3 tests/test_combo_detector.py
```
