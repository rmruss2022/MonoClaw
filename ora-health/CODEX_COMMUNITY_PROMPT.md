# Task: Redesign Community Screen — Unified Single-Tab Layout with Letters, Posts, Post Detail & Compose

## Project

**Ora Health** — React Native (Expo) wellness app  
**Repo root:** `/Users/matthew/.openclaw/workspace/ora-health/ora-health`  
**Theme file:** `src/theme/index.ts` (Mediterranean Sanctuary aesthetic — sage greens, warm cream, muted gold)  
**API service:** `src/services/api.ts` (base URL `http://localhost:4000`)  

## Current State

`src/screens/CommunityScreen.tsx` currently has 4 tabs: **Feed, Inbox, Groups, Profile**. The Inbox, Groups, and Profile tabs are unimplemented placeholders. The Feed tab has a weekly prompt banner, horizontal category filter chips, and post cards with like/comment/bookmark actions. Posts are not tappable — there's no detail view, no replies, no compose flow.

The API service (`src/services/api.ts`) currently has:
- `communityAPI.getCategories()` → `Category[]` (id, name, description, icon, color, displayOrder)
- `communityAPI.getPosts(categoryId?)` → `Post[]` (id, userId, content, categoryId, isAnonymous, likes, comments, createdAt)
- `communityAPI.createPost(content, categoryId, isAnonymous)` → `Post`
- `inboxAPI.getMessages()` → messages array
- `inboxAPI.getUnreadCount()` → count

## What I Want

**Remove the separate tabs entirely.** Everything lives in ONE scrollable screen with these sections from top to bottom:

### 1. Letters Section (top)
Letters are curated messages from Ora to the community — think "letters from your therapist" or motivational notes. Display them as elegant, distinct cards near the top of the screen (above the regular posts feed). They should feel special and separate from user posts — maybe a slightly different card style (soft gold border or subtle background tint using `mutedGold`).

- Show the 2-3 most recent letters in a horizontal scroll or stacked cards
- Each letter card: title, preview snippet (2-3 lines), date, "Read More" tap target
- Tapping opens a full-screen letter detail view (modal or push navigation)

### 2. Weekly Prompt Banner
Keep the existing weekly prompt banner but move it right below the letters. Same golden styling.

### 3. Category Filters
Keep the existing horizontal scrolling category chips. Same behavior — filters the posts below.

### 4. Posts Feed (main content)
Same post cards as now BUT:
- **Tappable** — tapping a post opens a **Post Detail Screen**
- Post Detail Screen shows:
  - Full post content
  - Author info
  - Like/comment counts
  - **All replies/comments** listed below
  - **Reply input** at the bottom (text input + send button)
  - Back navigation to return to community feed

### 5. Compose Section (bottom area)
Below the posts feed (or accessible via the FAB), show:
- **"Write a Post"** — opens compose flow (text input, category picker, anonymous toggle, submit)
- **"Write a Letter"** (if user has permission / future feature) — same idea but for letters
- **"Your History"** — collapsible section showing the user's own past posts and letters

### 6. Your History Section
At the bottom of the scroll, a section showing:
- "Your Posts" — list of the current user's posts (compact cards)
- Tappable to go to post detail
- "See All" link if there are many

## API Changes Needed

Update `src/services/api.ts` to add these new endpoints:

```typescript
// Add to communityAPI:
async getLetters(): Promise<Letter[]>
async getLetter(id: string): Promise<Letter>
async getPostDetail(id: string): Promise<PostDetail>
async getPostComments(postId: string): Promise<Comment[]>
async createComment(postId: string, content: string): Promise<Comment>
async likePost(postId: string): Promise<void>
async getUserPosts(): Promise<Post[]>

// New types:
interface Letter {
  id: string;
  title: string;
  content: string;        // full letter body
  author: string;         // e.g. "Ora Team" or "Dr. Sarah"
  excerpt: string;        // preview text
  createdAt: string;
  readCount: number;
  icon?: string;          // optional emoji
}

interface PostDetail extends Post {
  commentsData: Comment[];
}

interface Comment {
  id: string;
  postId: string;
  userId: string;
  content: string;
  isAnonymous: boolean;
  likes: number;
  createdAt: string;
}
```

