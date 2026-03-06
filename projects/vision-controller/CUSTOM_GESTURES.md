# Custom Gesture Training

This document explains how to train and use custom gestures in the Vision Controller.

## Overview

The Vision Controller now supports custom gesture training in addition to the 5 built-in gestures (peace, thumbs_up, fist, point, stop). Custom gestures are learned from training samples and stored in `config/custom_gestures.json`.

## API Endpoint

### POST /api/train-gesture

Train a new custom gesture by providing training samples.

**Request Body:**
```json
{
  "name": "my_gesture",
  "samples": [
    [
      {"x": 0.5, "y": 0.5, "z": 0.0},
      {"x": 0.52, "y": 0.48, "z": 0.01},
      ... // 21 landmarks total
    ],
    ... // Multiple samples (recommended: 5-30)
  ]
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Gesture 'my_gesture' trained successfully",
  "gesture_name": "my_gesture",
  "num_samples": 5,
  "saved_to": "/Users/matthew/Desktop/vision-controller/config/custom_gestures.json"
}
```

**Response (Error):**
```json
{
  "detail": "Error message here"
}
```

## Training Requirements

### Gesture Name
- Must not be empty
- Will be normalized: lowercase, spaces replaced with underscores
- Example: "Rock On" → "rock_on"

### Samples
- Each sample must have exactly **21 landmarks**
- Each landmark must have `x`, `y`, and `z` coordinates (floats)
- Recommended: **5-30 training samples** for best results
- More samples = better recognition, but also slower training

### Landmark Format
Each landmark should have normalized coordinates (0-1 range):
```javascript
{
  "x": 0.5,    // Horizontal position (0=left, 1=right)
  "y": 0.5,    // Vertical position (0=top, 1=bottom)
  "z": 0.0     // Depth (negative=closer to camera)
}
```

## How Custom Gestures Work

### Recognition Algorithm
1. **Normalization**: Landmarks are normalized relative to wrist position and hand size
2. **Comparison**: Current hand pose is compared against all trained samples
3. **Similarity Score**: Calculated using Euclidean distance with exponential decay
4. **Best Match**: Highest similarity score wins

### Priority Logic
Custom gestures are checked first, then built-in gestures:

- **Custom gesture wins if:**
  - Confidence ≥ 0.65 (always preferred)
  - Confidence ≥ 0.5 AND built-in confidence < 0.8

- **Built-in gesture wins if:**
  - Custom confidence < 0.5
  - Built-in confidence ≥ 0.8 (very confident)

This ensures custom gestures take priority when they match well, while still allowing built-in gestures to work reliably.

## Storage

Custom gestures are stored in:
```
/Users/matthew/Desktop/vision-controller/config/custom_gestures.json
```

**File Structure:**
```json
{
  "my_gesture": {
    "name": "my_gesture",
    "samples": [ /* array of landmark arrays */ ],
    "created_at": "2024-02-15T10:30:00",
    "num_samples": 5
  },
  "another_gesture": {
    ...
  }
}
```

## Example Usage

### Using curl

```bash
# Create sample training data
cat > training_data.json << 'EOF'
{
  "name": "Test Wave",
  "samples": [
    [
      {"x": 0.5, "y": 0.5, "z": 0.0},
      {"x": 0.51, "y": 0.49, "z": 0.001},
      {"x": 0.52, "y": 0.48, "z": 0.002},
      ... // Continue for all 21 landmarks
    ]
  ]
}
EOF

# Train the gesture
curl -X POST http://127.0.0.1:8765/api/train-gesture \
  -H "Content-Type: application/json" \
  -d @training_data.json
```

### Using Python

```python
import requests

# Prepare training data
gesture_data = {
    "name": "shaka",
    "samples": [
        # Sample 1
        [
            {"x": 0.5, "y": 0.5, "z": 0.0},
            # ... 20 more landmarks
        ],
        # Sample 2
        [
            {"x": 0.51, "y": 0.49, "z": 0.01},
            # ... 20 more landmarks
        ]
        # ... more samples
    ]
}

# Train gesture
response = requests.post(
    "http://127.0.0.1:8765/api/train-gesture",
    json=gesture_data
)

print(response.json())
```

### Frontend Integration

The frontend should:
1. Enter "training mode" when user clicks "Train Gesture"
2. Prompt user for gesture name
3. Capture 10-30 frames of hand landmarks
4. POST the collected samples to `/api/train-gesture`
5. Show success/error message

## Testing

### Test Scripts

**Test API Endpoint:**
```bash
cd /Users/matthew/Desktop/vision-controller
python3 backend/tests/test_train_gesture.py
```

**Test Gesture Matching:**
```bash
cd /Users/matthew/Desktop/vision-controller
python3 backend/tests/test_custom_gesture_matching.py
```

### Manual Testing

1. Start the API server:
```bash
cd /Users/matthew/Desktop/vision-controller/backend
uvicorn api.main:app --host 127.0.0.1 --port 8765 --reload
```

2. Train a gesture using the test script or curl

3. Use the frontend to perform the trained gesture

4. Check that it's recognized in the WebSocket stream

## Troubleshooting

### Gesture Not Recognized
- **Ensure sufficient samples**: Train with at least 10 samples
- **Vary hand positions**: Capture samples from slightly different angles
- **Check similarity threshold**: May need to adjust in `gesture_classifier.py`

### Custom Gesture File Not Found
- Check that `/Users/matthew/Desktop/vision-controller/config/` exists
- Ensure API has write permissions
- Look for errors in API logs

### Custom Gesture Overriding Built-in
- This is expected behavior if custom gesture confidence is high
- Adjust priority thresholds in `gesture_classifier.py` if needed
- Use more distinctive hand poses for custom gestures

### Low Confidence Scores
- Increase number of training samples
- Ensure consistent hand orientation across samples
- Check that landmarks are properly normalized

## Configuration

### Adjusting Sensitivity

Edit `backend/ml/gesture_classifier.py`:

```python
# In _compare_landmarks():
similarity = math.exp(-avg_distance * 8.0)  # Increase for stricter matching
                                            # Decrease for looser matching

# In classify():
if custom_confidence >= 0.65:  # Adjust threshold (0.5-0.9)
```

### Changing Storage Location

Edit `backend/api/main.py` and `backend/ml/gesture_classifier.py`:

```python
config_path = Path("/path/to/your/config")
custom_gestures_file = config_path / "custom_gestures.json"
```

## Advanced Features

### Retraining Existing Gesture
Simply POST with the same gesture name - it will overwrite the existing one.

### Deleting Custom Gestures
Manually edit `config/custom_gestures.json` and remove the gesture entry, or delete the entire file to remove all custom gestures.

### Exporting/Importing Gestures
Copy `config/custom_gestures.json` to another machine to share trained gestures.

## Performance

- **Training**: ~10-50ms per gesture (depends on number of samples)
- **Recognition**: +5-15ms overhead per frame when custom gestures are loaded
- **Memory**: ~1-5KB per trained gesture
- **Recommended limit**: <50 custom gestures for real-time performance

## Future Enhancements

Potential improvements (not yet implemented):
- [ ] Web UI for gesture training
- [ ] Gesture management API (list, delete, update)
- [ ] Gesture validation and quality scoring
- [ ] Multi-hand custom gestures
- [ ] Temporal gesture sequences (sign language)
- [ ] Gesture recording from video files
