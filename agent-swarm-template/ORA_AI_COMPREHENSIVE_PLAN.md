# Ora AI - Comprehensive Polish & Enhancement Plan
## Agent Swarm Implementation Strategy

**Project:** Ora AI - Wellness companion app
**Location:** `/Users/matthew/Desktop/Feb26/ora-ai/`
**Goal:** Top-tier App Store quality (Calm/Headspace level)
**Timeline:** 9-15 days with parallel agent execution

---

## 🎯 Core Requirements (User-Specified)

### 1. Home Screen Redesign ✨
**Reference:** `/Users/matthew/Desktop/Feb26/ora-ai-api/home-screen.png`

**Design:**
- Clean header with app name + tagline
- "Choose Your Focus" section
- 5 behavior cards (iconified, clean layout):
  1. **Free-Form Chat** - Open conversation and emotional support
  2. **Journal Prompts** - Guided journaling with thoughtful questions
  3. **Guided Exercise** - Structured personal growth activities
  4. **Progress Analysis** - Insights on your personal growth journey
  5. **Weekly Planning** - Set intentions and plan your week

**Requirements:**
- Follow Ora 2 brand assets (/Users/matthew/Documents/Ora 2/)
- Clean, modern iOS design
- Each card navigates to appropriate behavior/screen
- Smooth animations and transitions

### 2. Chat Screen - Multi-Vector Decision Making 🧠
**Reference:** https://docs.amigo.ai/agent/dynamic-behavior

**Current State:**
- Basic keyword/pattern matching in `behavior-detection.service.ts`
- Simple trigger system with confidence scores

**Target Implementation:**
- **Multi-vector broadcast system:**
  - Standalone Agent Message Vector
  - Standalone User Message Vector
  - Combined Agent + User Message Vector
  - Agent Inner Thought Vector
  - External Events Vector
  - Action/Tool Call Vector

- **Behavior Selection Process:**
  1. Generate embeddings for each vector
  2. Broadcast against all conversational triggers
  3. Rank behaviors by cosine similarity
  4. LLM selects best from top 20 candidates
  5. Previously active behavior persists as candidate (behavior continuity)

- **Instruction Flexibility Spectrum:**
  - High-entropy: Vague triggers, open context (creative/exploratory conversations)
  - Low-entropy: Strict triggers, precise instructions (safety/compliance protocols)
  - Balanced mix across most interactions

**Key Focus: Goal-Oriented Conversations**
- **Journal Prompting Example:** 3-4 exchanges with clear end goal
  - Exchange 1: Initial prompt ("What's on your mind?")
  - Exchange 2: Follow-up question based on response
  - Exchange 3: Deeper exploration
  - Exchange 4: Reflection/closure
  - ❌ Don't keep going endlessly where users lose interest
  - ✅ Natural completion point with sense of accomplishment

- **Behavior-Specific Exit Conditions:**
  - Journal prompt: Save entry after 3-4 exchanges
  - Guided exercise: Complete structured activity
  - Progress analysis: Deliver insights, suggest next action
  - Weekly planning: Confirm intentions, set reminders

**Implementation Priority:**
- P0: Upgrade behavior detection to embedding-based system
- P0: Implement multi-vector broadcast
- P0: Add goal-oriented conversation flows with clear exits
- P1: Add inner thought vector for deeper pattern recognition
- P1: Implement behavior persistence/decay
- P2: Add tool usage vector for cross-behavior coordination

### 3. Community Screen - Letters & Forum 💌
**Existing:** 4-tab community (Inbox, Feed, Following, Groups) with posts/comments

**New Requirements:**

#### Daily Inbox - Letters System
- **Concept:** Like receiving letters from people
- **Features:**
  - Write letters to other users
  - Receive letters in daily inbox
  - Read and respond to letters
  - Offer support through letter responses
  - Private 1-1 communication format
  - Beautiful letter UI (envelope metaphor?)

- **UX Flow:**
  1. User writes letter to another user
  2. Letter appears in recipient's inbox (next day or immediately?)
  3. Recipient reads letter (opens envelope animation?)
  4. Respond with letter back
  5. Support exchange continues as letter thread

#### Public Forum Posts as Cards
- **Current:** Basic post list with category badges
- **Target:** Engaging card-based UI

