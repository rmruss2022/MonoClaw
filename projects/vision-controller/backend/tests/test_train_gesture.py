#!/usr/bin/env python3
"""
Test script for custom gesture training endpoint
Tests POST /api/train-gesture with sample data
"""

import json
import requests
import sys

# API endpoint
API_URL = "http://127.0.0.1:8765/api/train-gesture"

def create_sample_landmarks():
    """Create a sample landmark sequence (21 landmarks with x,y,z coordinates)"""
    # Create a simple pattern (not real landmarks, just for testing)
    landmarks = []
    for i in range(21):
        landmarks.append({
            "x": 0.5 + (i * 0.01),
            "y": 0.5 + (i * 0.01),
            "z": 0.0 + (i * 0.001)
        })
    return landmarks

def test_train_gesture():
    """Test training a custom gesture"""
    
    # Create training data
    gesture_name = "test_wave"
    num_samples = 5
    
    samples = [create_sample_landmarks() for _ in range(num_samples)]
    
    payload = {
        "name": gesture_name,
        "samples": samples
    }
    
    print(f"Testing POST {API_URL}")
    print(f"Training gesture: {gesture_name}")
    print(f"Number of samples: {num_samples}")
    print(f"Landmarks per sample: {len(samples[0])}")
    print()
    
    try:
        response = requests.post(API_URL, json=payload, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("\n✅ Test PASSED: Gesture trained successfully")
            return True
        else:
            print(f"\n❌ Test FAILED: Unexpected status code {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API server")
        print("Make sure the server is running: cd backend && uvicorn api.main:app --port 8765")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_invalid_input():
    """Test with invalid input to check error handling"""
    
    test_cases = [
        {
            "name": "empty_samples",
            "payload": {"name": "test", "samples": []},
            "expected_status": 400
        },
        {
            "name": "missing_name",
            "payload": {"name": "", "samples": [[]]},
            "expected_status": 400
        },
        {
            "name": "wrong_landmark_count",
            "payload": {"name": "test", "samples": [[{"x": 0, "y": 0, "z": 0}]]},
            "expected_status": 400
        }
    ]
    
    print("\n" + "="*60)
    print("Testing error handling...")
    print("="*60 + "\n")
    
    all_passed = True
    
    for test in test_cases:
        print(f"Test: {test['name']}")
        try:
            response = requests.post(API_URL, json=test['payload'], timeout=5)
            if response.status_code == test['expected_status']:
                print(f"✅ Correctly returned {response.status_code}")
            else:
                print(f"❌ Expected {test['expected_status']}, got {response.status_code}")
                all_passed = False
        except Exception as e:
            print(f"❌ Error: {e}")
            all_passed = False
        print()
    
    return all_passed

def verify_custom_gestures_file():
    """Verify that custom_gestures.json was created and contains the gesture"""
    import os
    
    file_path = "/Users/matthew/Desktop/vision-controller/config/custom_gestures.json"
    
    print("="*60)
    print("Verifying custom_gestures.json file...")
    print("="*60 + "\n")
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        print(f"✅ File exists: {file_path}")
        print(f"Gestures in file: {list(data.keys())}")
        print(f"\nFile contents:")
        print(json.dumps(data, indent=2))
        return True
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Custom Gesture Training API Test")
    print("="*60 + "\n")
    
    # Test successful training
    success = test_train_gesture()
    
    if success:
        # Test error handling
        error_tests_passed = test_invalid_input()
        
        # Verify file was created
        file_verified = verify_custom_gestures_file()
        
        if error_tests_passed and file_verified:
            print("\n" + "="*60)
            print("🎉 ALL TESTS PASSED!")
            print("="*60)
            sys.exit(0)
        else:
            print("\n" + "="*60)
            print("⚠️  Some tests failed")
            print("="*60)
            sys.exit(1)
    else:
        print("\n" + "="*60)
        print("❌ PRIMARY TEST FAILED - skipping other tests")
        print("="*60)
        sys.exit(1)
