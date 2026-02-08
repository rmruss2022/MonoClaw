-- Meditations table
CREATE TABLE IF NOT EXISTS meditations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  description TEXT,
  duration INTEGER NOT NULL,
  category VARCHAR(50) NOT NULL,
  icon VARCHAR(10),
  audio_url TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Meditation sessions (user progress tracking)
CREATE TABLE IF NOT EXISTS meditation_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  meditation_id UUID NOT NULL REFERENCES meditations(id) ON DELETE CASCADE,
  started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP,
  duration_completed INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Community posts
CREATE TABLE IF NOT EXISTS community_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  author_name VARCHAR(255),
  author_avatar VARCHAR(10),
  is_anonymous BOOLEAN DEFAULT false,
  type VARCHAR(50) NOT NULL,
  content TEXT NOT NULL,
  prompt_text TEXT,
  tags TEXT[],
  likes_count INTEGER DEFAULT 0,
  comments_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Post likes
CREATE TABLE IF NOT EXISTS post_likes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id UUID NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(post_id, user_id)
);

-- Post comments
CREATE TABLE IF NOT EXISTS post_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  post_id UUID NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  author_name VARCHAR(255),
  author_avatar VARCHAR(10),
  is_anonymous BOOLEAN DEFAULT false,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User progress tracking
CREATE TABLE IF NOT EXISTS user_progress (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  check_in_date DATE NOT NULL,
  mood VARCHAR(50),
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, check_in_date)
);

-- Seed initial meditation data
INSERT INTO meditations (title, description, duration, category, icon) VALUES
  ('Morning Presence', 'Start your day with gentle awareness and grounding', 8, 'breathwork', '🌅'),
  ('Body Scan for Sleep', 'Release tension and drift into peaceful rest', 15, 'sleep', '🌙'),
  ('Breath Awareness', 'Simple practice to center yourself anytime', 5, 'breathwork', '🫁'),
  ('Loving-Kindness', 'Cultivate compassion for yourself and others', 10, 'loving-kindness', '💚'),
  ('Anxiety Relief', 'Find calm when feeling overwhelmed', 12, 'anxiety', '🌊'),
  ('Evening Wind Down', 'Let go of the day with ease', 10, 'sleep', '🌆'),
  ('Self-Compassion', 'Meet yourself with kindness and understanding', 8, 'loving-kindness', '🤲'),
  ('Quick Reset', 'Brief practice to shift your state', 3, 'breathwork', '⚡')
ON CONFLICT DO NOTHING;
