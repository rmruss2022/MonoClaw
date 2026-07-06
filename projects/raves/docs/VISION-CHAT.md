# SHOW GROUP CHATS — Vision & Implementation

## What Radiate Does (Research Summary)

Radiate (iOS/Android, founded 2015) is the closest comparable to what we're building. Key takeaways from their model:

**Per-event group chats**
- Every event has its own group chat that anyone who's marked "going" can join
- People discuss set times, meetups, after-parties, ticket exchanges, travel logistics
- Some festivals broadcast real-time alerts (emergencies, lost & found, weather)
- Posts can be pinned to a specific event or to a geographic location
- Chats tend to die after the event ends (this is a known Radiate limitation)

**Social matching**
- "Swipe" mechanic to match with people attending the same events
- Match based on music taste + past event overlap
- Hey mechanic (introduced Jan 2023) — light-weight wave/introduction to start conversations

**Safety gaps (from user feedback)**
- No ID/photo verification → scammers common
- Requires always-on location → privacy concerns
- No lasting community — chats vanish after events

## Groundfloor Implementation Plan

Steal what works from Radiate, skip what doesn't.

### Core: Per-Event Group Chats

**Data model:**
```
chat_threads
  id, event_id (FK), created_at, expires_at (event_date + 7 days)

chat_messages  
  id, thread_id (FK), user_id (FK), body, created_at

chat_members
  thread_id, user_id, joined_at, last_read_at
```

**Access rules:**
- Anyone with `interest='going'` on an event auto-joins the chat
- Maybe/skip users can browse but not post (read-only)
- Auth required for posting (need user account)
- Threads auto-archive 7 days after event_date (but stay viewable as read-only)

**UI: Event Chat tab**
- Inside ShowDetailModal, add a "CHAT" tab alongside the existing info
- Message list: chronological, author + timestamp + body
- Message input at bottom (sticky)
- Show attendee count: "47 going"
- Pinned messages section (admin/system messages at top)
- Typing indicator (nice to have)

### Matching Features (Phase 2)

- **Scene overlap** — show users who went to ≥2 of the same shows as you, with their profile
- **Hey/intro** — quick "I'm going to X" button that posts to thread
- **Find your people** — see who else is going before the event

### What We're NOT Doing (Yet)

- Swipe matching (not core to event discovery)
- Video/Spaces (way too much infra)
- Ticket marketplace
- Always-on location

### Phase 1 Scope (Build Now)

**Backend:**
1. SQLite tables: chat_threads, chat_messages, chat_members
2. Auto-create thread when an event is created (background)
3. Auto-join user to thread when interest set to 'going'
4. API endpoints:
   - GET /api/events/:id/chat (paginated messages + members)
   - POST /api/events/:id/chat (send message)
   - GET /api/events/:id/chat/members
   - POST /api/events/:id/chat/join (explicit join — for maybe users)
   - POST /api/events/:id/chat/leave
   - POST /api/events/:id/chat/pin (system/admin pin)
   - GET /api/chat/unread (count of unread across all threads)
5. Push notifications when new message arrives in your thread

**Frontend:**
1. ShowDetailModal: add CHAT tab (or expand inline chat section)
2. Message list with auto-scroll to bottom
3. Message input with send button
4. Attendee counter on event card: "💬 47" badge
5. Unread badge on tab/event when chat has new messages
6. Empty state: "Join the conversation" prompt

**Realtime:**
- Use polling every 5s for new messages (MVP — WebSocket later)
- Optimistic UI: message appears immediately, then syncs

### Phase 2 Scope (After MVP)

- Typing indicators
- Reactions to messages
- Reply threading
- Push notifications for new messages
- Scene overlap profiles
- Hey/intro mechanic

## Design System Compliance

- Background: #0C0C0C, Surface: #141414, Border: #2A2A2A
- Accent: #E8FF41 for own messages + unread indicators
- Incoming messages: #141414 background
- Text: #F0EEE9 (own), #F0EEE9 (incoming), #888 (timestamps)
- No avatars (just initial letters in small circles)
- 1px borders, no shadows, no rounded corners
- 12px message body, 10px timestamps with 0.1em tracking

## Architecture Decisions

1. **Single-user fallback**: When auth is disabled (current state), messages post as "You" — no user_id. Same tables, just null user_id.
2. **Thread auto-creation**: When an event gets upserted, check if thread exists, if not create it.
3. **Join on interest change**: When user sets interest='going', add them to chat_members.
4. **Archive policy**: Instead of deleting threads after event+7d, just set `archived=1` flag. Viewable read-only.
5. **Message length**: 500 char max.
6. **Rate limit**: 30 messages/min per user (or 60 for single-user mode).