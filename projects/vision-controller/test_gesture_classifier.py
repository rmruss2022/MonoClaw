"""
Test script for gesture classifier with webcam
"""

import cv2
import mediapipe as mp
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from ml.gesture_classifier import GestureClassifier

def main():
    # Initialize MediaPipe Hands
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    # Initialize classifier
    classifier = GestureClassifier()
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    
    print("Gesture Classifier Test - Press 'q' to quit")
    print("Supported gestures: peace ✌️, thumbs_up 👍, fist ✊, point 👉, stop ✋")
    
    while cap.isOpened():
        success, image = cap.read()
        if not success:
            continue
        
        # Flip image for selfie view
        image = cv2.flip(image, 1)
        
        # Convert to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Process image
        results = hands.process(image_rgb)
        
        # Draw landmarks and classify gestures
        if results.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                # Draw landmarks
                mp_drawing.draw_landmarks(
                    image, 
                    hand_landmarks, 
                    mp_hands.HAND_CONNECTIONS
                )
                
                # Extract landmarks as list of tuples
                landmarks = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
                
                # Get hand label
                hand_label = "right"
                if results.multi_handedness:
                    hand_label = results.multi_handedness[idx].classification[0].label.lower()
                
                # Classify gesture
                result = classifier.classify(landmarks, hand_label)
                
                # Display result
                gesture = result['gesture']
                confidence = result['confidence']
                hand = result['hand']
                
                # Draw text with gesture name and confidence
                text = f"{hand.upper()}: {gesture} ({confidence:.0%})"
                y_pos = 30 + (idx * 30)
                
                # Color based on confidence
                if confidence > 0.8:
                    color = (0, 255, 0)  # Green
                elif confidence > 0.6:
                    color = (0, 255, 255)  # Yellow
                else:
                    color = (0, 0, 255)  # Red
                
                cv2.putText(
                    image, 
                    text, 
                    (10, y_pos), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, 
                    color, 
                    2
                )
        
        # Show FPS
        cv2.putText(
            image,
            "Press 'q' to quit",
            (10, image.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1
        )
        
        # Display image
        cv2.imshow('Gesture Recognition Test', image)
        
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    hands.close()

if __name__ == "__main__":
    main()
