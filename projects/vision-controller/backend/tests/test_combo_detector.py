"""
Test suite for ComboDetector module

Tests gesture combo detection, timeout windows, and config loading.
Run: python test_combo_detector.py
"""

import time
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.combo_detector import ComboDetector


def test_basic_combo_detection():
    """Test basic two-gesture combo detection."""
    print("\n" + "="*60)
    print("TEST 1: Basic Combo Detection (Peace → Fist)")
    print("="*60)
    
    detector = ComboDetector(timeout_window=2.0)
    
    # Create test combo config
    test_config = {
        "combos": [
            {
                "name": "special_move",
                "sequence": ["peace", "fist"],
                "action": "test",
                "description": "Test combo"
            }
        ]
    }
    
    config_path = '/tmp/test_combo_config.json'
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    detector.load_combos_from_config(config_path)
    
    # Add gestures
    detector.add_gesture('peace', 0.95, 'right')
    time.sleep(0.3)
    detector.add_gesture('fist', 0.87, 'right')
    
    # Check for combo
    result = detector.check_combos()
    
    if result:
        print(f"✓ PASS: Combo '{result['name']}' detected")
        print(f"  Sequence: {' → '.join(result['sequence'])}")
        print(f"  Confidence: {result['confidence']:.2f}")
        return True
    else:
        print("✗ FAIL: Combo not detected")
        return False


def test_timeout_window():
    """Test that combos outside timeout window are not detected."""
    print("\n" + "="*60)
    print("TEST 2: Timeout Window (gestures too far apart)")
    print("="*60)
    
    detector = ComboDetector(timeout_window=1.0)  # 1 second window
    
    test_config = {
        "combos": [
            {
                "name": "timeout_test",
                "sequence": ["peace", "fist"],
                "action": "test"
            }
        ]
    }
    
    config_path = '/tmp/test_combo_timeout.json'
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    detector.load_combos_from_config(config_path)
    
    # Add gestures with long delay
    detector.add_gesture('peace', 0.95)
    time.sleep(1.5)  # Wait longer than timeout
    detector.add_gesture('fist', 0.87)
    
    result = detector.check_combos()
    
    if result is None:
        print("✓ PASS: Combo correctly NOT detected (outside timeout)")
        return True
    else:
        print(f"✗ FAIL: Combo incorrectly detected: {result['name']}")
        return False


def test_triple_gesture_combo():
    """Test three-gesture combo sequence."""
    print("\n" + "="*60)
    print("TEST 3: Triple Gesture Combo (Thumbs Up x3)")
    print("="*60)
    
    detector = ComboDetector(timeout_window=3.0)
    
    test_config = {
        "combos": [
            {
                "name": "triple_thumbs",
                "sequence": ["thumbs_up", "thumbs_up", "thumbs_up"],
                "action": "test"
            }
        ]
    }
    
    config_path = '/tmp/test_triple_combo.json'
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    detector.load_combos_from_config(config_path)
    
    # Add three thumbs up gestures
    detector.add_gesture('thumbs_up', 0.92)
    time.sleep(0.4)
    detector.add_gesture('thumbs_up', 0.89)
    time.sleep(0.4)
    detector.add_gesture('thumbs_up', 0.91)
    
    result = detector.check_combos()
    
    if result and result['name'] == 'triple_thumbs':
        print(f"✓ PASS: Triple combo '{result['name']}' detected")
        print(f"  Confidence: {result['confidence']:.2f}")
        return True
    else:
        print("✗ FAIL: Triple combo not detected")
        return False


def test_duplicate_filtering():
    """Test that rapid duplicate gestures are filtered."""
    print("\n" + "="*60)
    print("TEST 4: Duplicate Gesture Filtering")
    print("="*60)
    
    detector = ComboDetector(timeout_window=2.0)
    
    # Add same gesture multiple times rapidly
    detector.add_gesture('peace', 0.95)
    detector.add_gesture('peace', 0.94)  # Should be filtered
    detector.add_gesture('peace', 0.96)  # Should be filtered
    
    history = detector.get_history_summary()
    
    if len(history) == 1:
        print(f"✓ PASS: Duplicates filtered correctly (kept 1 of 3)")
        return True
    else:
        print(f"✗ FAIL: Expected 1 gesture in history, got {len(history)}")
        return False