**Card Design:**
- Question/prompt prominently displayed
- Author info (anonymous option)
- Response count
- Support/reaction count
- Category badge
- Visual hierarchy

**Interaction Flow:**
1. User sees forum feed with question cards
2. Tap card → Opens full post view
3. See original post + all responses
4. Users can:
   - Add their own response
   - Reply to other responses (threaded discussions)
   - React/support responses
   - Talk to each other in comments

**Implementation:**
- P0: Design letter system (write, send, receive, respond)
- P0: Build letter UI with envelope/card metaphor
- P0: Redesign forum posts as engaging cards
- P0: Implement threaded discussions
- P1: Add letter notification system
- P1: Add letter history/archive
- P2: Add letter templates for common support scenarios

### 4. Authentication & Onboarding 🔐

#### Authentication
- Clean sign-in/sign-up flow
- Email + password
- Social auth (optional: Apple, Google)
- Secure JWT handling
- Biometric login (Face ID/Touch ID)

#### Intake Quiz
- **Purpose:** Learn about users to personalize experience
- **Must be:** Top-quality, thoughtful, engaging
- **Questions to cover:**
  - Wellness goals
  - Current challenges
  - Preferred communication style
  - Daily routine/schedule
  - Previous therapy/wellness experience
  - What brings them to app

**Implementation:**
- P0: Build auth flow (sign-up, sign-in, JWT)
- P0: Design intake quiz (8-12 questions, progress indicator)
- P0: Save quiz responses to user profile
- P0: Use quiz data to personalize initial experience
- P1: Add biometric auth
- P1: Build onboarding flow (quiz → tutorial → first action)

### 5. Meditation Screen Enhancement 🧘
**Existing:** Meditation timer working

**Enhancements:**
- Better visual design (circular progress, ambient animations)
- Ambient sounds (rain, ocean, forest, white noise)
- Breathing guides (4-7-8 technique, box breathing)
- Session history and streaks
- Session variety (timed, guided, breathing exercises)

---

## 📊 Task Categories (70-100 Tasks)

### Category 1: Home Screen Redesign (8-10 tasks)
- Design home screen matching reference image
- Implement "Choose Your Focus" card grid
- Create behavior cards with icons/descriptions
- Add smooth card tap animations
- Wire up navigation to behaviors
- Integrate Ora 2 brand assets
- Add header with app name + tagline
- Implement responsive layout
- Add empty state/loading state

### Category 2: Multi-Vector Chat System (12-15 tasks)
- Research/document Amigo.ai approach
- Design embedding architecture
- Implement vector generation service
- Build cosine similarity ranking
- Create behavior candidacy pool system
- Implement LLM selection logic
- Add behavior persistence/decay
- Build goal-oriented conversation flows
- Add exit conditions per behavior
- Implement 3-4 exchange journal flow
- Add conversation completion detection
- Build inner thought vector
- Add tool usage tracking vector
- Test behavior transitions
- Performance optimization

### Category 3: Letters System (10-12 tasks)
- Design letter data model
- Build letter writing UI
- Create envelope/card animation
- Implement letter send/receive
- Build inbox letter list
- Add letter read/unread states
- Implement letter response flow
- Design letter thread view
- Add letter notifications
- Build letter archive
- Add letter search
- Test letter delivery

### Category 4: Forum Card Redesign (8-10 tasks)
- Redesign post cards (question-focused)
- Improve card visual hierarchy
- Add engaging card interactions
- Build full post view (expanded card)
- Implement threaded discussions
- Add response nesting (replies to replies)
- Improve comment UI
- Add reaction system
- Build conversation threading
- Test discussion flows

### Category 5: Authentication & Intake (10-12 tasks)
- Design auth screens (sign-up, sign-in)
- Implement email/password auth
- Add JWT token management
- Build secure storage
- Design intake quiz flow
- Write quiz questions (8-12)
- Build quiz UI with progress
- Implement quiz data model
- Save quiz responses to profile
- Use quiz data for personalization
- Add biometric auth
- Build onboarding flow

### Category 6: Visual Design & Branding (10-12 tasks)
- Integrate Ora 2 logo/assets
- Define color palette from brand bible
- Create typography system
- Design icon set (custom or system)
- Implement dark mode
- Add smooth transitions/animations
- Design loading states
- Create empty states
- Build error states
- Add micro-interactions
- Polish button/input styles
- Create design system documentation

