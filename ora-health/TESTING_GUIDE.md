# Ora Health - Testing Guide 🧪

**For:** Matthew  
**Date:** February 7, 2026  
**App Status:** ✅ Built & Ready to Test

---

## Quick Start

### 1. Verify Backend is Running ✅
```bash
curl http://localhost:4000/health
# Expected: {"status":"ok","timestamp":"..."}
```

### 2. Check Frontend is Running ✅
```bash
# Should already be running on:
open http://localhost:8081
```

### 3. Open in Expo
```bash
cd /Users/matthew/.openclaw/workspace/ora-health/ora-health

# If not already running:
npx expo start

# Then press:
# 'i' for iOS Simulator
# 'a' for Android Emulator
# or scan QR code with Expo Go app
```

---

## What to Test

### 🏠 Home Screen

**Expected Visuals:**
- Hero section with Mediterranean arch image
- "Hi Matt" greeting with "Week 5" golden badge
- Two stat badges: 🔥 7 and 🏆 20
- Large "Self Compassion" card:
  - 🤲 icon
  - "Day 3/7" progress
  - "Today's Affirmation" badge
  - "I am kind to myself" heading
  - Subtitle text about compassion
- Meditation CTA card:
  - Circular image placeholder with 🧘‍♀️
  - "Meditation for today" badge
  - "XP 100" badge
- Two quick action cards:
  - "Plan your week" with 📔
  - "Workshops" with 🎯
- Streak card:
  - "7 days streak" heading
  - "Way to go Matt" subtitle
  - Weekly calendar with 3 purple circles (Mon/Tue/Wed)
  - "View history" link

**Test Actions:**
1. Scroll up and down - should be smooth
2. Tap "Meditation for today" - should navigate to Meditate tab
3. Check all text is readable (not too light)
4. Verify spacing feels generous, not cramped

---

### 🧘 Meditation Screen

**Expected Visuals:**
- "Find Calm" heading
- "Take a moment to center yourself" subtitle
- Featured meditation card:
  - "Today's Practice" green badge
  - Large circular emoji (🌅, 🌙, or 🌬️)
  - Title (e.g., "Morning Presence")
  - Description text
  - Duration (e.g., "8 min")
  - Category badge
  - "Begin Practice" button
- Horizontal category filter:
  - All ✨
  - Breathe 🌬️
  - Guided 🎧
  - Mindful 🧘
  - Sleep 🌙
- Grid of meditation cards (8 total):
  - Color background with emoji
  - Title and description
  - Duration
  - Play button (➤)

