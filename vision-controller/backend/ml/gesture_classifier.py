"""
Gesture Classifier for Vision Controller
Recognizes 5 basic hand gestures: peace, thumbs_up, fist, point, stop
Plus custom trained gestures from custom_gestures.json
"""

import math
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class GestureClassifier:
    """Classifies hand gestures from MediaPipe landmarks"""
    
    def __init__(self):
        self.gesture_names = ['peace', 'thumbs_up', 'fist', 'point', 'stop', 'four_fingers', 'unknown']
        self.custom_gestures = {}
        self.load_custom_gestures()
        
    def _get_finger_states(self, landmarks: List[Tuple[float, float, float]]) -> Dict[str, bool]:
        """
        Determine if each finger is extended
        Returns dict: {'thumb': bool, 'index': bool, 'middle': bool, 'ring': bool, 'pinky': bool}
        """
        # Landmark indices for finger tips and joints
        finger_tips = {
            'thumb': 4,
            'index': 8,
            'middle': 12,
            'ring': 16,
            'pinky': 20
        }
        
        finger_joints = {
            'thumb': 3,   # Use IP joint for thumb
            'index': 6,   # PIP joint
            'middle': 10,
            'ring': 14,
            'pinky': 18
        }
        
        finger_bases = {
            'thumb': 2,
            'index': 5,
            'middle': 9,
            'ring': 13,
            'pinky': 17
        }
        
        states = {}
        
        # For thumb: check if tip is further from palm than base
        wrist = landmarks[0]
        thumb_tip = landmarks[finger_tips['thumb']]
        thumb_base = landmarks[finger_bases['thumb']]
        
        thumb_tip_dist = self._distance_3d(wrist, thumb_tip)
        thumb_base_dist = self._distance_3d(wrist, thumb_base)
        states['thumb'] = thumb_tip_dist > thumb_base_dist * 1.2
        
        # For other fingers: check if tip is above the PIP joint
        for finger in ['index', 'middle', 'ring', 'pinky']:
            tip = landmarks[finger_tips[finger]]
            joint = landmarks[finger_joints[finger]]
            base = landmarks[finger_bases[finger]]
            
            # Extended if tip is further from base than joint is (stricter threshold)
            tip_to_base = self._distance_3d(tip, base)
            joint_to_base = self._distance_3d(joint, base)
            
            # Also check Y-coordinate (vertical position) - extended fingers point up
            # Tip should be higher (lower y value in image coords) than joint
            # Use -0.01 for more lenient vertical check (1% screen height)
            tip_higher = tip[1] < joint[1] + 0.01  # Allow slight downward tilt
            
            # Both conditions must be true
            states[finger] = (tip_to_base > joint_to_base * 1.4) and tip_higher
            
        return states
    
    def _distance_3d(self, p1: Tuple[float, float, float], 
                     p2: Tuple[float, float, float]) -> float:
        """Calculate 3D Euclidean distance"""
        return math.sqrt(
            (p1[0] - p2[0])**2 + 
            (p1[1] - p2[1])**2 + 
            (p1[2] - p2[2])**2
        )
    
    def load_custom_gestures(self):
        """Load custom gestures from custom_gestures.json"""
        try:
            config_path = Path("/Users/matthew/Desktop/vision-controller/config/custom_gestures.json")
            if config_path.exists():
                with open(config_path, 'r') as f:
                    self.custom_gestures = json.load(f)
                print(f"[GestureClassifier] Loaded {len(self.custom_gestures)} custom gestures: {list(self.custom_gestures.keys())}")
            else:
                self.custom_gestures = {}
                print("[GestureClassifier] No custom gestures file found")
        except Exception as e:
            print(f"[GestureClassifier] Error loading custom gestures: {e}")
            self.custom_gestures = {}
    
    def _normalize_landmarks(self, landmarks: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Normalize landmarks relative to wrist for scale/translation invariance"""
        wrist = landmarks[0]
        normalized = []
        
        # Calculate bounding box for scaling
        max_dist = 0.0
        for lm in landmarks:
            dist = self._distance_3d(wrist, lm)
            if dist > max_dist:
                max_dist = dist
        
        # Normalize each landmark
        for lm in landmarks:
            if max_dist > 0:
                normalized.append((
                    (lm[0] - wrist[0]) / max_dist,
                    (lm[1] - wrist[1]) / max_dist,
                    (lm[2] - wrist[2]) / max_dist
                ))
            else:
                normalized.append((0.0, 0.0, 0.0))
        
        return normalized
    
    def _compare_landmarks(self, landmarks1: List[Tuple[float, float, float]], 
                          landmarks2: List[Tuple[float, float, float]]) -> float:
        """Compare two landmark sets and return similarity score (0-1, higher is more similar)"""
        if len(landmarks1) != len(landmarks2):
            return 0.0
        
        # Normalize both landmark sets
        norm1 = self._normalize_landmarks(landmarks1)
        norm2 = self._normalize_landmarks(landmarks2)
        
        # Calculate average Euclidean distance
        total_distance = 0.0
        for lm1, lm2 in zip(norm1, norm2):
            total_distance += self._distance_3d(lm1, lm2)
        
        avg_distance = total_distance / len(landmarks1)
        
        # Convert distance to similarity score (inverse exponential)
        # Distance of 0 = similarity 1.0, distance increases = similarity decreases
        # Increased sensitivity factor from 5.0 to 8.0 for better discrimination
        similarity = math.exp(-avg_distance * 8.0)
        
        return similarity
    
    def _match_custom_gesture(self, landmarks: List[Tuple[float, float, float]]) -> Dict[str, any]:
        """Match current landmarks against all custom gestures"""
        best_match = None
        best_confidence = 0.0
        
        for gesture_name, gesture_data in self.custom_gestures.items():
            samples = gesture_data.get('samples', [])
            
            # Compare against each sample and take the best match
            max_similarity = 0.0
            for sample in samples:
                # Convert sample from dict format to tuple format
                sample_landmarks = [(lm['x'], lm['y'], lm['z']) for lm in sample]
                similarity = self._compare_landmarks(landmarks, sample_landmarks)
                if similarity > max_similarity:
                    max_similarity = similarity
            
            if max_similarity > best_confidence:
                best_confidence = max_similarity
                best_match = gesture_name
        
        return {
            'gesture': best_match,
            'confidence': best_confidence
        }
    
    def _calculate_confidence(self, finger_states: Dict[str, bool], 
                            expected_states: Dict[str, bool]) -> float:
        """Calculate confidence score based on how well fingers match expected pattern"""
        matches = sum(1 for k in finger_states if finger_states[k] == expected_states[k])
        confidence = matches / len(finger_states)
        return confidence
    
    def classify(self, landmarks: List[Tuple[float, float, float]], 
                 hand_label: str = "right") -> Dict[str, any]:
        """
        Classify gesture from 21 hand landmarks
        Checks both built-in and custom gestures
        
        Args:
            landmarks: List of 21 (x, y, z) tuples from MediaPipe
            hand_label: "right" or "left"
            
        Returns:
            Dict with keys: 'gesture', 'confidence', 'hand'
        """
        if len(landmarks) != 21:
            return {
                'gesture': 'unknown',
                'confidence': 0.0,
                'hand': hand_label
            }
        
        # First, try to match against custom gestures
        custom_result = self._match_custom_gesture(landmarks)
        custom_confidence = custom_result.get('confidence', 0.0)
        custom_gesture = custom_result.get('gesture')
        
        # Then check built-in gestures
        finger_states = self._get_finger_states(landmarks)
        
        # DEBUG: Log finger states for debugging
        # print(f"[DEBUG] Finger states: {finger_states}")
        
        # Define expected states for each gesture
        gesture_patterns = {
            'peace': {
                'thumb': False,
                'index': True,
                'middle': True,
                'ring': False,
                'pinky': False
            },
            'thumbs_up': {
                'thumb': True,
                'index': False,
                'middle': False,
                'ring': False,
                'pinky': False
            },
            'fist': {
                'thumb': False,
                'index': False,
                'middle': False,
                'ring': False,
                'pinky': False
            },
            'point': {
                'thumb': False,
                'index': True,
                'middle': False,
                'ring': False,
                'pinky': False
            },
            'stop': {
                'thumb': True,
                'index': True,
                'middle': True,
                'ring': True,
                'pinky': True
            },
            'four_fingers': {
                'thumb': False,
                'index': True,
                'middle': True,
                'ring': True,
                'pinky': True
            }
        }
        
        # Find best matching built-in gesture
        best_builtin_gesture = 'unknown'
        best_builtin_confidence = 0.0
        
        for gesture_name, expected_states in gesture_patterns.items():
            confidence = self._calculate_confidence(finger_states, expected_states)
            if confidence > best_builtin_confidence:
                best_builtin_confidence = confidence
                best_builtin_gesture = gesture_name
        
        # Require minimum confidence of 0.6 (3 out of 5 fingers correct) for built-in
        if best_builtin_confidence < 0.6:
            best_builtin_gesture = 'unknown'
            best_builtin_confidence = 0.0
        
        # Choose between custom and built-in based on confidence
        # Priority logic:
        # 1. If custom gesture has confidence >= 0.65, prefer it over built-in
        # 2. If custom confidence >= 0.5, prefer it if built-in confidence < 0.8
        # 3. Otherwise use built-in if confidence >= 0.6
        
        if custom_confidence >= 0.65:
            # High confidence custom gesture wins
            return {
                'gesture': custom_gesture,
                'confidence': custom_confidence,
                'hand': hand_label,
                'type': 'custom'
            }
        elif custom_confidence >= 0.5 and best_builtin_confidence < 0.8:
            # Medium confidence custom gesture wins if built-in isn't very confident
            return {
                'gesture': custom_gesture,
                'confidence': custom_confidence,
                'hand': hand_label,
                'type': 'custom'
            }
        elif best_builtin_confidence > 0:
            return {
                'gesture': best_builtin_gesture,
                'confidence': best_builtin_confidence,
                'hand': hand_label,
                'type': 'builtin'
            }
        else:
            return {
                'gesture': 'unknown',
                'confidence': 0.0,
                'hand': hand_label,
                'type': 'none'
            }


if __name__ == "__main__":
    # Test with synthetic landmarks
    classifier = GestureClassifier()
    
    # Create test landmarks (simplified example)
    test_landmarks = [(0, 0, 0)] * 21  # Wrist at origin
    
    print("Gesture Classifier initialized successfully")
    print("Supported gestures:", classifier.gesture_names)
