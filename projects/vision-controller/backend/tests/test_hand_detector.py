"""
Unit tests for HandDetector
Tests initialization and mocks MediaPipe interactions
"""
import pytest
import sys
import os
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ml'))
from hand_detector import HandDetector


class TestHandDetector:
    """Tests for the HandDetector class"""
    
    def test_initialization_default_params(self):
        """Test HandDetector initialization with default parameters"""
        detector = HandDetector()
        
        assert detector.min_detection_confidence == 0.7
        assert detector.min_tracking_confidence == 0.5
        assert detector.hands is not None
    
    def test_initialization_custom_params(self):
        """Test HandDetector initialization with custom confidence values"""
        detector = HandDetector(
            min_detection_confidence=0.9,
            min_tracking_confidence=0.7
        )
        
        assert detector.min_detection_confidence == 0.9
        assert detector.min_tracking_confidence == 0.7
    
    def test_initialization_stores_mp_references(self):
        """Test that MediaPipe references are stored"""
        detector = HandDetector()
        
        assert hasattr(detector, 'mp_hands')
        assert hasattr(detector, 'mp_drawing')
        assert detector.mp_hands is not None
    
    @patch('hand_detector.mp.solutions.hands.Hands')
    def test_detect_no_hands_found(self, mock_hands_class):
        """Test detect when no hands are found"""
        # Setup mock
        mock_hands = MagicMock()
        mock_hands.process.return_value = MagicMock(
            multi_hand_landmarks=None,
            multi_handedness=None
        )
        mock_hands_class.return_value = mock_hands
        
        detector = HandDetector()
        detector.hands = mock_hands
        
        # Create a test frame
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        result = detector.detect(frame)
        
        assert result == []
        mock_hands.process.assert_called_once()
    
    @patch('hand_detector.mp.solutions.hands.Hands')
    def test_detect_single_hand_found(self, mock_hands_class):
        """Test detect when one hand is found"""
        # Create mock landmarks
        mock_landmark = MagicMock()
        mock_landmark.x = 0.5
        mock_landmark.y = 0.5
        mock_landmark.z = 0.0
        
        mock_hand_landmarks = MagicMock()
        mock_hand_landmarks.landmark = [mock_landmark] * 21
        
        mock_handedness = MagicMock()
        mock_handedness.classification = [MagicMock(label="Right", score=0.95)]
        
        # Setup mock
        mock_hands = MagicMock()
        mock_hands.process.return_value = MagicMock(
            multi_hand_landmarks=[mock_hand_landmarks],
            multi_handedness=[mock_handedness]
        )
        mock_hands_class.return_value = mock_hands
        
        detector = HandDetector()
        detector.hands = mock_hands
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        
        assert len(result) == 1
        assert result[0]['handedness'] == 'Right'
        assert result[0]['confidence'] == 0.95
        assert len(result[0]['landmarks']) == 21
    
    @patch('hand_detector.mp.solutions.hands.Hands')
    def test_detect_multiple_hands(self, mock_hands_class):
        """Test detect when multiple hands are found"""
        # Create mock landmarks for two hands
        mock_landmark = MagicMock()
        mock_landmark.x = 0.5
        mock_landmark.y = 0.5
        mock_landmark.z = 0.0
        
        mock_hand_landmarks1 = MagicMock()
        mock_hand_landmarks1.landmark = [mock_landmark] * 21
        
        mock_hand_landmarks2 = MagicMock()
        mock_hand_landmarks2.landmark = [mock_landmark] * 21
        
        mock_handedness1 = MagicMock()
        mock_handedness1.classification = [MagicMock(label="Right", score=0.92)]
        
        mock_handedness2 = MagicMock()
        mock_handedness2.classification = [MagicMock(label="Left", score=0.88)]
        
        # Setup mock
        mock_hands = MagicMock()
        mock_hands.process.return_value = MagicMock(
            multi_hand_landmarks=[mock_hand_landmarks1, mock_hand_landmarks2],
            multi_handedness=[mock_handedness1, mock_handedness2]
        )
        mock_hands_class.return_value = mock_hands
        
        detector = HandDetector()
        detector.hands = mock_hands
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        
        assert len(result) == 2
        assert result[0]['handedness'] == 'Right'
        assert result[1]['handedness'] == 'Left'
    
    @patch('hand_detector.mp.solutions.hands.Hands')
    def test_detect_landmark_structure(self, mock_hands_class):
        """Test that detected landmarks have correct structure"""
        # Create mock landmarks
        mock_landmark = MagicMock()
        mock_landmark.x = 0.3
        mock_landmark.y = 0.4
        mock_landmark.z = 0.1
        
        mock_hand_landmarks = MagicMock()
        mock_hand_landmarks.landmark = [mock_landmark] * 21
        
        mock_handedness = MagicMock()
        mock_handedness.classification = [MagicMock(label="Right", score=0.9)]
        
        # Setup mock
        mock_hands = MagicMock()
        mock_hands.process.return_value = MagicMock(
            multi_hand_landmarks=[mock_hand_landmarks],
            multi_handedness=[mock_handedness]
        )
        mock_hands_class.return_value = mock_hands
        
        detector = HandDetector()
        detector.hands = mock_hands
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        
        # Check landmark structure
        landmark =