# ORA-033: Add envelope open animation for letter reading

## Context
Letters feature in Ora AI Community tab. Opening a letter should feel premium and delightful.

## Task
Create envelope open animation when user taps a letter card.

## Files to create/modify
- `src/components/EnvelopeCard.tsx` - Update to include animation
- `src/screens/LetterDetailScreen.tsx` - Trigger animation on open

## Implementation
1. Add animation to EnvelopeCard:
   - Use react-native-reanimated or Animated API
   - Flip/open transition (400ms)
   - Scale and fade effect
   - Option to add subtle sound via expo-av (paper rustle)

2. Trigger on tap:
   - User taps EnvelopeCard in list
   - Animation plays
   - Navigate to LetterDetailScreen after animation

## Acceptance
- Smooth 400ms open animation
- Feels premium and delightful
- No jank or performance issues

## Project paths
- App: /Users/matthew/Desktop/Feb26/ora-ai/
