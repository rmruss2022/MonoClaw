# Combo Detector - Multi-Gesture Sequence Detection

The Combo Detector tracks sequences of gestures over time and detects predefined combos (e.g., peace + fist = "special move"). This allows for more complex gesture-based interactions beyond single gestures.

## Features

- ✅ **Sequence Tracking**: Tracks gesture history within configurable time windows
- ✅ **Configurable Combos**: Load combo definitions from `gestures.json`
- ✅ **Timeout Windows**: Customizable time limits for gesture sequences (default: 2 seconds)
- ✅ **Duplicate Filtering**: Prevents rapid duplicate gesture detection
- ✅ **Combo Cooldown**: Prevents duplicate combo triggers
- ✅ **WebSocket Integration**: Automatically emits combo events to connected clients
- ✅ **Multi-Step Combos**: Support for 2+ gesture sequences

## How It Works

1. **Gesture Detection**: When a gesture is detected by the GestureClassifier, it's added to the ComboDetector's history
2. **Sequence Matching**: ComboDetector checks if recent gestures match any defined combo sequences
3. **Time Window**: Only gestures within the timeout window (default 2s) are considered
4. **Event Emission**: When a combo is detected, a `combo_detected` event is sent via WebSocket

## Configuration

Combos are defined in `/Users/matthew/Desktop/vision-controller/config/gestures.json` under the `"combos"` key:

```json
{
  "peace": { ... },
  "fist": { ... },
  "combos": [
    {
      "name": "special_move",
      "sequence": ["peace", "fist"],
      "action": "applescript",
      "script": "display notification \"Special Move!\" with title \"Vision Controller\"",
      "description": "Peace + Fist = Special move notification"
    },
    {
      "name": "dismiss",
      "sequence": ["point", "stop"],
      "action": "keyboard",
      "keys": ["cmd", "w"],
      "description": "Point + Stop = Close window"
    },
    {
      "name": "triple_thumbs",
      "sequence": ["thumbs_up", "thumbs_up", "thumbs_up"],
      "action": "openclaw_rpc",
      "method": "/api/message",
      "params": {
        "action": "send",
        "target": "telegram",
        "message": "🎉 Triple combo!"
      },
      "description": "Three thumbs up in a row"
    }
  ]
}
```

### Combo Fields

- **name**: Unique identifier for the combo
- **sequence**: Array of gesture names that make up the combo (2+ gestures)
- **action**: Action type (`"applescript"`, `"keyboard"`, `"openclaw_rpc"`, etc.)
- **description**: Human-readable description of the combo
- **script**: (optional) AppleScript code for `applescript` actions
- **keys**: (optional) Array of keys for `keyboard` actions
- **method**: (optional) RPC method for `openclaw_rpc` actions
- **params**: (optional) Additional parameters for the action

## WebSocket Events

### Combo Detected Event

When a combo is detected, the server sends a `combo_detected` event:

```json
{
  "type": "combo_detected",
  "combo_name": "special_move",
  "sequence": ["peace", "fist"],
  "confidence": 0.91,
  "action": "applescript",
  "description": "Peace + Fist = Special move",
  "matched_gestures": [
    {
      "gesture": "peace",
      "confidence": 0.95,
      "timestamp": 1707982345678,
      "hand": "right"
    },
    {
      "gesture": "fist",
      "confidence": 0.87,
      "timestamp": 1707982346123,
      "hand": "right"
    }
  ],
  "timestamp": 1707982346150
}
```

## Usage Examples

### Python API

```python
from ml.combo_detector import ComboDetector

# Initialize with 2-second timeout window
detector = ComboDetector(timeout_window=2.0)

# Load combos from config
detector.load_combos_from_config('/path/to/gestures.json')

# Add detected gestures
detector.add_gesture('peace', confidence=0.95, hand='right')
time.sleep(0.5)
detector.add_gesture('fist', confidence=0.87, hand='right')

# Check for combos
combo_result = detector.check_combos()
if combo_result:
    print(f"Combo detected: {combo_result['name']}")
    print(f"Sequence: {' → '.join(combo_result['sequence'])}")
    print(f"Confidence: {combo_result['confidence']:.2f}")
```

### JavaScript WebSocket Client

