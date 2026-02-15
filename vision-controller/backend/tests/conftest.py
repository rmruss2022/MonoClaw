""" Shared fixtures for Vision Controller tests

Provides synthetic hand landmarks for all 5 gestures plus edge cases
"""

import pytest
import numpy as np
from typing import List, Tuple, Dict, Any


@pytest.fixture
def base_hand_landmarks() -> List[Tuple[float, float, float]]:
    """ Base hand landmarks at neutral/open position
    
    Returns 21 landmarks in MediaPipe format: (x, y, z)
    """
    # Wrist at origin
    wrist = (0.5, 0.8, 0.0)
    landmarks = [wrist]
    
    # Thumb (extends outward)
    landmarks.extend([
        (0.45, 0.75, 0.0),  # CMC
        (0.40, 0.70, 0.0),  # MCP
        (0.35, 0.65, 0.0),  # IP
        (0.30, 0.60, 0.0),  # TIP
    ])
    
    # Index finger (vertical path)
    landmarks.extend([
        (0.50, 0.70, 0.0),  # MCP
        (0.50, 0.60, 0.0),  # PIP
        (0.50, 0.50, 0.0),  # DIP
        (0.50, 0.40, 0.0),  # TIP
    ])
    
    # Middle finger (vertical path)
    landmarks.extend([
        (0.55, 0.70, 0.0),  # MCP
        (0.55, 0.60, 0.0),  # PIP
        (0.55, 0.50, 0.0),  # DIP
        (0.55, 0.40, 0.0),  # TIP
    ])
    
    # Ring finger (vertical path)
    landmarks.extend([
        (0.60, 0.70, 0.0),  # MCP
        (0.60, 0.60, 0.0),  # PIP
        (0.60, 0.50, 0.0),  # DIP
        (0.60, 0.40, 0.0),  # TIP
    ])
    
    # Pinky finger (vertical path)
    landmarks.extend([
        (0.65, 0.70, 0.0),  # MCP
        (0.65, 0.60, 0.0),  # PIP
        (0.65, 0.50, 0.0),  # DIP
        (0.65, 0.40, 0.0),  # TIP
    ])
    
    return landmarks


@pytest.fixture
def peace_gesture_landmarks() -> List[Tuple[float, float, float]]:
    """ Peace gesture: index and middle fingers extended, others curled """
    wrist = (0.5, 0.8, 0.0)
    return [
        wrist,  # 0: WRIST
        (0.45, 0.75, 0.0),  # 1: THUMB_CMC
        (0.42, 0.72, 0.0),  # 2: THUMB_MCP
        (0.40, 0.70, 0.0),  # 3: THUMB_IP
        (0.38, 0.68, 0.0),  # 4: THUMB_TIP (curled in)
        (0.50, 0.70, 0.0),  # 5: INDEX_MCP
        (0.50, 0.60, 0.0),  # 6: INDEX_PIP
        (0.50, 0.50, 0.0),  # 7: INDEX_DIP
        (0.50, 0.40, 0.0),  # 8: INDEX_TIP (extended)
        (0.55, 0.70, 0.0),  # 9: MIDDLE_MCP
        (0.55, 0.60, 0.0),  # 10: MIDDLE_PIP
        (0.55, 0.50, 0.0),  # 11: MIDDLE_DIP
        (0.55, 0.40, 0.0),  # 12: MIDDLE_TIP (extended)
        (0.60, 0.70, 0.0),  # 13: RING_MCP
        (0.58, 0.65, 0.0),  # 14: RING_PIP
        (0.56, 0.70, 0.0),  # 15: RING_DIP (curled - tip closer)
        (0.55, 0.72, 0.0),  # 16: RING_TIP (curled)
        (0.65, 0.70, 0.0),  # 17: PINKY_MCP
        (0.63, 0.65, 0.0),  # 18: PINKY_PIP
        (0.61, 0.70, 0.0),  # 19: PINKY_DIP (curled)
        (0.60, 0.72, 0.0),  # 20: PINKY_TIP (curled)
    ]


