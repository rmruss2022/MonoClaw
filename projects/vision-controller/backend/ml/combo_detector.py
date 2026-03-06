"""
Gesture Combo Detector for Vision Controller

Tracks sequences of gestures over time and detects predefined combos.
Example: swipe left + swipe right = "dismiss"

Usage:
    detector = ComboDetector(timeout_window=2.0)
    detector.load_combos_from_config('/path/to/gestures.json')
    
    # Feed gestures as they're detected
    detector.add_gesture('peace', confidence=0.95)
    detector.add_gesture('fist', confidence=0.87)
    
    # Check for combo matches
    combo_result = detector.check_combos()
    if combo_result:
        print(f"Combo detected: {combo_result['name']}")
"""

import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque


@dataclass
class GestureEvent:
    """Represents a single gesture event in the sequence."""
    gesture: str
    confidence: float
    timestamp: float
    hand: str = "right"


class ComboDetector:
    """
    Detects gesture combos/sequences within configurable time windows.
    
    Attributes:
        timeout_window: Maximum time (seconds) between gestures in a combo
        gesture_history: Recent gestures within the time window
        combos: List of combo definitions loaded from config
    """
    
    def __init__(self, timeout_window: float = 2.0):
        """
        Initialize ComboDetector.
        
        Args:
            timeout_window: Time window in seconds for combo detection (default: 2.0)
        """
        self.timeout_window = timeout_window
        self.gesture_history: deque[GestureEvent] = deque(maxlen=10)
        self.combos: List[Dict] = []
        self.last_combo_detected: Optional[Dict] = None
        self.last_combo_time: float = 0
        self.combo_cooldown: float = 1.0  # Prevent duplicate combo triggers
        
    def load_combos_from_config(self, config_path: str) -> None:
        """
        Load combo definitions from gestures.json config file.
        
        Expected format in gestures.json:
        {
            "peace": { ... },
            "fist": { ... },
            "combos": [
                {
                    "name": "special",
                    "sequence": ["peace", "fist"],
                    "action": "applescript",
                    "script": "...",
                    "description": "Special combo action"
                }
            ]
        }
        
        Args:
            config_path: Path to gestures.json file
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.combos = config.get('combos', [])
            print(f"[ComboDetector] Loaded {len(self.combos)} combo(s) from {config_path}")
            
            for combo in self.combos:
                name = combo.get('name', 'unnamed')
                sequence = combo.get('sequence', [])
                print(f"  - {name}: {' → '.join(sequence)}")
                
        except FileNotFoundError:
            print(f"[ComboDetector] Config file not found: {config_path}")
            self.combos = []
        except json.JSONDecodeError as e:
            print(f"[ComboDetector] Error parsing JSON: {e}")
            self.combos = []
        except Exception as e:
            print(f"[ComboDetector] Error loading combos: {e}")
            self.combos = []
    
    def add_gesture(self, gesture: str, confidence: float, hand: str = "right") -> None:
        """
        Add a detected gesture to the history.
        
        Args:
            gesture: Gesture name (e.g., "peace", "fist")
            confidence: Detection confidence (0.0 to 1.0)
            hand: Which hand ("left" or "right")
        """
        # Ignore unknown gestures or low confidence
        if gesture == "unknown" or gesture is None:
            return
        
        current_time = time.time()
        
        # Don't add duplicate gestures in rapid succession (< 0.3s)
        if self.gesture_history:
            last_gesture = self.gesture_history[-1]
            if (last_gesture.gesture == gesture and 
                current_time - last_gesture.timestamp < 0.3):
                return
        
        event = GestureEvent(
            gesture=gesture,
            confidence=confidence,
            timestamp=current_time,
            hand=hand
        )
        
        self.gesture_history.append(event)
        self._clean_old_gestures()
    
    def _clean_old_gestures(self) -> None:
        """Remove gestures outside the timeout window."""
        current_time = time.time()
        cutoff_time = current_time - self.timeout_window
        
        # Remove old gestures from the left side of deque
        while self.gesture_history and self.gesture_history[0].timestamp < cutoff_time:
            self.gesture_history.popleft()
    
    def check_combos(self) -> Optional[Dict]:
        """
        Check if recent gesture history matches any defined combos.
        
        Returns:
            Dict with combo info if match found, None otherwise
            Format: {
                'name': 'combo_name',
                'sequence': ['gesture1', 'gesture2'],
                'action': 'applescript',
                'matched_gestures': [GestureEvent, ...],
                'confidence': 0.92,
                'description': 'Combo description'
            }
        """
        self._clean_old_gestures()
        
        # Need at least 2 gestures for a combo
        if len(self.gesture_history) < 2:
            return None
        
        # Check cooldown to prevent duplicate triggers
        current_time = time.time()
        if current_time - self.last_combo_time < self.combo_cooldown:
            return None
        
        # Extract recent gesture sequence
        recent_gestures = list(self.gesture_history)
        
        # Check each combo definition
        for combo in self.combos:
            combo_sequence = combo.get('sequence', [])
            if len(combo_sequence) < 2:
                continue
            
            # Try to match the combo sequence
            match_result = self._match_sequence(recent_gestures, combo_sequence)
            
            if match_result:
                matched_events, avg_confidence = match_result
                
                # Build combo result
                combo_result = {
                    'name': combo.get('name', 'unnamed'),
                    'sequence': combo_sequence,
                    'action': combo.get('action', 'none'),
                    'matched_gestures': [
                        {
                            'gesture': e.gesture,
                            'confidence': e.confidence,
                            'timestamp': e.timestamp,
                            'hand': e.hand
                        }
                        for e in matched_events
                    ],
                    'confidence': avg_confidence,
                    'description': combo.get('description', ''),
                    'timestamp': current_time
                }
                
                # Copy action-specific parameters
                if combo.get('script'):
                    combo_result['script'] = combo['script']
                if combo.get('params'):
                    combo_result['params'] = combo['params']
                if combo.get('keys'):
                    combo_result['keys'] = combo['keys']
                if combo.get('method'):
                    combo_result['method'] = combo['method']
                
                # Update last combo detection
                self.last_combo_detected = combo_result
                self.last_combo_time = current_time
                
                print(f"[ComboDetector] Combo detected: {combo_result['name']} "
                      f"({' → '.join(combo_sequence)}) confidence: {avg_confidence:.2f}")
                
                return combo_result
        
        return None
    
    def _match_sequence(
        self, 
        events: List[GestureEvent], 
        target_sequence: List[str]
    ) -> Optional[Tuple[List[GestureEvent], float]]:
        """
        Check if events contain the target sequence in order.
        
        Args:
            events: List of GestureEvent objects
            target_sequence: List of gesture names to match
            
        Returns:
            Tuple of (matched_events, avg_confidence) if match found, None otherwise
        """
        sequence_len = len(target_sequence)
        events_len = len(events)
        
        if events_len < sequence_len:
            return None
        
        # Try to match the sequence starting from different positions
        # Check most recent matches first (right to left)
        for start_idx in range(events_len - sequence_len, -1, -1):
            matched = True
            matched_events = []
            
            # Check if this starting position matches the sequence
            for i, target_gesture in enumerate(target_sequence):
                event = events[start_idx + i]
                if event.gesture == target_gesture:
                    matched_events.append(event)
                else:
                    matched = False
                    break
            
            if matched:
                # Verify time window constraint
                time_span = matched_events[-1].timestamp - matched_events[0].timestamp
                if time_span <= self.timeout_window:
                    avg_confidence = sum(e.confidence for e in matched_events) / len(matched_events)
                    return (matched_events, avg_confidence)
        
        return None
    
    def reset(self) -> None:
        """Clear gesture history and combo state."""
        self.gesture_history.clear()
        self.last_combo_detected = None
        self.last_combo_time = 0
        print("[ComboDetector] Reset: gesture history cleared")
    
    def get_history_summary(self) -> List[Dict]:
        """
        Get current gesture history summary.
        
        Returns:
            List of gesture events as dicts
        """
        return [
            {
                'gesture': e.gesture,
                'confidence': e.confidence,
                'timestamp': e.timestamp,
                'hand': e.hand
            }
            for e in self.gesture_history
        ]
    
    def set_timeout_window(self, timeout: float) -> None:
        """
        Update the combo timeout window.
        
        Args:
            timeout: New timeout in seconds
        """
        self.timeout_window = max(0.5, min(10.0, timeout))  # Clamp between 0.5-10s
        print(f"[ComboDetector] Timeout window set to {self.timeout_window}s")


if __name__ == "__main__":
    # Test the ComboDetector
    print("ComboDetector Test\n" + "="*50)
    
    detector = ComboDetector(timeout_window=2.0)
    
    # Create a test config
    test_config = {
        "peace": {"action": "applescript", "description": "Peace gesture"},
        "fist": {"action": "keyboard", "description": "Fist gesture"},
        "combos": [
            {
                "name": "special_move",
                "sequence": ["peace", "fist"],
                "action": "applescript",
                "script": "display notification \"Combo activated!\"",
                "description": "Peace then fist = special move"
            },
            {
                "name": "triple_tap",
                "sequence": ["thumbs_up", "thumbs_up", "thumbs_up"],
                "action": "openclaw_rpc",
                "description": "Three thumbs up in a row"
            }
        ]
    }
    
    # Save test config
    test_config_path = '/tmp/test_gestures.json'
    with open(test_config_path, 'w') as f:
        json.dump(test_config, f)
    
    # Load combos
    detector.load_combos_from_config(test_config_path)
    
    print("\nSimulating gesture sequence:")
    print("  1. Adding 'peace' gesture...")
    detector.add_gesture('peace', 0.95)
    time.sleep(0.5)
    
    print("  2. Adding 'fist' gesture...")
    detector.add_gesture('fist', 0.87)
    
    print("\n  3. Checking for combos...")
    result = detector.check_combos()
    
    if result:
        print(f"\n✓ Combo detected: {result['name']}")
        print(f"  Sequence: {' → '.join(result['sequence'])}")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Description: {result['description']}")
    else:
        print("\n✗ No combo detected")
    
    print("\nGesture history:")
    for event in detector.get_history_summary():
        print(f"  - {event['gesture']} (confidence: {event['confidence']:.2f})")
    
    print("\nComboDetector test complete!")
