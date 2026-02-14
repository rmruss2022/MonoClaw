# ORA-026: Design letters system data model and API

**Priority:** Critical (P0)
**Type:** Backend Development (Design)
**Estimated:** 4 hours
**Dependencies:** None
**Tags:** backend, database, API, letters

## 🎯 Objective

Design the PostgreSQL schema and REST API for the "Letters" feature - a thoughtful, asynchronous messaging system where users can send and receive encouraging letters from their AI wellness companion.

## 📋 Background

The Letters feature is a core differentiator for Ora AI:
- Users receive periodic "letters" from their AI companion (like handwritten notes)
- Letters are personal, thoughtful, and reference past conversations
- Users can read, reply, and create conversation threads
- Aesthetic is warm and personal (think handwritten letters, not chat bubbles)

**References:**
- Product spec: `/Users/matthew/.openclaw/workspace/agent-swarm-template/PRODUCT_SPEC.md`
- Inspiration: Slowly app, Bottled app

## 🗄️ Database Schema

### 1. `letters` Table

```sql
CREATE TABLE letters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Participants
    sender_id UUID NOT NULL,              -- User or 'system' (AI companion)
    sender_type VARCHAR(20) NOT NULL,     -- 'user' or 'ai'
    recipient_id UUID NOT NULL,           -- Always a user
    
    -- Content
    subject VARCHAR(200) NOT NULL,        -- Letter subject/title
    body TEXT NOT NULL,                   -- Full letter content (markdown supported)
    tone VARCHAR(50),                     -- 'encouraging', 'reflective', 'celebratory', etc.
    
    -- Thread management
    thread_id UUID,                       -- NULL for new threads
    replied_to_id UUID,                   -- NULL for first letter in thread
    
    -- Metadata
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    read_at TIMESTAMP,                    -- NULL = unread
    favorited BOOLEAN DEFAULT FALSE,      -- User can favorite letters
    
    -- AI generation context (for AI-sent letters)
    generation_context JSONB,             -- Stores prompts, triggers, insights used
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY (replied_to_id) REFERENCES letters(id) ON DELETE SET NULL,
    CHECK (sender_type IN ('user', 'ai'))
);

-- Indexes
CREATE INDEX idx_letters_recipient ON letters(recipient_id, sent_at DESC);
CREATE INDEX idx_letters_thread ON letters(thread_id, sent_at ASC);
CREATE INDEX idx_letters_unread ON letters(recipient_id, read_at) WHERE read_at IS NULL;
CREATE INDEX idx_letters_favorited ON letters(recipient_id, favorited) WHERE favorited = TRUE;
```

**Field Notes:**
- `sender_id`: For AI letters, use special UUID (e.g., `00000000-0000-0000-0000-000000000001`)
- `body`: Supports markdown for formatting (bold, italics, line breaks)
- `generation_context`: For AI letters, stores:
  ```json
  {
    "trigger": "user_milestone",
    "insights_referenced": ["insight_id_1", "insight_id_2"],
    "conversation_ids": ["conv_123"],
    "tone_seed": "encouraging"
  }
  ```

### 2. `letter_threads` Table

```sql
CREATE TABLE letter_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Participants (always user + AI for now)
    user_id UUID NOT NULL,
    
    -- Metadata
    title VARCHAR(200),                   -- First letter's subject
    letter_count INTEGER DEFAULT 0,       -- Denormalized count
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP,            -- Last letter sent in thread
    
    -- State
    archived BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_threads_user ON letter_threads(user_id, last_message_at DESC);
CREATE INDEX idx_threads_active ON letter_threads(user_id, archived) WHERE archived = FALSE;
```

### 3. `letter_templates` Table (For AI letter generation)

```sql
CREATE TABLE letter_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Template metadata
    name VARCHAR(100) NOT NULL,           -- 'weekly_check_in', 'milestone_celebration', etc.
    category VARCHAR(50) NOT NULL,        -- 'check_in', 'milestone', 'encouragement', 'reflection'
    
    -- Content template
    subject_template TEXT NOT NULL,       -- "Reflecting on your week"
    body_template TEXT NOT NULL,          -- Markdown with {{placeholders}}
    tone VARCHAR(50) NOT NULL,
    
    -- Trigger conditions
    trigger_conditions JSONB,             -- When to send this template
    
    -- Usage tracking
    times_used INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index
CREATE INDEX idx_templates_category ON letter_templates(category);
```

**Template Example:**
```json
{
  "subject_template": "Your progress this week ✨",
  "body_template": "Hi {{user_name}},\n\nI've been reflecting on our conversations this week...\n\n{{weekly_insights}}\n\nKeep going! 🌱",
  "trigger_conditions": {
    "frequency": "weekly",
    "day_of_week": "sunday",
    "requires_activity": true
  }
}
```

## 🔌 REST API Endpoints

### Base URL
`/api/v1/letters`

### 1. **GET /letters/inbox**
Get user's inbox (all received letters)

