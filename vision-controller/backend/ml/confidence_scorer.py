"""
Confidence Scoring System for Vision Controller
Tracks gesture stability and adjusts confidence scores
"""

import time
from collections import deque
from typing import Dict, List, Optional, Tuple

class ConfidenceScorer:
    """
    Enhance gesture confidence scoring with temporal stability
    """
    
    def __init__(self, window_size: int = 5, stability_weight: float = 0.3):
        """
        Initialize confidence scorer
        
        Args:
            window_size: Number of recent frames to track (for stability)
            stability_weight: Weight of stability score (0-1)
        """
        self.window_size = window_size
        self.stability_weight = stability_weight
        
        # Track recent gesture detections
        self.gesture_history = deque(maxlen=window_size)
        self.confidence_history = deque(maxlen=window_size)
        self.timestamp_history = deque(maxlen=window_size)
        
        # Track hand presence
        self.hand_present_history = deque(maxlen=window_size)
        
    def update(self, gesture: Optional[str], 
               confidence: float, 
               hand_present: bool = True) -> Dict[str, any]:
        """
        Update confidence score with temporal stability
        
        Args:
            gesture: Detected gesture name (or None)
            confidence: Raw confidence score from classifier (0-1)
            hand_present: Whether hand is detected in frame
            
        Returns:
            Dict with keys:
                - gesture: Final gesture name
                - raw_confidence: Original confidence
                - adjusted_confidence: Confidence after stability adjustment
                - stability_score: How stable the gesture is over time
                - hand_present: Whether hand was detected
        """
        current_time = time.time()
        
        # Update histories
        self.gesture_history.append(gesture)
        self.confidence_history.append(confidence)
        self.timestamp_history.append(current_time)
        self.hand_present_history.append(hand_present)
        
        # Calculate stability score
        stability_score = self._calculate_stability()
        
        # Adjust confidence based on stability
        adjusted_confidence = self._adjust_confidence(confidence, stability_score)
        
        return {
            'gesture': gesture,
            'raw_confidence': confidence,
            'adjusted_confidence': adjusted_confidence,
            'stability_score': stability_score,
            'hand_present': hand_present,
            'history_length': len(self.gesture_history)
        }
    
    def _calculate_stability(self) -> float:
        """
        Calculate gesture stability score (0-1)
        
        A gesture is stable if:
        - Same gesture appears consistently
        - Confidence values are consistent
        - Timing is regular
        
        Returns:
            Stability score (0-1, higher is more stable)
        """
        if len(self.gesture_history) < 2:
            return 0.0
        
        # 1. Gesture consistency
        non_none_gestures = [g for g in self.gesture_history if g is not None]
        if len(non_none_gestures) == 0:
            gesture_consistency = 0.0
        else:
            most_common = max(set(non_none_gestures), key=non_none_gestures.count)
            gesture_consistency = non_none_gestures.count(most_common) / len(self.gesture_history)
        
        # 2. Confidence consistency (low variance is better)
        non_zero_confidences = [c for c in self.confidence_history if c > 0]
        if len(non_zero_confidences) < 2:
            confidence_consistency = 0.0
        else:
            mean_conf = sum(non_zero_confidences) / len(non_zero_confidences)
            variance = sum((c - mean_conf) ** 2 for c in non_zero_confidences) / len(non_zero_confidences)
            # Normalize variance to 0-1 range (assume max variance is 0.25)
            confidence_consistency = max(0, 1 - (variance / 0.25))
        
        # 3. Hand presence consistency
        hand_consistency = sum(self.hand_present_history) / len(self.hand_present_history)
        
        # Combined stability score
        stability = (
            gesture_consistency * 0.5 +
            confidence_consistency * 0.3 +
            hand_consistency * 0.2
        )
        
        return stability
    
    def _adjust_confidence(self, raw_confidence: float, stability_score: float) -> float:
        """
        Adjust confidence score based on stability
        
        Args:
            raw_confidence: Original confidence from classifier
            stability_score: Stability score (0-1)
            
        Returns:
            Adjusted confidence (0-1)
        """
        # Blend raw confidence with stability
        adjusted = (
            raw_confidence * (1 - self.stability_weight) +
            (raw_confidence * stability_score) * self.stability_weight
        )
        
        # Ensure bounds
        return max(0.0, min(1.0, adjusted))
    
    def reset(self):
        """Reset all tracking histories"""
        self.gesture_history.clear()
        self.confidence_history.clear()
        self.timestamp_history.clear()
        self.hand_present_history.clear()
    
    def get_dominant_gesture(self, min_confidence: float = 0.7) -> Optional[str]:
        """
        Get the most stable gesture from recent history
        
        Args:
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dominant gesture name or None
        """
        if len(self.gesture_history) == 0:
            return None
        
        # Filter by confidence
        valid_gestures = [
            g for g, c in zip(self.gesture_history, self.confidence_history)
            if g is not None and c >= min_confidence
        ]
        
        if len(valid_gestures) == 0:
            return None
        
        # Return most common
        return max(set(valid_gestures), key=valid_gestures.count)
    
    def get_stats(self) -> Dict[str, any]:
        """Get current tracking statistics"""
        return {
            'history_length': len(self.gesture_history),
            'recent_gestures': list(self.gesture_history),
            'recent_confidences': list(self.confidence_history),
            'stability': self._calculate_stability(),
            'dominant_gesture': self.get_dominant_gesture()
        }


if __name__ == "__main__":
    # Test confidence scorer
    scorer = ConfidenceScorer(window_size=5, stability_weight=0.3)
    
    print("Confidence Scorer Test")
    print("=" * 50)
    
    # Simulate consistent gesture detection
    print("\nSimulating stable 'peace' gesture:")
    for i in range(6):
        result = scorer.update('peace', 0.85 + (i % 3) * 0.05, hand_present=True)
        print(f"Frame {i+1}: raw={result['raw_confidence']:.2f}, "
              f"adjusted={result['adjusted_confidence']:.2f}, "
              f"stability={result['stability_score']:.2f}")
    
    print(f"\nDominant gesture: {scorer.get_dominant_gesture()}")
    
    # Simulate unstable detection
    print("\nSimulating unstable gestures:")
    scorer.reset()
    gestures = ['peace', 'thumbs_up', 'peace', 'fist', 'peace']
    for i, gesture in enumerate(gestures):
        result = scorer.update(gesture, 0.7, hand_present=True)
        print(f"Frame {i+1} ({gesture}): adjusted={result['adjusted_confidence']:.2f}, "
              f"stability={result['stability_score']:.2f}")
    
    print(f"\nDominant gesture: {scorer.get_dominant_gesture()}")
    print("\nConfidence Scorer initialized successfully")
