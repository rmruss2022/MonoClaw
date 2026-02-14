# Agent Swarm Orchestration Architecture
## For Aura Health App Development

**Goal:** Build Aura Health app to App Store top-tier quality using distributed agent swarm

---

## Two-Tier Architecture

### Tier 1: Project Manager Agent (PM-Agent)
**Purpose:** One-time strategic planning and task breakdown

**When to run:** Project initialization or major milestone planning

**Responsibilities:**
1. **Requirements Analysis**
   - Analyze user goals for Aura Health app
   - Define core features (meditation, sleep tracking, mood journal, etc.)
   - Research competitive landscape

2. **Competitive Research**
   - Study top-ranked health apps: Calm, Headspace, Balance, Insight Timer
   - Identify best practices, UI patterns, features
   - Note gaps and opportunities

3. **Task Breakdown**
   - Decompose project into 50-100+ actionable tasks
   - Create clear, specific task descriptions
   - Assign priorities (P0/P1/P2)
   - Estimate effort (hours)
   - Set task dependencies

4. **Phase Organization**
   - Research & Planning
   - Design & Prototyping
   - Backend Development
   - iOS Development
   - QA & Testing
   - Polish & Optimization
   - App Store Deployment

5. **Kanban Population**
   - Insert tasks into SQLite database
   - Set initial state (todo)
   - Configure dependencies
   - Create project entry

**Output:**
- Project ID in database
- 50-100+ tasks ready to execute
- Dependency graph established
- Roadmap document created

**Spawn command:**
```javascript
sessions_spawn({
  label: "PM-Agent-Aura-Health",
  agentId: "main",
  model: "anthropic/claude-opus-4-6",
  thinking: "high",
  task: `You are a Project Manager Agent for the Agent Swarm system.

YOUR MISSION: Break down the Aura Health app project into 50-100+ actionable tasks.

CONTEXT:
- Goal: Build Aura Health app to App Store top-tier quality
- Competitive apps: Calm, Headspace, Balance, Insight Timer
- Features: Meditation, sleep tracking, mood journal, breathing exercises
- Platform: iOS (SwiftUI)
- Backend: Firebase/Supabase

RESEARCH PHASE:
1. Research top 5 health/meditation apps on App Store
2. Document their core features, UI patterns, user flows
3. Identify what makes them successful

TASK BREAKDOWN:
Create tasks for EVERY aspect:
- Product specs (feature definitions)
- Design (UI/UX mockups, assets, color schemes)
- Backend (API, database, auth, cloud functions)
- iOS Development (screens, components, ViewModels)
- QA (test plans, automated tests)
- Polish (animations, performance, accessibility)
- Deployment (App Store assets, submission)

TASK FORMAT:
- ID: short-slug (e.g., "med-timer-ui")
- Title: Clear, actionable (e.g., "Design meditation timer screen UI")
- Description: What needs to be done
- Priority: P0 (critical), P1 (important), P2 (nice-to-have)
- Estimated hours: realistic estimate
- Dependencies: task IDs that must complete first
- Agent type: which specialist should handle this

DATABASE API:
POST http://localhost:3001/api/tasks
{
  "project_id": 1,
  "task_id": "task-slug",
  "title": "Task title",
  "description": "Detailed description",
  "state": "todo",
  "priority": "high",
  "estimated_hours": 3,
  "dependencies": ["other-task-id"],
  "metadata": {
    "agent_type": "Designer-Agent",
    "phase": "Design"
  }
}

DELIVERABLES:
1. Create project in database (POST /api/projects)
2. Create all tasks (POST /api/tasks for each)
3. Write ROADMAP.md summarizing phases and milestones
4. Report task count and dependency graph

START NOW. Research, plan, then populate the database.`,
  runTimeoutSeconds: 3600, // 1 hour
  cleanup: "keep"
});
```

---

### Tier 2: Orchestrator Agent (Continuous)
**Purpose:** Execution manager and traffic controller

**When to run:** Continuously after PM Agent completes

**Responsibilities:**

1. **Kanban Monitoring**
   - Poll database every 30 seconds
   - Query: `SELECT * FROM tasks WHERE state = 'todo' AND dependencies_met = true`
   - Check for ready tasks

2. **Agent Spawning**
   - Identify agent type from task metadata
   - Spawn appropriate specialist via `sessions_spawn`
   - Track spawned agents in `agents` table
   - Update task state to "in-progress"

3. **Progress Tracking**
   - Monitor agent completion via `sessions_list`
   - Check for agent errors or timeouts
   - Update task states based on agent results
   - Move tasks: todo → in-progress → ready → qa → complete