@pytest.fixture
def thumbs_up_landmarks() -> List[Tuple[float, float, float]]:
    """ Thumbs up gesture: only thumb extended, all other fingers curled """
    wrist = (0.5, 0.8, 0.0)
    return [
        wrist,  # 0: WRIST
        (0.45, 0.75, 0.0),  # 1: THUMB_CMC
        (0.42, 0.70, 0.0),  # 2: THUMB_MCP
        (0.40, 0.60, 0.0),  # 3: THUMB_IP
        (0.38, 0.50, 0.0),  # 4: THUMB_TIP (extended up)
        (0.50, 0.70, 0.0),  # 5: INDEX_MCP
        (0.48, 0.68, 0.0),  # 6: INDEX_PIP
        (0.50, 0.72, 0.0),  # 7: INDEX_DIP (curled)
        (0.52, 0.75, 0.0),  # 8: INDEX_TIP (curled into palm)
        (0.55, 0.70, 0.0),  # 9: MIDDLE_MCP
        (0.53, 0.68, 0.0),  # 10: MIDDLE_PIP
        (0.55, 0.72, 0.0),  # 11: MIDDLE_DIP (curled)
        (0.57, 0.75, 0.0),  # 12: MIDDLE_TIP (curled)
        (0.60, 0.70, 0.0),  # 13: RING_MCP
        (0.58, 0.68, 0.0),  # 14: RING_PIP
        (0.60, 0.72, 0.0),  # 15: RING_DIP (curled)
        (0.62, 0.75, 0.0),  # 16: RING_TIP (curled)
        (0.65, 0.70, 0.0),  # 17: PINKY_MCP
        (0.63, 0.68, 0.0),  # 18: PINKY_PIP
        (0.65, 0.72, 0.0),  # 19: PINKY_DIP (curled)
        (0.67, 0.75, 0.0),  # 20: PINKY_TIP (curled)
    ]


@pytest.fixture
def fist_landmarks() -> List[Tuple[float, float, float]]:
    """ Fist gesture: all fingers curled into palm """
    wrist = (0.5, 0.8, 0.0)
    return [
        wrist,  # 0: WRIST
        (0.45, 0.75, 0.0),  # 1: THUMB_CMC
        (0.47, 0.77, 0.0),  # 2: THUMB_MCP (curled over)
        (0.46, 0.79, 0.0),  # 3: THUMB_IP
        (0.45, 0.81, 0.0),  # 4: THUMB_TIP (curled)
        (0.50, 0.75, 0.0),  # 5: INDEX_MCP
        (0.48, 0.77, 0.0),  # 6: INDEX_PIP
        (0.52, 0.79, 0.0),  # 7: INDEX_DIP
        (0.50, 0.78, 0.0),  # 8: INDEX_TIP (curled into palm)
        (0.55, 0.75, 0.0),  # 9: MIDDLE_MCP
        (0.53, 0.77, 0.0),  # 10: MIDDLE_PIP
        (0.57, 0.79, 0.0),  # 11: MIDDLE_DIP
        (0.55, 0.78, 0.0),  # 12: MIDDLE_TIP (curled)
        (0.60, 0.75, 0.0),  # 13: RING_MCP
        (0.58, 0.77, 0.0),  # 14: RING_PIP
        (0.62, 0.79, 0.0),  # 15: RING_DIP
        (0.60, 0.78, 0.0),  # 16: RING_TIP (curled)
        (0.65, 0.75, 0.0),  # 17: PINKY_MCP
        (0.63, 0.77, 0.0),  # 18: PINKY_PIP
        (0.67, 0.79, 0.0),  # 19: PINKY_DIP
        (0.65, 0.78, 0.0),  # 20: PINKY_TIP (curled)
    ]


