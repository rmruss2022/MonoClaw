# ORA-045: Implement post categories with visual badges

## Context
Community posts need visual organization and filtering.

## Task
Add 6 category types with colored badges and icons.

## Categories
1. **Reflection** - Purple 🪷
2. **Growth** - Green 🌱
3. **Wellness** - Teal 🧘
4. **Gratitude** - Blue 🙏
5. **Support** - Pink 💗
6. **Question** - Orange ❓

## Backend
Files: /Users/matthew/Desktop/Feb26/ora-ai-api/

1. Add category enum to Post model
2. Update API to accept/return category
3. Add filter endpoint: GET /posts?category=reflection

## Frontend
Files: /Users/matthew/Desktop/Feb26/ora-ai/

1. Create `CategoryBadge.tsx` component:
   - Colored chip with icon + label
   - Colors: map category to hex codes

2. Update `CreatePostScreen.tsx`:
   - Category picker (dropdown or chips)
   - Required field

3. Update `PostCard.tsx`:
   - Show CategoryBadge at top

4. Add filter UI to feed screen:
   - Horizontal scrollable category chips
   - Tap to filter

## Acceptance
- 6 categories with distinct visual styles
- Posts can be filtered by category
- Category shown on all posts

## Projects
- App: /Users/matthew/Desktop/Feb26/ora-ai/
- Backend: /Users/matthew/Desktop/Feb26/ora-ai-api/