**Test Actions:**
1. Check that 8 meditations load from API
2. Tap category filters - cards should filter
3. Tap "All" - should show all 8 again
4. Scroll through meditation cards
5. Tap play button (won't do anything yet - timer not built)

**API Test:**
```bash
# Verify meditations are loading
curl http://localhost:4000/meditations | jq '.meditations | length'
# Should return: 8
```

---

### 💬 Chat Screen

**Expected Visuals:**
- "Your Space" heading
- Empty state initially:
  - 💜 large emoji
  - "I'm here to listen and support you" heading
  - "Share what's on your mind..." subtitle
  - 4 suggested prompts in pill buttons:
    - "How can I manage stress better?"
    - "I'm feeling overwhelmed today"
    - "Help me practice gratitude"
    - "I want to work on my goals"
- Input box at bottom:
  - "Share what's on your mind..." placeholder
  - Send button (↑) in green circle

**Test Actions:**
1. Tap a suggested prompt - should send message
2. Wait for AI response (may take 2-5 seconds)
3. Check AI response appears in white bubble (left aligned)
4. Check your message appears in green bubble (right aligned)
5. Look for behavior badge (e.g., "Gratitude Practice")
6. Type your own message and send
7. Verify keyboard pushes content up (doesn't cover input)

**What to Look For:**
- User messages: right side, green background, white text
- AI messages: left side, white background, dark text
- Small green dot + behavior name appears under "Your Space" header
- Loading spinner shows while AI is thinking

**API Test:**
```bash
# Send test message
curl -X POST http://localhost:4000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I feel stressed today"}' | jq
# Should return: {"response":"...", "behavior":"..."}
```

---

### 🤝 Community Screen

**Expected Visuals:**
- "Community" heading
- "Share your journey, support others" subtitle
- 4 tabs below header:
  - Feed (active by default)
  - Inbox
  - Groups  
  - Profile
- Weekly prompt banner (golden yellow):
  - "Weekly Prompt" badge
  - "What's one small win you experienced this week?"
  - "Share Your Story" button
- Category filters (horizontal scroll):
  - All
  - 🎯 Progress
  - 💭 Prompts
  - 📚 Resources
  - 🤝 Support
  - 💛 Gratitude
- Empty state (if no posts):
  - 🌱 emoji
  - "No posts yet"
  - "Be the first to share your story"
- Floating + button (bottom right, green circle)

**Test Actions:**
1. Check 5 categories load from API
2. Tap category filters - should highlight when active
3. Pull down to refresh (should show spinner briefly)
4. Tap other tabs (Inbox, Groups, Profile) - shows "Coming Soon"
5. Tap floating + button (won't open modal yet - not built)

**API Test:**
```bash
# Verify categories loading
curl http://localhost:4000/community/categories | jq '.categories | length'
# Should return: 5
```

**If Posts Exist:**
- Each post card should show:
  - Avatar (emoji or ?)
  - Username or "Anonymous"
  - Date
  - Category badge with icon
  - Post content text
  - Like/comment/bookmark buttons at bottom

---

## Navigation Testing

### Bottom Tab Bar

**Expected:**
- 4 tabs visible at bottom
- White background
- Icons: 🏠 Meditate 🧘 Chat 💬 Community 🤝
- Active tab has:
  - Larger icon (28px vs 24px)
  - Sage green color (#8B9A6B)
  - Label below icon
- Inactive tabs are lighter gray
- Tab bar height: ~80px with padding

**Test Actions:**
1. Tap each tab - screen should change
2. Note transition (should be instant)
3. Active tab icon should grow slightly
4. All 4 screens should load without errors

---

## Visual Design Checklist

### ✅ Color Palette
- [ ] Background is warm cream (#F5F2EA) not gray
- [ ] Cards are warm white (#FEFEFE) not pure white
- [ ] Green accents are sage (#8B9A6B) not bright green
- [ ] Text is charcoal (#2C2C2C) not black
- [ ] Secondary text is gray but readable

### ✅ Typography
- [ ] Headings are bold and prominent (28-32px)
- [ ] Body text is 16px and comfortable to read
- [ ] Line height is generous (1.5-1.7)
- [ ] Font weight appropriate for hierarchy

### ✅ Spacing
- [ ] Padding inside cards feels generous (16px)
- [ ] Gap between cards is consistent (16px)
- [ ] No cramped or claustrophobic areas
- [ ] White space is intentional

### ✅ Components
- [ ] Cards have soft shadows (barely noticeable)
- [ ] Corners are rounded (16px on cards, 24px on buttons)
- [ ] Buttons have hover/press states
- [ ] Loading spinners are sage green

### ✅ Overall Feel
- [ ] Calm and soothing (not sterile)
- [ ] Warm and inviting (not cold)
- [ ] Premium quality (not cheap)
- [ ] Organic and human (not clinical)

---

## Performance Checks

### Load Times
- [ ] Home screen renders instantly
- [ ] Meditation screen loads 8 items in <500ms
- [ ] Chat sends message in <3 seconds
- [ ] Community categories load in <500ms
- [ ] Tab switching is instant (<100ms)

### Smooth Scrolling
- [ ] Home screen scrolls smoothly (no jank)
- [ ] Meditation grid scrolls smoothly
- [ ] Chat messages scroll without lag
- [ ] Community feed scrolls smoothly
- [ ] Horizontal category scrolls are smooth

### Memory/CPU
- [ ] App doesn't lag after 5 minutes of use
- [ ] No warning messages in Expo console
- [ ] Device doesn't heat up excessively

---

## Common Issues & Fixes

### Issue: "Cannot connect to Metro bundler"
**Fix:**
```bash
cd ora-health
npx expo start --clear
```

### Issue: "Network request failed" on API calls
**Fix:**
1. Check backend is running: `curl http://localhost:4000/health`
2. If iOS simulator, localhost should work
3. If physical device, use computer's IP address in `src/services/api.ts`:
   ```typescript
   const API_BASE_URL = 'http://192.168.1.xxx:4000';
   ```

### Issue: TypeScript errors in console
**Fix:**
```bash
cd ora-health
npx tsc --noEmit
# Should show no errors
```

### Issue: Blank white screen
**Fix:**
1. Check Expo console for errors
2. Verify `App.tsx` is importing `AppNavigator`
3. Try: `npx expo start --clear`

### Issue: Images not loading
**Expected:** 
- Hero image uses Unsplash URL (requires internet)
- Meditation cards show emoji placeholders (should work offline)
- If images fail, check internet connection

---

## Backend API Quick Reference

### Health Check
```bash
curl http://localhost:4000/health
```

### Meditations (8 items)
```bash
curl http://localhost:4000/meditations | jq
```

### Categories (5 items)
```bash
curl http://localhost:4000/community/categories | jq
```

### Send Chat Message
```bash
curl -X POST http://localhost:4000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!"}' | jq
```

### Create Journal Entry
```bash
curl -X POST http://localhost:4000/journal \
  -H "Content-Type: application/json" \
  -d '{"content":"Today was great!","mood":"happy"}' | jq
```

---

## Success Criteria

### Must Work ✅
- [x] All 4 screens render without errors
- [x] Tab navigation works
- [x] Meditations load from API (8 items)
- [x] Categories load from API (5 items)
- [x] Chat sends message and receives response
- [x] Colors match UI reference (warm, muted palette)
- [x] Typography is readable and hierarchical
- [x] Spacing feels generous

### Nice to Have 🎯
- [ ] Images load (requires internet for Unsplash)
- [ ] Smooth animations on transitions
- [ ] Loading states look polished
- [ ] Empty states are friendly and helpful

### Future Features 🚀
- [ ] Meditation timer actually works
- [ ] Post creation modal
- [ ] Journal screen
- [ ] Profile tab populated
- [ ] Real user images
- [ ] Push notifications

---

## Reporting Issues

If you find bugs or have feedback, note:

1. **Which screen?** (Home, Meditate, Chat, Community)
2. **What happened?** (describe the issue)
3. **What did you expect?** (expected behavior)
4. **Console errors?** (check Expo dev tools)
5. **Screenshot?** (if visual issue)

---

## Next Steps After Testing

### If Everything Works 🎉
1. Start adding real content:
   - Replace Unsplash URL with curated image
   - Seed posts in community
   - Add more meditations
   - Customize welcome message

2. Build additional features:
   - Meditation timer interface
   - Post creation modal
   - Journal entry screen
   - Profile settings

3. Polish and refine:
   - Add subtle animations
   - Improve loading states
   - Add error boundaries
   - Implement data persistence

### If Issues Found 🐛
1. Document the issue
2. Check console for errors
3. Verify backend is running
4. Try clearing cache: `npx expo start --clear`
5. Check `BUILD_COMPLETE.md` for known limitations

---

## File Locations

**Screens:** `src/screens/`
- HomeScreen.tsx
- MeditationScreen.tsx
- ChatScreen.tsx
- CommunityScreen.tsx

**Components:** `src/components/`
- Card.tsx
- Button.tsx
- Badge.tsx

**Services:** `src/services/`
- api.ts

**Theme:** `src/theme/`
- index.ts

**Navigation:** `src/navigation/`
- AppNavigator.tsx

**Entry:** `App.tsx`

---

## Support

Built by: **ora-health-dev-v2** subagent  
Session: **February 7, 2026**  
Documentation:
- `BUILD_COMPLETE.md` - Full build report
- `DEVELOPMENT_PLAN.md` - Original plan
- `STATUS_REPORT.md` - Pre-build status

---

**Happy Testing! 🦞✨**

*The app is ready to test. Everything should work smoothly. Enjoy exploring your new wellness platform!*