4. **Dependency Resolution**
   - Mark tasks as ready when dependencies complete
   - Update `dependencies_met` flag in database
   - Trigger next wave of agents

5. **Reporting**
   - Send progress updates to Telegram every hour
   - Alert on blockers or errors
   - Celebrate milestones (25%, 50%, 75%, 100%)

6. **Error Handling**
   - Retry failed agents (max 3 attempts)
   - Escalate persistent failures to user
   - Log all errors to activity log

**Loop Logic:**
```javascript
while (project.status !== 'completed') {
  // 1. Check for ready tasks
  const readyTasks = await fetch('http://localhost:3001/api/tasks?state=todo&ready=true');
  
  // 2. Spawn agents for ready tasks (max 3 concurrent)
  for (const task of readyTasks.slice(0, 3)) {
    await spawnAgentForTask(task);
  }
  
  // 3. Check completed agents
  const activeAgents = await sessions_list({ kinds: ['subagent'] });
  for (const agent of activeAgents) {
    if (agent.state === 'completed') {
      await handleAgentCompletion(agent);
    }
  }
  
  // 4. Update progress
  const stats = await fetch('http://localhost:3001/api/projects/1');
  await reportProgress(stats);
  
  // 5. Wait before next cycle
  await sleep(30000); // 30 seconds
}
```

**Spawn command:**
```javascript
sessions_spawn({
  label: "Orchestrator-Aura-Health",
  agentId: "main",
  model: "nvidia/moonshotai/kimi-k2.5",
  thinking: "low",
  task: `You are the Orchestrator Agent for the Agent Swarm system.

YOUR MISSION: Execute the Aura Health app project by spawning and managing specialist agents.

CONTEXT:
- Project ID: 1 (Aura Health)
- Dashboard: http://localhost:5173/
- Backend API: http://localhost:3001/

LOOP CONTINUOUSLY:

1. Check for ready tasks:
   GET http://localhost:3001/api/tasks?state=todo&ready=true

2. For each ready task (max 3 concurrent):
   - Read task details
   - Identify agent type from metadata
   - Spawn specialist agent with task context
   - Update task state to "in-progress"

3. Monitor active agents:
   - Use sessions_list to check sub-agent status
   - When agent completes, move task to next state
   - Log completion to activity log

4. Report progress every hour:
   - Send Telegram message with stats
   - Include: completed tasks, active agents, blockers

5. Sleep 30 seconds, repeat

ERROR HANDLING:
- Retry failed agents (max 3 attempts)
- If task fails 3 times, mark as "blocked" and alert user

AGENT TYPES:
- Product-Engineer-Agent: Feature specs, requirements
- Designer-Agent: UI/UX, mockups, assets
- iOS-Dev-Agent: SwiftUI code, ViewModels
- Backend-Dev-Agent: API, database, functions
- QA-Agent: Tests, bug reports
- Polish-Agent: Optimization, accessibility
- Deploy-Agent: App Store submission

START MONITORING. Run continuously until project complete.`,
  runTimeoutSeconds: 86400, // 24 hours
  cleanup: "keep"
});
```

---

## Specialized Sub-Agents

### 1. Product-Engineer-Agent
**Responsibilities:**
- Write feature specifications
- Define user stories and acceptance criteria
- Create wireframes/mockups (text-based)
- Document API contracts
- Define data models

**Output:** `PRODUCT_SPEC.md` for each feature

### 2. Designer-Agent
**Responsibilities:**
- Create UI/UX mockups (describe in detail or generate with DALL-E)
- Define color schemes and typography
- Design app icons and splash screens
- Create asset lists (images, animations)
- Write design system documentation

**Output:** Design files, asset manifests, style guides

### 3. iOS-Dev-Agent
**Responsibilities:**
- Write SwiftUI views and components
- Implement ViewModels (MVVM architecture)
- Integrate with backend APIs
- Handle navigation and state management
- Implement animations and gestures

**Output:** Swift code files, Xcode project structure

### 4. Backend-Dev-Agent
**Responsibilities:**
- Design database schema
- Create API endpoints (REST/GraphQL)
- Implement authentication (Firebase Auth)
- Set up cloud functions
- Configure push notifications

**Output:** Backend code (Node.js/Python), database migrations

### 5. QA-Agent
**Responsibilities:**
- Write test plans
- Create automated tests (XCTest, UI tests)
- Perform manual testing
- File bug reports
- Validate accessibility compliance

**Output:** Test files, bug reports, QA checklist

### 6. Polish-Agent
**Responsibilities:**
- Optimize performance (reduce load times)
- Improve animations and transitions
- Enhance accessibility (VoiceOver, Dynamic Type)
- Add haptic feedback
- Refine edge cases

