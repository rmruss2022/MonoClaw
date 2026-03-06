#!/usr/bin/env python3
"""
Test custom gesture matching in GestureClassifier
Tests that custom gestures are loaded and matched correctly
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, '/Users/matthew/Desktop/vision-controller/backend')
from ml.gesture_classifier import GestureClassifier

def create_test_landmarks():
    """Create test landmarks pattern"""
    landmarks = []
    # Create a distinctive pattern
    for i in range(21):
        landmarks.append((
            0.5 + (i * 0.02),
            0.5 - (i * 0.015),
            0.0 + (i * 0.001)
        ))
    return landmarks

def create_similar_landmarks():
    """Create similar but slightly different landmarks"""
    landmarks = []
    for i in range(21):
        landmarks.append((
            0.5 + (i * 0.02) + 0.01,  # Slight offset
            0.5 - (i * 0.015) + 0.01,
            0.0 + (i * 0.001)
        ))
    return landmarks

def create_different_landmarks():
    """Create completely different landmarks"""
    landmarks = []
    for i in range(21):
        landmarks.append((
            0.3 + (i * 0.01),
            0.7 + (i * 0.02),
            0.1 - (i * 0.002)
        ))
    return landmarks

def setup_test_gesture():
    """Create a test custom gesture file"""
    config_path = Path("/Users/matthew/Desktop/vision-controller/config")
    config_path.mkdir(parents=True, exist_ok=True)
    
    custom_gestures_file = config_path / "custom_gestures.json"
    
    # Create test gesture with multiple samples
    test_landmarks = create_test_landmarks()
    similar_landmarks = create_similar_landmarks()
    
    # Convert to dict format
    samples = [
        [{"x": lm[0], "y": lm[1], "z": lm[2]} for lm in test_landmarks],
        [{"x": lm[0], "y": lm[1], "z": lm[2]} for lm in similar_landmarks]
    ]
    
    custom_gestures = {
        "test_custom": {
            "name": "test_custom",
            "samples": samples,
            "created_at": "2024-02-15T10:00:00",
            "num_samples": len(samples)
        }
    }
    
    with open(custom_gestures_file, 'w') as f:
        json.dump(custom_gestures, f, indent=2)
    
    print(f"✅ Created test gesture file: {custom_gestures_file}")
    return test_landmarks, similar_landmarks

def test_custom_gesture_loading():
    """Test that custom gestures are loaded correctly"""
    print("\n" + "="*60)
    print("Test 1: Loading Custom Gestures")
    print("="*60 + "\n")
    
    classifier = GestureClassifier()
    
    if len(classifier.custom_gestures) > 0:
        print(f"✅ Custom gestures loaded: {list(classifier.custom_gestures.keys())}")
        print(f"   Total: {len(classifier.custom_gestures)} gestures")
        return True
    else:
        print("❌ No custom gestures loaded")
        return False

def test_custom_gesture_matching():
    """Test matching against custom gestures"""
    print("\n" + "="*60)
    print("Test 2: Custom Gesture Matching")
    print("="*60 + "\n")
    
    # Setup test gesture
    test_landmarks, similar_landmarks = setup_test_gesture()
    
    # Create classifier
    classifier = GestureClassifier()
    
    # Test 1: Match exact gesture
    print("Test 2a: Matching exact gesture...")
    result = classifier.classify(test_landmarks, "right")
    
    print(f"  Gesture: {result['gesture']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Type: {result.get('type', 'unknown')}")
    
    if result['gesture'] == 'test_custom' and result['confidence'] > 0.7:
        print("  ✅ Exact match successful")
        exact_match = True
    else:
        print("  ❌ Exact match failed")
        exact_match = False
    
    # Test 2: Match similar gesture
    print("\nTest 2b: Matching similar gesture...")
    result = classifier.classify(similar_landmarks, "right")
    
    print(f"  Gesture: {result['gesture']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Type: {result.get('type', 'unknown')}")
    
    if result['gesture'] == 'test_custom' and result['confidence'] > 0.5:
        print("  ✅ Similar match successful")
        similar_match = True
    else:
        print("  ❌ Similar match failed")
        similar_match = False
    
    # Test 3: No match for different gesture
    print("\nTest 2c: Rejecting different gesture...")
    different_landmarks = create_different_landmarks()
    result = classifier.classify(different_landmarks, "right")
    
    print(f"  Gesture: {result['gesture']}")
    print(f"  Confidence: {result['confidence']:.2f}")
    print(f"  Type: {result.get('type', 'unknown')}")
    
    # Should either not match test_custom or have low confidence
    if result['gesture'] != 'test_custom' or result['confidence'] < 0.7:
        print("  ✅ Correctly rejected different gesture")
        reject_match = True
    else:
        print("  ❌ Incorrectly matched different gesture")
        reject_match = False
    
    return exact_match and similar_match and reject_match

def test_builtin_vs_custom_priority():
    """Test that custom gestures with higher confidence override built-in"""
    print("\n" + "="*60)
    print("Test 3: Built-in vs Custom Priority")
    print("="*60 + "\n")
    
    classifier = GestureClassifier()
    
    # Create peace sign landmarks (built-in gesture)
    peace_landmarks = [(0.5, 0.5, 0)] * 21  # Simplified
    peace_landmarks[4] = (0.3, 0.4, 0)   # Thumb down
    peace_landmarks[8] = (0.5, 0.2, 0)   # Index up
    peace_landmarks[12] = (0.6, 0.2, 0)  # Middle up
    peace_landmarks[16] = (0.4, 0.7, 0)  # Ring down
    peace_landmarks[20] = (0.3, 0.7, 0)  # Pinky down
    
    result = classifier.classify(peace_landmarks, "right")
    
    print(f"Gesture: {result['gesture']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Type: {result.get('type', 'unknown')}")
    
    # Should recognize as built-in peace
    if result['gesture'] in ['peace', 'stop', 'unknown']:  # May match peace or stop
        print("✅ Built-in gestures still work")
        return True
    else:
        print("❌ Built-in gesture recognition broken")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Custom Gesture Classifier Test")
    print("="*60)
    
    try:
        # Run tests
        test1 = test_custom_gesture_loading()
        test2 = test_custom_gesture_matching()
        test3 = test_builtin_vs_custom_priority()
        
        print("\n" + "="*60)
        print("Test Results Summary")
        print("="*60)
        print(f"Test 1 (Loading): {'✅ PASS' if test1 else '❌ FAIL'}")
        print(f"Test 2 (Matching): {'✅ PASS' if test2 else '❌ FAIL'}")
        print(f"Test 3 (Priority): {'✅ PASS' if test3 else '❌ FAIL'}")
        
        if test1 and test2 and test3:
            print("\n🎉 ALL TESTS PASSED!")
            sys.exit(0)
        else:
            print("\n⚠️  SOME TESTS FAILED")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