def test_unknown_gesture_filtering():
    """Test that unknown/None gestures are ignored."""
    print("\n" + "="*60)
    print("TEST 5: Unknown Gesture Filtering")
    print("="*60)
    
    detector = ComboDetector(timeout_window=2.0)
    
    # Add valid and invalid gestures
    detector.add_gesture('peace', 0.95)
    detector.add_gesture('unknown', 0.50)  # Should be filtered
    detector.add_gesture(None, 0.0)  # Should be filtered
    detector.add_gesture('fist', 0.87)
    
    history = detector.get_history_summary()
    
    if len(history) == 2 and history[0]['gesture'] == 'peace' and history[1]['gesture'] == 'fist':
        print(f"✓ PASS: Unknown gestures filtered (kept 2 of 4)")
        return True
    else:
        print(f"✗ FAIL: Expected 2 gestures, got {len(history)}")
        return False


def test_combo_cooldown():
    """Test that combo cooldown prevents duplicate triggers."""
    print("\n" + "="*60)
    print("TEST 6: Combo Cooldown (prevent duplicate triggers)")
    print("="*60)
    
    detector = ComboDetector(timeout_window=2.0)
    
    test_config = {
        "combos": [
            {
                "name": "cooldown_test",
                "sequence": ["peace", "fist"],
                "action": "test"
            }
        ]
    }
    
    config_path = '/tmp/test_cooldown.json'
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    detector.load_combos_from_config(config_path)
    
    # Trigger combo
    detector.add_gesture('peace', 0.95)
    time.sleep(0.3)
    detector.add_gesture('fist', 0.87)
    
    result1 = detector.check_combos()
    result2 = detector.check_combos()  # Immediate re-check
    
    if result1 and result2 is None:
        print("✓ PASS: Second check blocked by cooldown")
        return True
    else:
        print("✗ FAIL: Cooldown not working properly")
        return False


def test_multiple_combos():
    """Test detection with multiple combo definitions."""
    print("\n" + "="*60)
    print("TEST 7: Multiple Combo Definitions")
    print("="*60)
    
    detector = ComboDetector(timeout_window=2.0)
    
    test_config = {
        "combos": [
            {
                "name": "combo_a",
                "sequence": ["peace", "fist"],
                "action": "test"
            },
            {
                "name": "combo_b",
                "sequence": ["point", "stop"],
                "action": "test"
            }
        ]
    }
    
    config_path = '/tmp/test_multi_combo.json'
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    detector.load_combos_from_config(config_path)
    
    # Test first combo
    detector.add_gesture('peace', 0.95)
    time.sleep(0.3)
    detector.add_gesture('fist', 0.87)
    result1 = detector.check_combos()
    
    # Reset and test second combo
    detector.reset()
    time.sleep(1.0)  # Wait for cooldown
    detector.add_gesture('point', 0.91)
    time.sleep(0.3)
    detector.add_gesture('stop', 0.88)
    result2 = detector.check_combos()
    
    if result1 and result1['name'] == 'combo_a' and result2 and result2['name'] == 'combo_b':
        print("✓ PASS: Both combos detected correctly")
        print(f"  Combo A: {result1['name']}")
        print(f"  Combo B: {result2['name']}")
        return True
    else:
        print("✗ FAIL: Multiple combo detection failed")
        return False


def test_partial_sequence():
    """Test that partial sequences don't trigger combos."""
    print("\n" + "="*60)
    print("TEST 8: Partial Sequence (should not trigger)")
    print("="*60)
    
    detector = ComboDetector(timeout_window=2.0)
    
    test_config = {
        "combos": [
            {
                "name": "triple_test",
                "sequence": ["peace", "fist", "stop"],
                "action": "test"
            }
        ]
    }
    
    config_path = '/tmp/test_partial.json'
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    detector.load_combos_from_config(config_path)
    
    # Add only 2 of 3 gestures
    detector.add_gesture('peace', 0.95)
    time.sleep(0.3)
    detector.add_gesture('fist', 0.87)
    
    result = detector.check_combos()
    
    if result is None:
        print("✓ PASS: Partial sequence correctly NOT detected")
        return True
    else:
        print(f"✗ FAIL: Partial sequence incorrectly triggered: {result['name']}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("  COMBO DETECTOR TEST SUITE")
    print("="*60)
    
    tests = [
        test_basic_combo_detection,
        test_timeout_window,
        test_triple_gesture_combo,
        test_duplicate_filtering,
        test_unknown_gesture_filtering,
        test_combo_cooldown,
        test_multiple_combos,
        test_partial_sequence
    ]
    
    results = []
    for test in tests:
        try:
            passed = test()
            results.append(passed)
        except Exception as e:
            print(f"✗ ERROR: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED! 🎉")
    else:
        print(f"\n✗ {total - passed} test(s) failed")
    
    print("="*60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