```javascript
const ws = new WebSocket('ws://127.0.0.1:8765/ws/gestures');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  // Listen for combo events
  if (data.type === 'combo_detected') {
    console.log(`Combo: ${data.combo_name}`);
    console.log(`Sequence: ${data.sequence.join(' → ')}`);
    console.log(`Confidence: ${data.confidence.toFixed(2)}`);
    console.log(`Action: ${data.action}`);
    
    // Handle the combo action
    handleComboAction(data);
  }
};

function handleComboAction(combo) {
  // Execute combo-specific logic
  switch(combo.combo_name) {
    case 'special_move':
      showNotification('Special Move Activated!');
      break;
    case 'dismiss':
      closeCurrentWindow();
      break;
    // ... more combos
  }
}
```

## Configuration Options

### Timeout Window

Adjust how long gestures remain in the detection window:

```python
detector = ComboDetector(timeout_window=3.0)  # 3 seconds
detector.set_timeout_window(1.5)  # Update to 1.5 seconds
```

**Recommended values:**
- **Fast combos**: 1.0-1.5 seconds
- **Normal combos**: 2.0-2.5 seconds
- **Slow combos**: 3.0-4.0 seconds

### Combo Cooldown

The cooldown prevents duplicate combo triggers (default: 1 second). To modify:

```python
detector.combo_cooldown = 0.5  # 500ms cooldown
```

## Testing

Run the comprehensive test suite:

```bash
cd /Users/matthew/Desktop/vision-controller/backend
python3 tests/test_combo_detector.py
```

Test coverage includes:
- ✅ Basic combo detection
- ✅ Timeout window validation
- ✅ Triple gesture combos
- ✅ Duplicate filtering
- ✅ Unknown gesture filtering
- ✅ Combo cooldown
- ✅ Multiple combo definitions
- ✅ Partial sequence rejection

## Integration with Vision Controller

The ComboDetector is automatically integrated into the Vision Controller WebSocket server:

1. **Initialization**: ComboDetector is created on app startup in `api/main.py`
2. **Gesture Feed**: Every detected gesture is fed to the combo detector
3. **Combo Check**: After each gesture, combos are checked
4. **Event Emission**: Combo matches are sent to WebSocket clients

See `backend/api/main.py` for integration details.

## Example Combos

### Quick Actions
```json
{
  "name": "quick_minimize",
  "sequence": ["fist", "point"],
  "action": "keyboard",
  "keys": ["cmd", "m"],
  "description": "Fist + Point = Minimize window"
}
```

### Multi-Step Sequences
```json
{
  "name": "power_sequence",
  "sequence": ["peace", "fist", "stop", "thumbs_up"],
  "action": "applescript",
  "script": "display notification \"Power sequence activated!\"",
  "description": "Four-gesture power combo"
}
```

### Social Media Integration
```json
{
  "name": "twitter_love",
  "sequence": ["peace", "thumbs_up"],
  "action": "openclaw_rpc",
  "method": "/api/message",
  "params": {
    "action": "send",
    "target": "twitter",
    "message": "✌️👍"
  },
  "description": "Tweet peace and thumbs up emojis"
}
```

## Troubleshooting

### Combo not detected
- Check timeout window: gestures must be within the time limit
- Verify gesture names in sequence match exactly
- Ensure gestures have sufficient confidence (>0.6)
- Check for typos in gestures.json

### Duplicate combo triggers
- Increase `combo_cooldown` value
- Verify duplicate filtering is working (check gesture history)

### Partial sequences triggering
- This shouldn't happen - if it does, file a bug report
- Check test suite: `test_partial_sequence` should pass

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Vision Controller                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  WebSocket Server (main.py)                             │
│         │                                                │
│         ├─► HandDetector (MediaPipe)                    │
│         │        │                                       │
│         │        └─► landmarks                           │
│         │                                                │
│         ├─► GestureClassifier                           │
│         │        │                                       │
│         │        └─► gesture + confidence                │
│         │                 │                              │
│         │                 ▼                              │
│         └─► ComboDetector ◄─── gestures.json            │
│                  │                                       │
│                  └─► combo_detected event                │
│                           │                              │
│                           ▼                              │
│                  WebSocket Client                        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Performance

- **Memory**: Gesture history limited to 10 recent gestures
- **Processing**: Negligible overhead (~0.1ms per gesture check)
- **Network**: Combo events only sent when detected (not every frame)

## Future Enhancements

Potential improvements:
- [ ] Gesture velocity/speed requirements
- [ ] Hand-specific combos (left vs right hand)
- [ ] Simultaneous gesture combos (both hands at once)
- [ ] Direction-based combos (swipe left + swipe right)
- [ ] Custom gesture training integration
- [ ] Combo statistics and analytics

## Credits

Created for Vision Controller - VC-015 specification
Developed: February 2026
