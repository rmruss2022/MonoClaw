# Ora Health Development Plan
**Created:** February 7, 2026 22:32 EST  
**Subagent:** ora-health-dev-v2  
**Mission:** Build beautiful React Native UI matching Mediterranean sanctuary aesthetic

---

## Current State ✅

- ✅ Backend API running on localhost:4000 (fully functional)
- ✅ Frontend shell running on localhost:8081 (placeholder only)
- ✅ Design documentation complete (500+ lines)
- ✅ UI reference screenshot provided
- ✅ Color palette defined (Sage/Olive Greens, Warm Cream/Beige, Soft Taupe)
- ✅ 8 meditations seeded in database
- ✅ 5 community categories defined

## What Needs Building 🚧

### Phase 1: Foundation (30-45 min)
1. ✅ Review complete - understand architecture
2. ⏳ Create theme system matching UI reference colors
3. ⏳ Set up navigation structure (Tab Navigator)
4. ⏳ Build reusable component library (Card, Button, etc.)
5. ⏳ Connect API services

### Phase 2: Core Screens (2-3 hours)
6. ⏳ **Home Screen** - Hero with Mediterranean arch imagery
   - Daily affirmation card (Self Compassion theme)
   - Meditation CTA with circular image
   - Streak tracker (7-day calendar)
   - Quick action cards (Plan week, Workshops)

7. ⏳ **Meditation Screen** - Calm sanctuary feel
   - Featured meditation with circular image
   - Category filters (Breathwork, Sleep, Mindful, Guided)
   - Grid of meditation cards
   - Timer integration

8. ⏳ **Chat Screen** - Warm conversational interface
   - AI behavior indicator
   - Message history
   - Input with send button
   - Dynamic behavior system integration

9. ⏳ **Community Screen** - Soft, supportive space
   - Tab navigation (Feed, Inbox, Groups, Profile)
   - Post cards with category badges
   - Inbox with daily prompts
   - Create post modal

### Phase 3: Polish & Integration (1 hour)
10. ⏳ Smooth transitions and animations
11. ⏳ Loading states and error handling
12. ⏳ Image placeholders (use colors until real images)
13. ⏳ Test all flows end-to-end
14. ⏳ Accessibility improvements

---

## Design Specifications

### Color Palette (from UI Reference)
```typescript
colors: {
  // Primary Greens (Sage/Olive)
  sage: '#8B9A6B',
  oliveGreen: '#6B7B5A',
  
  // Backgrounds
  warmCream: '#F5F2EA',
  warmBeige: '#EDE9DF',
  
  // Surfaces
  softTaupe: '#D4C9B8',
  warmWhite: '#FEFEFE',
  
  // Accents
  mutedGold: '#C4A962',
  
  // Semantic
  text: '#2C2C2C',
  textSecondary: '#5C5C5C',
  textTertiary: '#8C8C8C',
}
```

### Typography
- **Family:** Humanist sans-serif (Inter or similar)
- **Heading:** 28-32px, bold, warm black
- **Body:** 16px, regular, charcoal
- **Caption:** 13-14px, medium, gray
- **Low contrast** for calming effect

### Key UI Elements from Reference
- **Hero Section:** Immersive nature photo (Mediterranean arch/courtyard)
- **Floating Cards:** Elevated with soft shadows, overlap for depth
- **Circular Images:** Meditation cards use rounded pill shapes
- **Badge System:** Category labels with muted colors
- **Streak Calendar:** Inline weekly view with purple indicators
- **Golden Accents:** "Week 5" pill badge, "XP 100" coins

### Component Patterns
- **Cards:** 16px border radius, 2-4px shadow, warm white bg
- **Buttons:** Rounded (24px), soft shadows, green accents
- **Badges:** Pill shape, category colors, 8px padding
- **Icons:** Organic emoji style (🧘, 📚, ✍️)

---

## Technical Approach

### Navigation Structure
```
TabNavigator (Bottom)
├── Home Tab 🏠
├── Meditate Tab 🧘
├── Chat Tab 💬
├── Community Tab 🤝
└── Profile Tab 👤
```

### API Endpoints (Already Working)
- GET `/meditations` - List all meditations
- GET `/community/categories` - Get 5 categories
- POST `/chat` - Send message, get AI response
- POST `/journal` - Create journal entry
- GET `/inbox` - Get daily messages

### File Structure
```
ora-health/
├── App.tsx                     # Main app entry
├── src/
│   ├── theme/
│   │   └── index.ts           # Design tokens
│   ├── components/
│   │   ├── Card.tsx           # Reusable card
│   │   ├── Button.tsx         # Button component
│   │   ├── Badge.tsx          # Category badge
│   │   └── Avatar.tsx         # User avatar
│   ├── navigation/
│   │   └── AppNavigator.tsx   # Tab navigation
│   ├── screens/
│   │   ├── HomeScreen.tsx
│   │   ├── MeditationScreen.tsx
│   │   ├── ChatScreen.tsx
│   │   └── CommunityScreen.tsx
│   └── services/
│       └── api.ts             # API client
```

---

## Implementation Priority

### Must-Have (Phase 1 + 2)
1. ✅ Theme system with reference colors
2. ✅ Navigation working
3. ✅ Home Screen with hero + daily card
4. ✅ Meditation Screen with seeded meditations
5. ✅ Basic chat interface
6. ✅ Community feed with categories

### Nice-to-Have (Phase 3)
7. Smooth animations (fade, slide)
8. Loading skeletons
9. Error boundaries
10. Offline indicators
11. Real images (vs color placeholders)

### Future Enhancements
12. Meditation timer with audio
13. Rich text journal editor
14. Photo uploads for posts
15. Push notifications
16. Sleep tracking

---

## Success Criteria

By end of session (4 hours):
- ✅ All 5 screens built and navigable
- ✅ Matches UI reference aesthetic (Mediterranean sanctuary)
- ✅ Connected to working backend
- ✅ Meditation list displays from API
- ✅ Community categories work
- ✅ Chat sends/receives messages
- ✅ Smooth, delightful UX
- ✅ No console errors
- ✅ Documented what was built

---

## Next Steps

**Immediate (Starting Now):**
1. Create theme/index.ts with reference colors
2. Build Card and Button components
3. Set up TabNavigator
4. Build HomeScreen with hero section
5. Wire up API services

**After Screens Built:**
- Test all flows manually
- Fix any layout issues
- Add loading states
- Polish animations
- Document changes

---

*Let's build something beautiful! 🦞*
