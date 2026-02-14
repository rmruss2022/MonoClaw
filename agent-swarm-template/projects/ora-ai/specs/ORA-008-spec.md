# ORA-008: Add loading skeleton for home screen

## Context
Ora AI wellness app needs professional loading states. Users see blank screen while FocusCards load.

## Task
Create SkeletonCard component with animated shimmer effect.

## Files to create/modify
- `src/components/SkeletonCard.tsx` - New component
- `src/screens/HomeScreen.tsx` - Use skeleton while loading

## Implementation
1. Create SkeletonCard.tsx:
   - Match FocusCard dimensions (width: 90%, height: 180)
   - Use React Native Animated API for shimmer
   - Gray gradient pulse animation (1.5s loop)
   - Export default SkeletonCard

2. Update HomeScreen.tsx:
   - Import SkeletonCard
   - Show 5 SkeletonCards when `loading === true`
   - Replace with FocusCards when data arrives

## Acceptance
- Loading state shows 5 animated skeleton cards
- Shimmer animation is smooth and professional
- Transitions seamlessly to real cards

## Project paths
- App: /Users/matthew/Desktop/Feb26/ora-ai/