### Category 7: Meditation Enhancements (6-8 tasks)
- Redesign meditation timer UI
- Add circular progress visualization
- Integrate ambient sound library
- Build sound selector/mixer
- Add breathing animation guide
- Implement session history
- Build streak tracking
- Add session variety (guided/timed)

### Category 8: Backend & API (10-12 tasks)
- Upgrade behavior detection to embeddings
- Add vector database (Pinecone/Weaviate)
- Implement letters API endpoints
- Add threaded discussions support
- Build quiz response storage
- Optimize database queries
- Add caching (Redis)
- Implement real-time features (WebSockets)
- Add analytics events
- Build admin moderation tools
- Add rate limiting
- Write API documentation

### Category 9: Performance & Quality (8-10 tasks)
- Optimize app bundle size
- Implement image lazy loading
- Add skeleton loaders
- Optimize chat message rendering
- Add error tracking (Sentry)
- Write unit tests (80%+ coverage)
- Build E2E test suite
- Performance profiling
- Memory leak detection
- Accessibility audit

### Category 10: App Store Prep (6-8 tasks)
- Design app icon (light/dark variants)
- Create App Store screenshots (6)
- Record app preview video (30s)
- Write App Store description
- Create privacy policy
- Write terms of service
- Build support website
- Create press kit

---

## 🏗️ PM Agent Task Breakdown Instructions

```javascript
sessions_spawn({
  label: "PM-Agent-Ora-Comprehensive",
  agentId: "main",
  model: "anthropic/claude-opus-4-6",
  thinking: "high",
  task: `You are a Project Manager Agent for the Ora AI wellness app enhancement.

YOUR MISSION: Create 70-100 actionable tasks to polish Ora AI to App Store top-tier quality.

PROJECT CONTEXT:
Location: /Users/matthew/Desktop/Feb26/ora-ai/
Type: React Native/Expo wellness app
Current State: Functional with 3 screens (Chat, Meditation, Community)
Goal: Calm/Headspace quality level

REFERENCE MATERIALS:
1. Home Screen Design: /Users/matthew/Desktop/Feb26/ora-ai-api/home-screen.png
2. Brand Assets: /Users/matthew/Documents/Ora 2/ (logo, brand bible, fonts)
3. Multi-Vector AI: https://docs.amigo.ai/agent/dynamic-behavior
4. Existing Backend: /Users/matthew/Desktop/Feb26/ora-ai-api/src/services/

CORE REQUIREMENTS (MANDATORY):

1. HOME SCREEN REDESIGN
   - Match reference design exactly
   - 5 behavior cards: Free-Form Chat, Journal Prompts, Guided Exercise, Progress Analysis, Weekly Planning
   - Use Ora 2 brand assets
   - Clean, modern iOS aesthetic

2. MULTI-VECTOR CHAT SYSTEM
   - Upgrade from keyword matching to embedding-based detection
   - Implement 6 vector types (agent message, user message, combined, inner thought, external events, tool usage)
   - Build behavior candidacy pool with cosine similarity
   - Add goal-oriented flows with 3-4 exchange cycles
   - Clear exit conditions (no endless conversations)
   - Example: Journal prompting finishes after 3-4 meaningful exchanges

3. LETTERS SYSTEM (Community Inbox)
   - Design letter writing/receiving UI
   - Envelope/card metaphor for inbox
   - Private 1-1 communication
   - Support exchange through letter threads
   - Daily inbox with new letters

4. FORUM CARD REDESIGN
   - Posts displayed as engaging question cards
   - Full post view with responses
   - Threaded discussions (replies to replies)
   - Users can talk to each other
   - Support/reaction system

5. AUTHENTICATION & INTAKE QUIZ
   - Clean auth flow (sign-up/sign-in)
   - 8-12 question intake quiz (top quality)
   - Questions cover: goals, challenges, preferences, routine, experience
   - Use quiz data for personalization

6. MEDITATION ENHANCEMENTS
   - Better timer UI (circular progress)
   - Ambient sounds (rain, ocean, forest)
   - Breathing guides
   - Session history + streaks