**Output:** Optimized code, polish report

### 7. Deploy-Agent
**Responsibilities:**
- Create App Store assets (screenshots, preview video)
- Write app description and keywords
- Configure App Store Connect
- Submit for review
- Monitor review status

**Output:** App Store listing, submission confirmation

---

## Kanban States & Workflow

```
todo → in-progress → ready → qa → complete
```

**State Transitions:**

1. **todo → in-progress**
   - Trigger: Orchestrator spawns agent for task
   - Action: Update task state, create agent entry

2. **in-progress → ready**
   - Trigger: Agent completes successfully
   - Action: Move task to "ready", mark dependent tasks as ready

3. **ready → qa**
   - Trigger: QA-Agent assigned (for dev tasks)
   - Action: QA-Agent validates work

4. **qa → complete**
   - Trigger: QA-Agent approves
   - Action: Task marked complete, update project progress

**Special Cases:**
- **Blocked**: Task stuck (agent failed 3x)
- **Skip QA**: Design/spec tasks go ready → complete directly

---

## Database Schema

### Projects Table
```sql
CREATE TABLE projects (
  id INTEGER PRIMARY KEY,
  name TEXT,
  description TEXT,
  status TEXT, -- in-progress, completed, blocked
  created_at TIMESTAMP,
  target_completion TIMESTAMP
);
```

### Tasks Table
```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  task_id TEXT UNIQUE,
  title TEXT,
  description TEXT,
  state TEXT, -- todo, in-progress, ready, qa, complete, blocked
  priority TEXT, -- P0, P1, P2
  estimated_hours REAL,
  actual_hours REAL,
  dependencies TEXT, -- JSON array of task_ids
  dependencies_met BOOLEAN,
  assigned_to TEXT,
  metadata TEXT, -- JSON object
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

### Agents Table
```sql
CREATE TABLE agents (
  id INTEGER PRIMARY KEY,
  project_id INTEGER,
  task_id TEXT,
  agent_id TEXT,
  session_key TEXT,
  status TEXT, -- running, completed, failed
  spawned_at TIMESTAMP,
  completed_at TIMESTAMP
);
```

---

## Progress Reporting

**Telegram Updates (Every Hour):**
```
🏗️ Aura Health - Build Progress

✅ Completed: 12/87 tasks (13.8%)
🔄 In Progress: 3 agents working
⏳ Ready: 5 tasks waiting
🚫 Blocked: 0

Recent Completions:
- ✓ Design meditation timer UI (Designer-Agent)
- ✓ Implement mood journal API (Backend-Dev-Agent)
- ✓ Write user auth spec (Product-Engineer-Agent)

Active Now:
- 🎨 Creating app icon variants (Designer-Agent)
- 💻 Building meditation screen (iOS-Dev-Agent)
- 🧪 Testing onboarding flow (QA-Agent)

Next Up:
- Design sleep tracker UI
- Implement breathing exercises
- Create workout routine API

ETA: ~68 hours remaining
```

---

## Implementation Steps

### Phase 1: PM Agent (Tonight)
1. Create PM-Agent spawn command
2. Test with Aura Health project
3. Verify tasks populate correctly
4. Review task breakdown quality

### Phase 2: Orchestrator Core (Tomorrow)
1. Build orchestrator loop logic
2. Implement task polling
3. Add agent spawning
4. Test with 1-2 manual tasks

### Phase 3: Specialist Agents (Weekend)
1. Define agent templates
2. Create spawn commands for each type
3. Test individual agents
4. Validate output quality

### Phase 4: Full Integration (Next Week)
1. Run full pipeline end-to-end
2. Monitor for 24 hours
3. Fix bugs and edge cases
4. Optimize parallel execution

### Phase 5: Production Deploy (Week 2)
1. Run Aura Health project fully
2. Deliver working iOS app
3. Document lessons learned
4. Refine for future projects

---

## Success Metrics

- **Task Completion Rate**: >90% of tasks complete successfully
- **Agent Efficiency**: <10% of agents require retry
- **Parallel Execution**: 3-5 agents running simultaneously
- **Time to Completion**: Full project done in 3-5 days
- **Output Quality**: Code passes QA, design matches specs
- **User Satisfaction**: Aura Health app reaches App Store top-tier quality

---

## Next Steps

1. **Tonight**: Spawn PM-Agent to break down Aura Health
2. **Review**: Check task breakdown quality in dashboard
3. **Tomorrow**: Build Orchestrator Agent
4. **This Weekend**: Test full pipeline with subset of tasks
5. **Next Week**: Run complete Aura Health build

**Ready to start with PM Agent?**
