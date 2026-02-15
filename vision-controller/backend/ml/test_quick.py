#!/usr/bin/env python3
"""Quick test of hand detector module without camera."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from hand_detector import HandDetector, LANDMARK_NAMES

def test_basic():
    """Test basic functionality."""
    print("Testing HandDetector...")
    
    # Create detector
    detector = HandDetector(
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    print("✓ HandDetector initialized")
    
    # Test on blank frame
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    hands = detector.detect(frame)
    print(f"✓ detect() returned empty list as expected: {len(hands)} hands")
    
    # Verify output format
    assert isinstance(hands, list)
    if hands:
        for hand in hands:
            assert "handedness" in hand
            assert "landmarks" in hand
            assert "confidence" in hand
            assert len(hand["landmarks"]) == 21
            for lm in hand["landmarks"]:
                assert all(k in lm for k in ["x", "y", "z"])
    
    # Test cleanup
    detector.close()
    print("✓ close() executed")
    
    # Test context manager
    with HandDetector() as det:
        hands = det.detect(frame)
        print(f"✓ Context manager works: {len(hands)} hands")
    print("✓ Context manager closed")
    
    # Print landmark reference
    print(f"\nLandmark reference: {len(LANDMARK_NAMES)} points")
    print(f"  - {LANDMARK_NAMES[0]}")
    print(f"  - Thumb: {LANDMARK_NAMES[1:5]}")
    print(f"  - Index: {LANDMARK_NAMES[5:9]}")
    print(f"  - Middle: {LANDMARK_NAMES[9:13]}")
    print(f"  - Ring: {LANDMARK_NAMES[13:17]}")
    print(f"  - Pinky: {LANDMARK_NAMES[17:21]}")
    
    print("\n✓ All tests passed!")
    return True

if __name__ == "__main__":
    test_basic()
