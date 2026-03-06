#!/usr/bin/env python3
"""
Headless gesture window manager — no browser needed.

Captures webcam directly via OpenCV, runs MediaPipe hand detection +
gesture classification, and feeds results into the window management
state machine. All local, no WebSocket.

Usage:
    cd /Users/matthew/.openclaw/workspace/vision-controller/backend
    python3 run_headless.py

Press 'q' in the preview window to quit (or Ctrl-C in terminal).
Set HEADLESS_NO_PREVIEW=1 to skip the preview window entirely.
"""

import os
import sys
import time

os.environ["PYTHONUNBUFFERED"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from ml.hand_detector import HandDetector
from ml.gesture_classifier import GestureClassifier
from api.window_mode_state_machine import WindowModeStateMachine
from api.window_manager import check_accessibility

SHOW_PREVIEW = os.environ.get("HEADLESS_NO_PREVIEW", "0") != "1"
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 15


def main():
    if not check_accessibility():
        print("[ERROR] Accessibility permission not granted.")
        print("  Go to System Settings > Privacy & Security > Accessibility")
        print("  and add your terminal app (Terminal.app, iTerm, etc.)")
        sys.exit(1)

    print("[init] Starting headless gesture window manager...")
    hand_detector = HandDetector(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=0,
        frame_skip=1,
    )
    gesture_classifier = GestureClassifier()
    state_machine = WindowModeStateMachine()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open camera {CAMERA_INDEX}")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

    print(f"[init] Camera opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f"[init] Preview: {'ON (press q to quit)' if SHOW_PREVIEW else 'OFF'}")
    print()
    print("  Gestures:")
    print("    Point (1 finger)   -> select window + full screen")
    print("    Peace (2 fingers)  -> half screen (left/right by hand position)")
    print("    4 fingers          -> quarter screen (quadrant by hand position)")
    print("    Open palm (stop)   -> deselect window")
    print()

    last_gesture = None
    frame_interval = 1.0 / TARGET_FPS

    try:
        while True:
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                print("[WARN] Frame capture failed, retrying...")
                time.sleep(0.1)
                continue

            small = cv2.resize(frame, (320, 240), interpolation=cv2.INTER_LINEAR)
            detected_hands = hand_detector.detect(small)

            gesture = None
            confidence = 0.0
            landmarks_tuples = None

            if detected_hands:
                hand = detected_hands[0]
                landmarks = hand["landmarks"]
                landmarks_tuples = [(lm["x"], lm["y"], lm["z"]) for lm in landmarks]
                hand_label = hand["handedness"]

                result = gesture_classifier.classify(landmarks_tuples, hand_label)
                gesture = result["gesture"]
                confidence = result["confidence"]

                if confidence < 0.7:
                    gesture = None

            wm_result = state_machine.process(gesture, confidence, landmarks_tuples)
            wm_action = wm_result.get("action", "none")

            if gesture != last_gesture and gesture is not None:
                print(f"[gesture] {gesture} (conf: {confidence:.2f})")
                last_gesture = gesture
            elif gesture is None and last_gesture is not None:
                print("[gesture] (none)")
                last_gesture = None

            if wm_action not in ("none", "debouncing", "holding", "snap_held"):
                state = state_machine.state
                owner = state_machine.selected_owner or ""
                print(f"  [window] {wm_action} | state={state} | {owner}")
                if "layout" in wm_result:
                    print(f"           layout={wm_result['layout']} monitor={wm_result.get('monitor_idx')} zone={wm_result.get('zone')}")

            if SHOW_PREVIEW:
                display = frame.copy()
                h, w = display.shape[:2]

                status_text = f"Gesture: {gesture or 'none'} | State: {state_machine.state}"
                if state_machine.selected_owner:
                    status_text += f" | Window: {state_machine.selected_owner}"
                cv2.putText(display, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2)

                if detected_hands:
                    for hand in detected_hands:
                        for lm in hand["landmarks"]:
                            px = int(lm["x"] * w)
                            py = int(lm["y"] * h)
                            cv2.circle(display, (px, py), 3, (255, 200, 0), -1)

                cv2.imshow("Gesture Window Manager", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            elapsed = time.time() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[exit] Shutting down...")
    finally:
        cap.release()
        if SHOW_PREVIEW:
            cv2.destroyAllWindows()
        hand_detector.close()
        print("[exit] Done.")


if __name__ == "__main__":
    main()