**Important:** The API server may not have these endpoints yet. That's fine — implement the frontend with proper fetch calls to the expected endpoints, and include mock/fallback data so the UI renders even if the server returns 404. Use try/catch with sensible defaults.

## Navigation

The app uses `@react-navigation`. You may need to:
- Add a `PostDetailScreen.tsx` in `src/screens/`
- Add a `LetterDetailScreen.tsx` in `src/screens/`  
- Update the navigation setup (check `src/navigation/TabNavigator.tsx`) to include stack navigation within the Community tab so we can push to PostDetail/LetterDetail and come back

If the navigation setup is a simple tab navigator, wrap the Community tab in a **stack navigator** so we get push/pop behavior for detail screens.

## Design Rules

- **Use the existing theme** (`src/theme/index.ts`) for ALL colors, spacing, typography, shadows
- **Mediterranean Sanctuary aesthetic** — warm cream backgrounds, sage green accents, muted gold highlights, soft taupe borders
- Letters should feel elevated/special — use `mutedGold` accent color, slightly different card styling
- Post cards use `Card` component from `src/components/Card.tsx`
- Badge component at `src/components/Badge.tsx`
- Keep the floating action button (FAB) for quick compose
- All touch targets should have `activeOpacity={0.7}` or similar feedback
- Use `SafeAreaView` from `react-native-safe-area-context`
- Loading states: `ActivityIndicator` with `theme.colors.sage`
- Empty states: emoji + text (existing pattern)

## File Changes Expected

1. **`src/screens/CommunityScreen.tsx`** — Complete rewrite (single unified layout, no tabs)
2. **`src/screens/PostDetailScreen.tsx`** — New file (post detail + comments + reply)
3. **`src/screens/LetterDetailScreen.tsx`** — New file (full letter view)
4. **`src/services/api.ts`** — Add new types + API methods with mock fallbacks
5. **`src/navigation/TabNavigator.tsx`** — Add stack navigator for Community tab

## Mock Data

Include realistic mock/fallback data for development:

```typescript
const MOCK_LETTERS: Letter[] = [
  {
    id: 'letter-1',
    title: 'A Note on Being Gentle With Yourself',
    content: 'Dear community,\n\nThis week I want to talk about the art of self-compassion...',
    author: 'Ora Team',
    excerpt: 'This week I want to talk about the art of self-compassion and why it matters more than you think.',
    createdAt: new Date().toISOString(),
    readCount: 342,
    icon: '💌',
  },
  {
    id: 'letter-2',
    title: 'Finding Peace in Uncertainty',
    content: 'Dear friends,\n\nUncertainty is one of the hardest things...',
    author: 'Dr. Sarah Chen',
    excerpt: 'Uncertainty is one of the hardest things we face. Here are three practices that help.',
    createdAt: new Date(Date.now() - 86400000 * 3).toISOString(),
    readCount: 518,
    icon: '🌿',
  },
];

const MOCK_COMMENTS: Comment[] = [
  {
    id: 'comment-1',
    postId: 'post-1',
    userId: 'user-2',
    content: 'Thank you for sharing this. I needed to hear it today.',
    isAnonymous: false,
    likes: 5,
    createdAt: new Date().toISOString(),
  },
];
```

## What NOT to Change

- Don't touch `HomeScreen.tsx`, `MeditationScreen.tsx`, or `ChatScreen.tsx`
- Don't change the theme file
- Don't change the existing `Card`, `Badge`, or `Button` components
- Don't remove any existing API methods — only add new ones

## Summary

Transform the Community screen from a multi-tab layout with placeholder tabs into a **single, unified, scrollable experience** with:
1. **Letters** at the top (special styling)
2. **Weekly prompt** below that
3. **Category filters** (horizontal chips)
4. **Posts feed** (tappable → detail screen with comments/replies)
5. **Your history** section at bottom
6. **Compose** via FAB (post) or dedicated section
7. **Post Detail Screen** with full comments and reply input
8. **Letter Detail Screen** for reading full letters

Keep the existing Mediterranean Sanctuary aesthetic. Use mock data as fallbacks. Make it feel like a warm, supportive community space.
