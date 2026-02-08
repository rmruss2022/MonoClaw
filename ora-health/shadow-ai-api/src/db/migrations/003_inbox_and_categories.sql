-- Migration 003: Inbox and Categories System
-- Adds inbox messaging system, post categories, and category support to posts

-- ==========================================
-- 1. POST CATEGORIES TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS post_categories (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  icon VARCHAR(10),
  color VARCHAR(7),
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed category data
INSERT INTO post_categories (id, name, description, icon, color, display_order) VALUES
  ('progress', 'Progress', 'Share wins and milestones', '🎯', '#8B9A7E', 1),
  ('prompt', 'Prompts', 'Respond to daily prompts', '💭', '#C47D5F', 2),
  ('resource', 'Resources', 'Share helpful tools and content', '📚', '#9B7AB8', 3),
  ('support', 'Support', 'Ask for and offer support', '🤝', '#D4A574', 4),
  ('gratitude', 'Gratitude', 'Express appreciation', '💛', '#F0C869', 5)
ON CONFLICT (id) DO NOTHING;

-- ==========================================
-- 2. INBOX MESSAGES TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS inbox_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message_type VARCHAR(50) NOT NULL,
  subject VARCHAR(255),
  content TEXT NOT NULL,
  metadata JSONB,
  is_read BOOLEAN DEFAULT FALSE,
  is_archived BOOLEAN DEFAULT FALSE,
  read_at TIMESTAMP,
  archived_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for inbox messages
CREATE INDEX IF NOT EXISTS idx_inbox_user_unread ON inbox_messages(user_id, is_read, is_archived);
CREATE INDEX IF NOT EXISTS idx_inbox_created ON inbox_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbox_message_type ON inbox_messages(message_type);

-- ==========================================
-- 3. INBOX MESSAGE RESPONSES TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS inbox_message_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID NOT NULL REFERENCES inbox_messages(id) ON DELETE CASCADE,
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  response_text TEXT NOT NULL,
  created_post_id UUID REFERENCES community_posts(id) ON DELETE SET NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for responses
CREATE INDEX IF NOT EXISTS idx_inbox_responses_message ON inbox_message_responses(message_id);
CREATE INDEX IF NOT EXISTS idx_inbox_responses_user ON inbox_message_responses(user_id);

-- ==========================================
-- 4. ALTER COMMUNITY_POSTS TABLE
-- ==========================================
-- Add category column to existing community_posts table
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'community_posts' AND column_name = 'category'
  ) THEN
    ALTER TABLE community_posts ADD COLUMN category VARCHAR(50) REFERENCES post_categories(id);

    -- Backfill existing posts: map type to category
    UPDATE community_posts SET category = type WHERE category IS NULL;

    -- Make category required for future posts
    ALTER TABLE community_posts ALTER COLUMN category SET NOT NULL;
  END IF;
END $$;

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_community_posts_category ON community_posts(category);
CREATE INDEX IF NOT EXISTS idx_community_posts_created_at ON community_posts(created_at DESC);

-- ==========================================
-- 5. SEED INITIAL INBOX MESSAGES (Optional)
-- ==========================================
-- Insert welcome messages for existing users
-- This can be customized or removed based on requirements
INSERT INTO inbox_messages (user_id, message_type, subject, content, metadata)
SELECT
  id as user_id,
  'encouragement' as message_type,
  'Welcome to your Inbox!' as subject,
  'This is your personal space for daily prompts, insights, and encouragement. Check back each day for new messages tailored to your journey.' as content,
  '{"is_welcome": true}'::jsonb as metadata
FROM users
WHERE NOT EXISTS (
  SELECT 1 FROM inbox_messages WHERE inbox_messages.user_id = users.id
)
ON CONFLICT DO NOTHING;

-- ==========================================
-- MIGRATION COMPLETE
-- ==========================================