TASK CATEGORIES (Create tasks for all):
1. Home Screen Redesign (8-10 tasks)
2. Multi-Vector Chat System (12-15 tasks) ← MOST CRITICAL
3. Letters System (10-12 tasks)
4. Forum Card Redesign (8-10 tasks)
5. Authentication & Intake (10-12 tasks)
6. Visual Design & Branding (10-12 tasks)
7. Meditation Enhancements (6-8 tasks)
8. Backend & API (10-12 tasks)
9. Performance & Quality (8-10 tasks)
10. App Store Prep (6-8 tasks)

TASK FORMAT:
POST http://localhost:3001/api/tasks
{
  "project_id": <project_id>,
  "task_id": "task-slug",
  "title": "Specific actionable title",
  "description": "Detailed what, why, and how. Include file paths and implementation notes.",
  "state": "todo",
  "priority": "high|medium|low",
  "estimated_hours": 2-8,
  "dependencies": ["other-task-id"],
  "metadata": {
    "agent_type": "Designer-Agent|iOS-Dev-Agent|Backend-Dev-Agent|QA-Agent|Content-Agent",
    "category": "HomeScreen|MultiVectorChat|Letters|Forum|Auth|Design|Meditation|Backend|Performance|AppStore",
    "file_paths": ["/Users/matthew/Desktop/Feb26/ora-ai/src/screens/HomeScreen.tsx"],
    "references": ["home-screen.png", "Ora 2 brand assets"]
  }
}

AGENT TYPES:
- Designer-Agent: UI/UX, visual design, mockups, brand integration
- iOS-Dev-Agent: React Native components, screens, navigation, animations
- Backend-Dev-Agent: Node.js API, embeddings, vector DB, endpoints
- QA-Agent: Testing, validation, bug reports
- Content-Agent: Quiz questions, copy, meditation scripts

PRIORITIES:
- P0 (Critical): Must-have for quality launch (home screen, multi-vector chat, letters, auth)
- P1 (Important): Significant improvements (forum redesign, meditation, branding)
- P2 (Nice-to-have): Polish and extras (advanced animations, analytics)

IMPLEMENTATION NOTES:
- Multi-vector chat is MOST COMPLEX - break into 12-15 subtasks
- Letters system is NEW feature - needs full design + implementation
- Home screen redesign MUST match reference image
- Intake quiz quality is CRITICAL - thoughtful, engaging questions
- All UI must follow Ora 2 brand guidelines

DELIVERABLES:
1. Create project (POST /api/projects)
2. Create 70-100 tasks across all categories
3. Write ROADMAP.md with phases and timeline
4. Highlight dependencies and critical path
5. Estimate total hours and team size needed

START NOW. Read the reference materials, then create comprehensive task breakdown.`,
  runTimeoutSeconds: 3600,
  cleanup: "keep"
});
```

---

## 🚀 Success Criteria

**Technical:**
- Multi-vector chat working with 6 vector types
- Goal-oriented flows complete naturally (3-4 exchanges)
- Letters system fully functional
- Intake quiz 8-12 questions, data saved
- Home screen matches reference design

**Quality:**
- App Store rating target: 4.7+ stars
- <3s load time, 60fps scrolling
- 80%+ test coverage
- Zero P0 bugs at launch

**User Experience:**
- Engaging onboarding (quiz feels thoughtful)
- Conversations feel natural and goal-oriented
- Letters system feels intimate and supportive
- Forum discussions are engaging
- Meditation experience is calming

---

## ⏱️ Timeline Estimate

**Phase 1: Design & Planning** (1-2 days)
- PM Agent task breakdown
- Designer creates mockups for new features
- Backend architect plans multi-vector system

**Phase 2: Core Features** (4-6 days)
- Home screen redesign
- Multi-vector chat implementation
- Letters system build
- Auth + intake quiz

**Phase 3: Polish & Enhancement** (2-3 days)
- Forum card redesign
- Meditation improvements
- Visual design polish
- Brand integration

**Phase 4: Quality & Testing** (1-2 days)
- Performance optimization
- Bug fixing
- QA testing
- User testing

**Phase 5: App Store Prep** (1-2 days)
- Screenshots, video, copy
- Policies and documentation
- Final polish

**Total: 9-15 days** with parallel execution

---

## 🎯 Ready to Start?

Spawn PM-Agent with instructions above to:
1. Analyze Ora AI codebase
2. Review reference materials
3. Create 70-100 detailed tasks
4. Populate Agent Swarm dashboard
5. Write comprehensive roadmap

Then build Orchestrator to execute with specialist agents! 🚀
