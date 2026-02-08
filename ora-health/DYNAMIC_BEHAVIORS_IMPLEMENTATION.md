# Dynamic Behaviors Implementation Complete! 🎯

## What I've Built

I've implemented a complete dynamic behavior system for Shadow AI with **8 intelligent behaviors** that automatically activate based on user messages.

---

## 📋 Implemented Behaviors

### 1. **Difficult Emotion Processing** (Priority: 10 - Highest)
**When**: User expresses distress, overwhelm, anxiety, sadness
**Keywords**: `struggling`, `overwhelmed`, `anxious`, `sad`, `angry`, `can't cope`
**Approach**:
- Validates emotions first without judgment
- Avoids toxic positivity or rushing to solutions
- Helps user feel heard and less alone
- Offers gentle next steps

**Example**: _"I'm feeling really overwhelmed and can't cope"_

---

### 2. **Cognitive Reframing** (Priority: 8)
**When**: User uses absolute/black-white thinking
**Keywords**: `always`, `never`, `everyone`, `nothing`, `everything`
**Approach**:
- Gently challenges distortions through questions
- Finds counter-examples from their own journal
- Introduces nuance without invalidating feelings
- Socratic method, not lecturing

**Example**: _"I always fail at everything and nothing ever works out"_

---

### 3. **Weekly Planning** (Priority: 7)
**When**: User wants to plan upcoming week
**Keywords**: `plan my week`, `upcoming week`, `this week`, `next week`
**Approach**:
- Creates 3-5 realistic intentions
- Balances productivity with self-care
- References past patterns from journal
- Makes it energizing, not overwhelming

**Example**: _"I want to plan my week ahead"_

---

### 4. **Weekly Review** (Priority: 7)
**When**: User reflects on past week
**Keywords**: `how was my week`, `week reflection`, `looking back`
**Approach**:
- Extracts patterns from past 7 days of journal entries
- Celebrates wins (big and small)
- Identifies learnings from challenges
- Focuses on growth, not just outcomes

**Example**: _"How was my week? I want to reflect on what happened"_

---

### 5. **Gratitude Practice** (Priority: 6)
**When**: User expresses gratitude or appreciation
**Keywords**: `grateful`, `gratitude`, `thankful`, `appreciate`
**Approach**:
- Guides to 3 specific gratitude items
- Explores the "why" behind each (deeper meaning)
- Encourages specificity over generic responses
- Makes it genuine, not forced

**Example**: _"I'm so grateful for my supportive friends"_

---

### 6. **Goal Setting & Tracking** (Priority: 6)
**When**: User expresses intentions or goals
**Keywords**: `want to`, `goal`, `trying to`, `working on`, `hoping to`
**Approach**:
- Makes goals SMART (Specific, Measurable, Achievable, Relevant, Time-bound)
- Breaks down to smallest first step (doable in 24-48 hours)
- Checks past patterns for feasibility
- Anticipates obstacles

**Example**: _"I want to start exercising more regularly"_

---

### 7. **Values Clarification** (Priority: 6)
**When**: User questions priorities or meaning
**Keywords**: `what matters`, `important to me`, `meaningful`, `values`, `purpose`
**Approach**:
- Explores core values through questions
- Uses journal entries to find patterns
- Connects values to current situations
- Notices value-action alignment or conflicts

**Example**: _"What's really important to me in life?"_

---

### 8. **Energy & Mood Check-in** (Priority: 5)
**When**: User mentions tiredness or energy levels
**Keywords**: `feeling tired`, `exhausted`, `drained`, `low energy`, `burnt out`
**Approach**:
- Quick, practical check-in (2-3 questions)
- Focuses on present moment
- Checks basics: sleep, food, movement
- Suggests one small action

**Example**: _"I'm feeling really tired and low energy today"_

---

### 9. **Free-form Chat** (Priority: 1 - Fallback)
**When**: No other behavior matches
**Approach**:
- Warm, non-directive presence
- Follows user's lead
- Adaptive and responsive
- Uses tools when helpful for context

**Example**: _"Just want to chat and share some thoughts"_

---

## 🛠️ Technical Implementation

### Files Created

1. **`src/config/behaviors.ts`** (525 lines)
   - Complete behavior definitions with triggers and instructions
   - Detailed system prompts for each behavior
   - Priority system for behavior selection

2. **`src/services/behavior-detection.service.ts`** (172 lines)
   - Multi-vector detection engine
   - Keyword and pattern matching
   - Context awareness (time of day, day of week)
   - Confidence scoring and priority handling
   - Behavior transition logging

3. **Updated `src/services/ai.service.ts`**
   - Integrated dynamic behavior detection
   - Applies behavior-specific system prompts
   - Logs activated behaviors with confidence scores
   - Saves behavior metadata with messages

### How It Works

