#!/usr/bin/env python3
"""
Test script for HandDetector.

Captures video from webcam, detects hands, and displays FPS.
Press 'q' to quit.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import cv2
from hand_detector import HandDetector


def main():
    """Run hand detection test with webcam."""
    print("=" * 50)
    print("Hand Detection Test")
    print("=" * 50)
    
    # Initialize hand detector
    print("Initializing HandDetector...")
    try:
        detector = HandDetector(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        print("✓ HandDetector initialized")
    except Exception as e:
        print(f"✗ Failed to initialize HandDetector: {e}")
        sys.exit(1)
    
    # Open webcam
    print("Opening webcam...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("✗ Failed to open webcam")
        sys.exit(1)
    
    # Set to 720p for FPS target
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"✓ Webcam opened: {width}x{height} @ {fps:.1f}fps")
    print("-" * 50)
    print("Press 'q' to quit")
    print("=" * 50)
    
    # FPS tracking
    frame_count = 0
    start_time = time.time()
    fps_display = 0
    
    try:
        while True:
            # Read frame
            ret, frame = cap.read()
            if not ret:
                print("Failed to capture frame")
                break
            
            # Detect hands
            hands = detector.detect(frame)
            
            # Draw landmarks if hands detected
            if hands:
                frame = detector.draw_landmarks(frame, hands)
            
            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            
            if elapsed >= 1.0:
                fps_display = frame_count / elapsed
                frame_count = 0
                start_time = time.time()
            
            # Display info on frame
            info_text = f"FPS: {fps_display:.1f} | Hands: {len(hands)}"
            cv2.putText(
                frame, info_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2
            )
            
            # Show hand details
            y_offset = 60
            for i, hand in enumerate(hands):
                hand_text = f"{hand['handedness']}: {hand['confidence']:.2f}"
                cv2.putText(
                    frame, hand_text, (10, y_offset + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1
                )
                
                # Print landmark sample (first hand only, to avoid spam)
                if i == 0 and frame_count % 30 == 0:
                    lm = hand['landmarks'][0]  # Wrist
                    print(f"\rHand: {hand['handedness']}, "
                          f"Wrist: ({lm['x']:.3f}, {lm['y']:.3f}, {lm['z']:.3f}), "
                          f"Landmarks: {len(hand['landmarks'])}", end="")
            
            # Show frame
            cv2.imshow("Hand Detection Test", frame)
            
            # Check for quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n\nQuitting...")
                break
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        # Cleanup
        detector.close()
        cap.release()
        cv2.destroyAllWindows()
        
        print("\nCleanup complete")
        print(f"Final FPS: {fps_display:.1f}")
        print("=" * 50)


def test_detector_api():
    """Test basic detector functionality without camera."""
    import numpy as np
    
    print("Testing HandDetector API...")
    
    # Create a blank frame
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    
    # Initialize detector
    detector = HandDetector()
    
    # Test detect (will return empty list for blank frame)
    hands = detector.detect(frame)
    assert isinstance(hands, list), "detect() should return a list"
    
    # Test output format
    if hands:  # Unlikely on blank frame, but check format
        for hand in hands:
            assert "handedness" in hand, "Missing handedness"
            assert "landmarks" in hand, "Missing landmarks"
            assert "confidence" in hand, "Missing confidence"
            assert len(hand["landmarks"]) == 21, "Should have 21 landmarks"
            for lm in hand["landmarks"]:
                assert all(k in lm for k in ["x", "y", "z"]), "Missing coordinate keys"
    
    detector.close()
    print("✓ API test passed")


if __name__ == "__main__":
    # Run API test first
    test_detector_api()
    
    # Run camera test
    main()