@pytest.fixture
def point_landmarks() -> List[Tuple[float, float, float]]:
    """ Point gesture: only index finger extended """
    wrist = (0.5, 0.8, 0.0)
    return [
        wrist,  # 0: WRIST
        (0.45, 0.75, 0.0),  # 1: THUMB_CMC
        (0.42, 0.72, 0.0),  # 2: THUMB_MCP
        (0.40, 0.70, 0.0),  # 3: THUMB_IP
        (0.38, 0.68, 0.0),  # 4: THUMB_TIP (curled in)
        (0.50, 0.70, 0.0),  # 5: INDEX_MCP
        (0.50, 0.60, 0.0),  # 6: INDEX_PIP
        (0.50, 0.50, 0.0),  # 7: INDEX_DIP
        (0.50, 0.40, 0.0),  # 8: INDEX_TIP (extended)
        (0.55, 0.70, 0.0),  # 9: MIDDLE_MCP
        (0.53, 0.68, 0.0),  # 10: MIDDLE_PIP
        (0.55, 0.72, 0.0),  # 11: MIDDLE_DIP (curled)
        (0.57, 0.75, 0.0),  # 12: MIDDLE_TIP (curled)
        (0.60, 0.70, 0.0),  # 13: RING_MCP
        (0.58, 0.68, 0.0),  # 14: RING_PIP
        (0.60, 0.72, 0.0),  # 15: RING_DIP (curled)
        (0.62, 0.75, 0.0),  # 16: RING_TIP (curled)
        (0.65, 0.70, 0.0),  # 17: PINKY_MCP
        (0.63, 0.68, 0.0),  # 18: PINKY_PIP
        (0.65, 0.72, 0.0),  # 19: PINKY_DIP (curled)
        (0.67, 0.75, 0.0),  # 20: PINKY_TIP (curled)
    ]


@pytest.fixture
def stop_landmarks() -> List[Tuple[float, float, float]]:
    """ Stop gesture (open palm): all fingers extended """
    wrist = (0.5, 0.8, 0.0)
    return [
        wrist,  # 0: WRIST
        (0.40, 0.75, 0.0),  # 1: THUMB_CMC
        (0.35, 0.70, 0.0),  # 2: THUMB_MCP
        (0.30, 0.65, 0.0),  # 3: THUMB_IP
        (0.25, 0.60, 0.0),  # 4: THUMB_TIP (extended outward)
        (0.50, 0.70, 0.0),  # 5: INDEX_MCP
        (0.50, 0.60, 0.0),  # 6: INDEX_PIP
        (0.50, 0.50, 0.0),  # 7: INDEX_DIP
        (0.50, 0.40, 0.0),  # 8: INDEX_TIP (extended up)
        (0.55, 0.70, 0.0),  # 9: MIDDLE_MCP
        (0.55, 0.60, 0.0),  # 10: MIDDLE_PIP
        (0.55, 0.50, 0.0),  # 11: MIDDLE_DIP
        (0.55, 0.40, 0.0),  # 12: MIDDLE_TIP (extended up)
        (0.60, 0.70, 0.0),  # 13: RING_MCP
        (0.60, 0.60, 0.0),  # 14: RING_PIP
        (0.60, 0.50, 0.0),  # 15: RING_DIP
        (0.60, 0.40, 0.0),  # 16: RING_TIP (extended up)
        (0.65, 0.70, 0.0),  # 17: PINKY_MCP
        (0.65, 0.60, 0.0),  # 18: PINKY_PIP
        (0.65, 0.50, 0.0),  # 19: PINKY_DIP
        (0.65, 0.40, 0.0),  # 20: PINKY_TIP (extended up)
    ]


@pytest.fixture
def partial_gesture_landmarks() -> List[Tuple[float, float, float]]:
    """ Ambiguous gesture: 3 fingers extended (between point and peace) """
    wrist = (0.5, 0.8, 0.0)
    return [
        wrist,  # 0: WRIST
        (0.45, 0.75, 0.0),  # 1: THUMB_CMC
        (0.42, 0.72, 0.0),  # 2: THUMB_MCP
        (0.40, 0.70, 0