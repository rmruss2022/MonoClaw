#!/usr/bin/env python3
"""
Latency Test for Optimized Vision Controller

Tests frame processing pipeline to verify <100ms latency target.

Usage:
    cd /Users/matthew/Desktop/vision-controller/backend
    python tests/test_latency_optimized.py
"""

import sys
import time
import cv2
import numpy as np
from pathlib import Path

sys.path.insert(0, '/Users/matthew/Desktop/vision-controller/backend')
from ml.hand_detector import HandDetector


def benchmark_hand_detection(num_frames=100, show_video=False):
    """Benchmark hand detection latency."""
    
    print("=" * 60)
    print("LATENCY OPTIMIZATION BENCHMARK")
    print("=" * 60)
    print(f"Target: <100ms per frame")
    print(f"Testing {num_frames} frames...")
    print()
    
    # Initialize detector with optimized settings
    detector = HandDetector(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=0,  # Lite model
        frame_skip=1  # No skipping for accurate benchmark
    )
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    if not cap.isOpened():
        print("❌ Error: Cannot open webcam")
        return
    
    print("✅ Webcam initialized (320x240 @ 30fps)")
    print("   Place your hand in view for accurate results")
    print()
    
    # Warm-up phase
    print("Warming up (5 frames)...")
    for _ in range(5):
        ret, frame = cap.read()
        if ret:
            detector.detect(frame)
    
    # Benchmark
    latencies = []
    frames_with_hands = 0
    
    print(f"\nBenchmarking {num_frames} frames...")
    
    for i in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            print(f"⚠️  Frame {i+1}: Failed to capture")
            continue
        
        # Measure detection latency
        start_time = time.perf_counter()
        hands = detector.detect(frame)
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        latencies.append(latency_ms)
        if hands:
            frames_with_hands += 1
        
        # Show progress
        if (i + 1) % 10 == 0:
            avg_so_far = sum(latencies) / len(latencies)
            print(f"  Frame {i+1}/{num_frames}: {latency_ms:.1f}ms (avg: {avg_so_far:.1f}ms)")
        
        # Optional visualization
        if show_video:
            if hands:
                frame = detector.draw_landmarks(frame, hands)
            cv2.putText(frame, f"{latency_ms:.1f}ms", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow('Latency Test', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    cap.release()
    if show_video:
        cv2.destroyAllWindows()
    detector.close()
    
    # Results
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"Frames processed: {len(latencies)}")
        print(f"Hands detected: {frames_with_hands} ({frames_with_hands/len(latencies)*100:.1f}%)")
        print()
        print(f"Average latency:  {avg_latency:.2f} ms")
        print(f"Minimum latency:  {min_latency:.2f} ms")
        print(f"Maximum latency:  {max_latency:.2f} ms")
        print(f"P95 latency:      {p95_latency:.2f} ms")
        print(f"P99 latency:      {p99_latency:.2f} ms")
        print()
        
        # Check target
        if avg_latency < 100:
            print(f"✅ TARGET MET: Average latency {avg_latency:.1f}ms < 100ms")
        else:
            print(f"❌ TARGET MISSED: Average latency {avg_latency:.1f}ms >= 100ms")
        
        if p95_latency < 100:
            print(f"✅ P95 within target: {p95_latency:.1f}ms < 100ms")
        else:
            print(f"⚠️  P95 exceeds target: {p95_latency:.1f}ms >= 100ms")
        
        # FPS calculation
        effective_fps = 1000 / avg_latency
        print()
        print(f"Effective FPS:    {effective_fps:.1f} fps")
        
        if effective_fps >= 30:
            print(f"✅ FPS TARGET MET: {effective_fps:.1f} >= 30 fps")
        else:
            print(f"⚠️  FPS below target: {effective_fps:.1f} < 30 fps")
    
    print("=" * 60)


def test_fast_detect():
    """Test the ultra-fast detect_fast() method."""
    print("\n" + "=" * 60)
    print("TESTING detect_fast() METHOD")
    print("=" * 60)
    
    detector = HandDetector(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=0,
        frame_skip=1
    )
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    
    # Warm up
    for _ in range(5):
        ret, frame = cap.read()
        if ret:
            detector.detect_fast(frame)
    
    # Test
    latencies = []
    for _ in range(50):
        ret, frame = cap.read()
        if not ret:
            continue
        
        start = time.perf_counter()
        landmarks = detector.detect_fast(frame)
        latency = (time.perf_counter() - start) * 1000
        latencies.append(latency)
    
    cap.release()
    detector.close()
    
    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"detect_fast() average: {avg:.2f}ms")
        print(f"Returns numpy array: {landmarks is not None}")
        if landmarks is not None:
            print(f"Array shape: {landmarks.shape} (expected: (21, 3))")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Latency benchmark for Vision Controller")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to test")
    parser.add_argument("--show", action="store_true", help="Show video window")
    parser.add_argument("--fast", action="store_true", help="Test detect_fast() method")
    
    args = parser.parse_args()
    
    if args.fast:
        test_fast_detect()
    else:
        benchmark_hand_detection(args.frames, args.show)