**Query Params:**
- `page` (int, default: 1)
- `limit` (int, default: 20, max: 100)
- `unread_only` (boolean, default: false)
- `favorited_only` (boolean, default: false)

**Response:**
```json
{
  "letters": [
    {
      "id": "letter_uuid",
      "sender_type": "ai",
      "subject": "Your week in reflection",
      "preview": "Hi Sarah, I've been thinking about...",
      "sent_at": "2026-02-13T20:00:00Z",
      "read_at": null,
      "favorited": false,
      "thread_id": "thread_uuid",
      "reply_count": 2
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 47,
    "has_more": true
  },
  "unread_count": 3
}
```

### 2. **GET /letters/:id**
Get full letter content

**Response:**
```json
{
  "id": "letter_uuid",
  "sender_type": "ai",
  "subject": "Your week in reflection",
  "body": "Hi Sarah,\n\nI've been thinking about our conversations this week...",
  "tone": "reflective",
  "sent_at": "2026-02-13T20:00:00Z",
  "read_at": null,
  "favorited": false,
  "thread_id": "thread_uuid",
  "replied_to": null,
  "generation_context": { /* ... */ }
}
```

### 3. **POST /letters**
Send a letter (user replying to AI)

**Request:**
```json
{
  "subject": "Re: Your week in reflection",
  "body": "Thank you for the encouraging words...",
  "replied_to_id": "previous_letter_uuid",
  "thread_id": "thread_uuid"
}
```

**Response:**
```json
{
  "letter": { /* full letter object */ },
  "thread_updated": true
}
```

### 4. **POST /letters/:id/reply**
Reply to a specific letter (convenience endpoint)

**Request:**
```json
{
  "body": "Thank you! This really helped..."
}
```

**Response:** Same as POST /letters

### 5. **PATCH /letters/:id/read**
Mark letter as read

**Response:**
```json
{
  "id": "letter_uuid",
  "read_at": "2026-02-13T21:15:00Z"
}
```

### 6. **PATCH /letters/:id/favorite**
Toggle favorite status

**Request:**
```json
{
  "favorited": true
}
```

**Response:**
```json
{
  "id": "letter_uuid",
  "favorited": true
}
```

### 7. **GET /letters/threads**
Get all letter threads for user

**Response:**
```json
{
  "threads": [
    {
      "id": "thread_uuid",
      "title": "Your week in reflection",
      "letter_count": 5,
      "last_message_at": "2026-02-13T20:00:00Z",
      "unread_count": 1,
      "latest_letter_preview": "Hi Sarah, I've been..."
    }
  ]
}
```

### 8. **GET /letters/threads/:id**
Get all letters in a thread

**Response:**
```json
{
  "thread": {
    "id": "thread_uuid",
    "title": "Your week in reflection",
    "letter_count": 5,
    "created_at": "2026-02-01T10:00:00Z"
  },
  "letters": [
    { /* letter 1 */ },
    { /* letter 2 */ },
    { /* letter 3 */ }
  ]
}
```

## 🔒 Authorization

All endpoints require authentication:
- `Authorization: Bearer <jwt_token>`
- User can only access their own letters
- Admin users can access all letters (for support)

## 🧪 Testing Criteria

### Database Tests
1. **Constraints:** Test sender_type CHECK constraint
2. **Foreign Keys:** Test thread_id and replied_to_id relationships
3. **Indexes:** Verify all indexes exist with EXPLAIN queries
4. **Thread integrity:** Ensure thread_id consistency across replies

### API Tests
1. **Inbox pagination:** Test with 100+ letters
2. **Unread filter:** Verify unread_only works correctly
3. **Mark as read:** Test read_at timestamp updates
4. **Reply flow:** Create thread, send reply, verify thread_id
5. **Unauthorized access:** Test accessing another user's letters (should fail)
6. **Invalid IDs:** Test with non-existent letter/thread IDs

## 📁 Migration Script

Create: `migrations/2026-02-13-letters-schema.sql`

Should include:
- All CREATE TABLE statements
- All indexes
- Helper functions (if any)
- Rollback script (DROP statements)
- Test data insertion (optional, for development)

## ✅ Acceptance Criteria

- [ ] All 3 tables created with proper relationships
- [ ] Indexes created for common queries (inbox, threads, unread)
- [ ] All 8 API endpoints defined with request/response schemas
- [ ] Migration script is complete and tested
- [ ] API spec documented (OpenAPI/Swagger optional but nice)
- [ ] Authorization logic specified
- [ ] Test plan written
- [ ] Database supports thread conversation chains
- [ ] Design can scale to 10k+ letters per user

## 🚀 Next Steps After Completion

This unblocks:
- ORA-027: Implement letters API endpoints
- ORA-028: Design letter UI/UX flow (parallel work)
- ORA-029: Build AI letter generation service
- ORA-030: Create letter scheduling system

## 🎯 Agent Type Required

**Backend-Dev Agent** with:
- PostgreSQL schema design expertise
- REST API design experience
- Understanding of data relationships and normalization
- Experience with messaging/thread systems
