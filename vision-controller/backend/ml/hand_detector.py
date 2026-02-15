"""Hand Detector Module - MediaPipe HandLandmarker

Provides real-time hand detection and landmark extraction.
Optimized for <100ms latency.
"""

import numpy as np
import cv2
from typing import List, Dict, Any, Optional
import mediapipe as mp
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions
from mediapipe.tasks.python.core.base_options import BaseOptions
import os


class HandDetector:
    """Real-time hand detection using MediaPipe HandLandmarker."""

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 0,
        frame_skip: int = 1
    ):
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.frame_skip = frame_skip
        self._frame_count = 0
        self._last_result = []

        # Get model path
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        model_path = os.path.join(backend_dir, 'models', 'hand_landmarker.task')

        base_options = BaseOptions(model_asset_path=model_path)
        options = HandLandmarkerOptions(
            base_options=base_options,
            num_hands=1,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_tracking_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self.detector = HandLandmarker.create_from_options(options)

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect hands in a video frame."""
        self._frame_count += 1
        if self.frame_skip > 1 and self._frame_count % self.frame_skip != 0:
            return self._last_result

        if frame is None or frame.size == 0:
            return []

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        detection_result = self.detector.detect(mp_image)
        detected_hands = []

        if detection_result and detection_result.hand_landmarks:
            for i, landmarks in enumerate(detection_result.hand_landmarks):
                handedness = "Unknown"
                confidence = 0.5

                if detection_result.handedness and i < len(detection_result.handedness):
                    handedness_category = detection_result.handedness[i]
                    if handedness_category and len(handedness_category) > 0:
                        handedness = handedness_category[0].category_name
                        confidence = handedness_category[0].score

                landmark_list = [
                    {"x": float(lm.x), "y": float(lm.y), "z": float(lm.z)}
                    for lm in landmarks
                ]

                detected_hands.append({
                    "handedness": handedness,
                    "landmarks": landmark_list,
                    "confidence": float(confidence)
                })

        self._last_result = detected_hands
        return detected_hands

    def detect_fast(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Ultra-fast detection returning landmark numpy array."""
        hands = self.detect(frame)
        if not hands:
            return None
        return np.array([
            [lm['x'], lm['y'], lm['z']]
            for lm in hands[0]['landmarks']
        ])

    def close(self):
        """Release resources."""
        if hasattr(self.detector, 'close'):
            self.detector.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
