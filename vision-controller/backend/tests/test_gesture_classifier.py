""" Unit tests for GestureClassifier Tests all 5 gestures with synthetic landmarks, edge cases, unknown gestures"""

import pytest
import sys
import os
import math

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ml'))

from gesture_classifier import GestureClassifier


class TestGestureClassifier:
    """Tests for the GestureClassifier class"""

    @pytest.fixture
    def classifier(self):
        """Fixture to create a GestureClassifier instance"""
        return GestureClassifier()

    def test_initialization(self, classifier):
        """Test that classifier initializes with correct gesture names"""
        assert 'peace' in classifier.gesture_names
        assert 'thumbs_up' in classifier.gesture_names
        assert 'fist' in classifier.gesture_names
        assert 'point' in classifier.gesture_names
        assert 'stop' in classifier.gesture_names
        assert 'unknown' in classifier.gesture_names
        assert len(classifier.gesture_names) == 6

    def test_distance_3d_calculation(self, classifier):
        """Test 3D distance calculation"""
        p1 = (0.0, 0.0, 0.0)
        p2 = (3.0, 4.0, 0.0)
        distance = classifier._distance_3d(p1, p2)
        assert distance == 5.0  # 3-4-5 triangle

    def test_distance_3d_with_z(self, classifier):
        """Test 3D distance with z-coordinate"""
        p1 = (0.0, 0.0, 0.0)
        p2 = (1.0, 1.0, 1.0)
        distance = classifier._distance_3d(p1, p2)
        expected = math.sqrt(3)
        assert abs(distance - expected) < 0.001

    def test_get_finger_states_structure(self, classifier, base_hand_landmarks):
        """Test that finger states returns correct structure"""
        states = classifier._get_finger_states(base_hand_landmarks)
        assert 'thumb' in states
        assert 'index' in states
        assert 'middle' in states
        assert 'ring' in states
        assert 'pinky' in states
        assert isinstance(states['thumb'], bool)

    def test_classify_wrong_landmark_count(self, classifier):
        """Test classification with wrong number of landmarks"""
        # Should return unknown with 0 confidence
        result = classifier.classify([(0, 0, 0)] * 10)  # Only 10 landmarks
        assert result['gesture'] == 'unknown'
        assert result['confidence'] == 0.0

    def test_classify_empty_landmarks(self, classifier):
        """Test classification with empty landmarks"""
        result = classifier.classify([])
        assert result['gesture'] == 'unknown'
        assert result['confidence'] == 0.0

    def test_calculate_confidence_perfect_match(self, classifier):
        """Test confidence calculation with perfect match"""
        finger_states = {'thumb': True, 'index': False}
        expected = {'thumb': True, 'index': False}
        confidence = classifier._calculate_confidence(finger_states, expected)
        assert confidence == 1.0

    def test_calculate_confidence_partial_match(self, classifier):
        """Test confidence calculation with partial match"""
        finger_states = {'thumb': True, 'index': True, 'middle': False}
        expected = {'thumb': True, 'index': False, 'middle': False}
        confidence = classifier._calculate_confidence(finger_states, expected)
        assert confidence == 2/3  # 2 out of 3 match

    def test_calculate_confidence_no_match(self, classifier):
        """Test confidence calculation with no match"""
        finger_states = {'thumb': True, 'index': True}
        expected = {'thumb': False, 'index': False}
        confidence = classifier._calculate_confidence(finger_states, expected)
        assert confidence == 0.0

    def test_classify_peace_gesture(self, classifier, peace_gesture_landmarks):
        """Test classification of peace gesture"""
        result = classifier.classify(peace_gesture_landmarks)
        assert result['gesture'] == 'peace'
        assert result['confidence'] >= 0.6
        assert result['hand'] == 'right'

    def test_classify_peace_left_hand(self, classifier, peace_gesture_landmarks):
        """Test peace gesture with left hand label"""
        result = classifier.classify(peace_gesture_landmarks, hand_label='left')
        assert result['gesture'] == 'peace'
        assert result['hand'] == 'left'

    def test_classify_thumbs_up_gesture(self, classifier, thumbs_up_landmarks):
        """Test classification of thumbs up gesture"""
        result = classifier.classify(thumbs_up_landmarks)
        assert result['gesture'] == 'thumbs_up'
        assert result['confidence'] >= 0.6

    def test_classify_fist_gesture(self, classifier, fist_landmarks):
        """Test classification of fist gesture"""
        result = classifier.classify(fist_landmarks)
        assert result['gesture'] == 'fist'
        assert result['confidence'] >= 0.6

    def test_classify_point_gesture(self, classifier, point_landmarks):
        """Test classification of point gesture"""
        result = classifier.classify(point_landmarks)
        assert result['gesture'] == 'point'
        assert result['confidence'] >= 0.6

    def test_classify_stop_gesture(self, classifier, stop_landmarks):
        """Test classification of stop (open palm) gesture"""
        result = classifier.classify(stop_landmarks)
        assert result['gesture'] == 'stop'
        assert result['confidence'] >= 0.6

    def test_classify_returns_dict_with_required_keys(self, classifier, peace_gesture_landmarks):
        """Test that classify returns dict with all required keys"""
        result = classifier.classify(peace_gesture_landmarks)
        assert 'gesture' in result
        assert 'confidence' in result
        assert 'hand' in result

    def test_classify_unknown_gesture_low_confidence(self, classifier, partial_gesture_landmarks):
        """Test that ambiguous gesture returns unknown due to low confidence"""
        result = classifier.classify(partial_gesture_landmarks)
        # This should be unknown since it's an ambiguous gesture
        assert result['gesture'] == 'unknown'
        assert result['confidence'] == 0.0

    def test_classify_extreme_landmark_values(self, classifier):
        """Test classification with extreme coordinate values"""
        # Create landmarks with very large/small values
        landmarks = [(1e6, 1e6, 1e6)] * 21
        result = classifier.classify(landmarks)
        # Should handle without crashing and return some result
        assert 'gesture' in result
        assert 'confidence' in result

    def test_classify_zero_landmarks(self, classifier):
        """Test classification with all zero landmarks"""
        landmarks = [(0, 0, 0)] * 21
        result = classifier.classify(landmarks)
        # Should handle without crashing
        assert 'gesture' in result
        assert 'confidence' in result

    def test_finger_states_all_extended(self, classifier, stop_landmarks):
        """Test finger states detection for fully extended hand"""
        states = classifier._get_finger_states(stop_landmarks)
        # All fingers should be extended for stop gesture
        assert states['thumb'] is True
        assert states['index'] is True
        assert states['middle'] is True
        assert states['ring'] is True
        assert states['pinky'] is True

    def test_finger_states_all_curled(self, classifier, fist_landmarks):
        """Test finger states detection for fully curled hand"""
        states = classifier._get_finger_states(fist_landmarks)
        # All fingers should be curled for fist gesture
        assert states['thumb'] is False
        assert states['index'] is False