```
User Message
    ↓
Behavior Detection Service
    ├── Keyword Matching
    ├── Pattern Matching (Regex)
    ├── Context Checks (time, day)
    └── Confidence Scoring
    ↓
Behavior Selection
    ├── Sort by Priority (1-10)
    ├── Then by Confidence
    └── Fallback to Free-form Chat
    ↓
AI Service
    ├── Apply Behavior System Prompt
    ├── Use Behavior Constraints
    ├── Apply Tool Bias
    └── Call Claude API
    ↓
Log Transition
    └── Save to behavior_transitions table
```

### Database Integration

The system logs every behavior transition to Postgres:
- Which behavior was activated
- Confidence score
- Matched triggers
- Message excerpt
- Timestamp

This data will be useful for:
- Analytics and insights
- Improving trigger detection
- Understanding user patterns
- Future: Behavior persistence and decay

---

## 🎯 Key Features

### 1. **Priority-Based Selection**
Higher priority behaviors override lower ones when both match. For example, if someone says "I always feel overwhelmed", both **Cognitive Reframing** (priority 8) and **Difficult Emotion Processing** (priority 10) match, but the latter wins because emotional support is more critical.

### 2. **Multi-Vector Detection**
- **Keywords**: Direct word matching
- **Patterns**: Regex for complex expressions
- **Context**: Day of week, time of day
- **Confidence**: Scored 0-1 based on match strength

### 3. **Behavior-Specific Instructions**
Each behavior has:
- **System Prompt**: Detailed instructions for Claude
- **Constraints**: What to avoid or prioritize
- **Tool Bias**: Which tools to use
- **Success Criteria**: What a good outcome looks like
- **Tone**: How to communicate

### 4. **Automatic Logging**
Every behavior activation is logged with:
- User ID
- From/To behavior IDs
- Trigger type and data
- Confidence score
- Context and metadata

---

## 🧪 Testing

### Manual Testing in Browser
1. Go to http://localhost:8081
2. Try the example messages for each behavior
3. Watch backend logs for: `🎯 Activated behavior: [Name]`

See `MANUAL_TEST_INSTRUCTIONS.md` for detailed test cases.

### What to Look For
- ✅ Correct behavior activates based on keywords
- ✅ Response tone matches behavior instructions
- ✅ Claude uses appropriate tools (journal entries, summaries)
- ✅ Higher priority behaviors override lower ones
- ✅ Transitions are logged to database

---

## 📊 Backend Logging

When a message is sent, you'll see:
```
Using real Claude API with dynamic behaviors
🎯 Activated behavior: Difficult Emotion Processing
   Confidence: 0.80, Triggers: keyword:overwhelmed, keyword:can't cope, pattern:can't\s+(handle|deal|cope)
```

This shows:
- Which behavior was activated
- How confident the detection was
- Which specific triggers matched

---

## 🚀 Next Steps (Future Enhancements)

### Phase 2: Embeddings-Based Detection
- Use OpenAI embeddings for semantic similarity
- Detect behaviors from meaning, not just keywords
- Handle edge cases and subtle expressions

### Phase 3: Behavior Persistence & Decay
- Behaviors persist across multiple messages
- Gradual decay back to free-form chat
- Context-aware transitions

### Phase 4: Learning & Optimization
- Analyze transition data for patterns
- User feedback on behavior helpfulness
- Automatic trigger optimization
- A/B testing different system prompts

### Phase 5: Custom Behaviors
- Users can create custom behaviors
- Define their own triggers and instructions
- Share behaviors with community

---

## 💡 Design Philosophy

### Based on Amigo AI's Dynamic Behavior Model

1. **Runtime Problem Definition Changers**
   - Behaviors reshape optimization constraints
   - Modify available tools mid-conversation
   - Redefine success criteria dynamically

2. **Multi-Vector Broadcast System**
   - Multiple detection vectors running in parallel
   - Catches sharp topic pivots
   - Detects subtle contextual shifts

3. **Entropy Spectrum**
   - High-entropy: Flexible, adaptive (free-form chat)
   - Low-entropy: Strict protocols (difficult emotions, crisis)

### Our Implementation

- **Keyword-first**: Starting simple for reliability
- **Priority-based**: Critical behaviors (emotional support) override others
- **Logging-focused**: Building data for future ML improvements
- **User-centered**: Each behavior designed around actual user needs

---

## ✅ Summary

You now have a fully functional dynamic behavior system with:
- ✅ 8 intelligent behaviors + 1 fallback
- ✅ Keyword and pattern-based detection
- ✅ Priority-based selection
- ✅ Confidence scoring
- ✅ Full database logging
- ✅ Claude API integration
- ✅ Behavior-specific system prompts
- ✅ Context awareness

The system is **ready to test** at http://localhost:8081!

Check backend logs to see which behaviors activate as you chat. 🎉
