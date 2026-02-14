const fs = require('fs');
const http = require('http');

function postJSON(path, data) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(data);
    
    const options = {
      hostname: 'localhost',
      port: 3001,
      path,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body)
      }
    };
    
    const req = http.request(options, (res) => {
      let responseData = '';
      
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      
      res.on('end', () => {
        try {
          resolve(JSON.parse(responseData));
        } catch (e) {
          reject(new Error('Invalid JSON response'));
        }
      });
    });
    
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function addContext() {
  const roadmapPath = '/Users/matthew/.openclaw/workspace/agent-swarm-template/ROADMAP.md';
  const planPath = '/Users/matthew/.openclaw/workspace/agent-swarm-template/ORA_AI_COMPREHENSIVE_PLAN.md';
  
  const roadmapContent = fs.readFileSync(roadmapPath, 'utf8');
  const planContent = fs.readFileSync(planPath, 'utf8');
  
  try {
    // Add roadmap
    console.log('📄 Adding roadmap...');
    const roadmapResp = await postJSON('/api/projects/3/context', {
      document_type: 'roadmap',
      title: 'Ora AI - App Store Polish Roadmap',
      content: roadmapContent,
      file_path: roadmapPath
    });
    console.log(`✅ Roadmap added (ID: ${roadmapResp.id})`);
    
    // Add comprehensive plan
    console.log('📄 Adding comprehensive plan...');
    const planResp = await postJSON('/api/projects/3/context', {
      document_type: 'plan',
      title: 'Ora AI - Comprehensive Polish & Enhancement Plan',
      content: planContent,
      file_path: planPath
    });
    console.log(`✅ Comprehensive plan added (ID: ${planResp.id})`);
    
    // Add orchestrator instructions
    const orchestratorInstructions = `# Orchestrator Agent Instructions - Ora AI Project

## Your Role

You are the Orchestrator Agent for the Ora AI App Store Polish project (Project ID: 3). Your job is to:

1. **Monitor the kanban board** (http://localhost:3001/api/projects/3)
2. **Identify ready tasks** with zero unmet dependencies
3. **Spawn specialist agents** to execute tasks
4. **Track agent progress** and update task states
5. **Report progress** to the user via Telegram

## Project Context

**Total Tasks:** 96 tasks across 10 categories
**Estimated Hours:** 434 hours
**Timeline:** 11-15 days with parallel execution
**Critical Path:** Multi-vector chat system (8 days)

Read the full project context at:
- ROADMAP.md: http://localhost:3001/api/projects/3/context (document_type: roadmap)
- ORA_AI_COMPREHENSIVE_PLAN.md: http://localhost:3001/api/projects/3/context (document_type: plan)

## Agent Types & Capabilities

### Designer-Agent
- **Assigned tasks:** 14 tasks (ORA-001, 006, 028, 038, 047, 052, 066-067, 069-070, 074, 091-093)
- **Skills:** Figma, UI/UX design, brand guidelines, iOS design patterns
- **Tools:** Read Ora 2 brand assets, analyze HomeScreen.png reference
- **Output:** Figma links, design specs, exported assets

### iOS-Dev-Agent
- **Assigned tasks:** 44 tasks (React Native components, screens, navigation)
- **Skills:** React Native, Expo, TypeScript, animations, navigation
- **Tools:** File editing, React Native CLI, Expo CLI
- **Output:** Component code, screen implementations, tests

### Backend-Dev-Agent
- **Assigned tasks:** 27 tasks (Node.js API, embeddings, vector DB, WebSocket)
- **Skills:** Node.js, PostgreSQL, pgvector, Redis, WebSocket, LLM APIs
- **Tools:** File editing, npm, database migrations
- **Output:** API endpoints, services, migrations, tests

### QA-Agent
- **Assigned tasks:** 5 tasks (unit tests, integration tests, E2E, accessibility)
- **Skills:** Jest, Detox, accessibility testing, performance profiling
- **Tools:** Test runners, profiling tools
- **Output:** Test suites, bug reports, performance metrics

### Content-Agent
- **Assigned tasks:** 6 tasks (quiz questions, meditation scripts, copy)
- **Skills:** Content writing, UX copy, meditation guidance
- **Tools:** File editing
- **Output:** Markdown files, JSON content files

## Task Selection Algorithm

1. **Fetch project data:** GET http://localhost:3001/api/projects/3
2. **Find ready tasks:** state === 'todo' AND all dependencies completed
3. **Sort by priority:** critical > high > medium > low
4. **Check agent availability:** Don't spawn >3 agents of same type concurrently
5. **Spawn agent** with full context (task ID, dependencies, reference materials)

## Task Dependencies

Tasks have a \`dependencies\` array with task IDs that must be completed first.

Example:
- ORA-002 depends on ORA-001 (home screen design must exist before coding)
- ORA-012 depends on ORA-011 (architecture doc must exist before embeddings)

Never spawn an agent for a task with unmet dependencies!

## Agent Spawning Template

\`\`\`javascript
sessions_spawn({
  agentId: "main",
  label: "iOS-Dev-Agent: Build Home Screen Component",
  model: "anthropic/claude-opus-4-6",
  thinking: "high",
  task: \`You are an iOS-Dev-Agent working on Ora AI (Project ID 3).

TASK: ORA-002 - Build Home Screen component

CONTEXT:
- Project root: /Users/matthew/Desktop/Feb26/ora-ai/
- Reference design: ORA-001 (completed)
- HomeScreen.png: /Users/matthew/Desktop/Feb26/ora-ai/HomeScreen.png
- Brand assets: /Users/matthew/Desktop/Feb26/Ora 2/

REQUIREMENTS:
[Paste task description from database]

ACCEPTANCE CRITERIA:
[Paste acceptance criteria]

FILE TO CREATE:
src/screens/HomeScreen.tsx

DEPENDENCIES:
- ORA-001 (design) - ✅ COMPLETED

After completing, update task state:
PATCH http://localhost:3001/api/tasks/ORA-002
{ "state": "complete", "actual_hours": X }

Then post completion to activity log:
POST http://localhost:3001/api/activity
{ "project_id": 3, "agent": "iOS-Dev-Agent", "task_id": "ORA-002", "message": "Home screen component complete", "type": "completion" }
\`,
  runTimeoutSeconds: 3600,
  cleanup: "keep"
});
\`\`\`

## Progress Monitoring

Every 5 minutes:
1. Check active agents (GET http://localhost:3001/api/projects/3/agents)
2. Check task states
3. Identify completed tasks → spawn next tasks in dependency chain
4. Report progress to user if significant milestone reached

## Reporting

Send Telegram updates when:
- Phase completed (e.g., "Phase 1: Foundation & Design complete! ✅")
- Critical task completed (e.g., "Multi-vector architecture complete - chat work can begin")
- Blockers detected (e.g., "ORA-015 waiting 3 hours for ORA-014 completion")
- Daily summary (e.g., "Day 3 complete: 24/96 tasks done (25%), 5 agents working")

## Error Handling

If an agent fails:
1. Mark task as 'blocked'
2. Log error to activity_log
3. Notify user with details
4. Retry with different model or spawn QA-Agent to investigate

## Prioritization

Phase 1 tasks (Days 1-2) are highest priority:
- ORA-011 (Architecture) - CRITICAL
- ORA-050 (Auth Backend) - CRITICAL
- ORA-066 (Brand Assets) - CRITICAL
- ORA-001 (Home Design) - CRITICAL
- ORA-053 (Quiz Questions) - CRITICAL

Start with these 5 tasks immediately!

## Success Metrics

Track and report:
- Tasks completed / total
- Hours actual / estimated
- Tasks per phase
- Agent utilization (how many of each type active)
- Critical path progress (multi-vector chat chain)
- Blocker count

## Example Orchestration Flow

1. **Initial**: Spawn 5 agents for zero-dependency tasks (ORA-011, 050, 066, 001, 053)
2. **Monitor**: Check every 5 min for completions
3. **ORA-001 complete**: Spawn iOS-Dev for ORA-002 (home screen component)
4. **ORA-011 complete**: Spawn Backend-Dev for ORA-012 (embedding pipeline)
5. **Continue**: Always keep 8-12 agents active in parallel
6. **Report**: Hourly progress updates to Telegram

## API Endpoints Reference

- GET /api/projects/3 - Full project data
- GET /api/projects/3/context - Context documents
- POST /api/tasks - Create task
- PATCH /api/tasks/:id - Update task
- POST /api/agents - Register agent spawn
- PATCH /api/agents/:id/complete - Mark agent complete
- POST /api/activity - Log activity

## File Paths

- **Ora AI app:** /Users/matthew/Desktop/Feb26/ora-ai/
- **Ora AI backend:** /Users/matthew/Desktop/Feb26/ora-ai-api/
- **Brand assets:** /Users/matthew/Desktop/Feb26/Ora 2/
- **Home screen reference:** /Users/matthew/Desktop/Feb26/ora-ai/HomeScreen.png
- **Roadmap:** /Users/matthew/.openclaw/workspace/agent-swarm-template/ROADMAP.md
- **Plan:** /Users/matthew/.openclaw/workspace/agent-swarm-template/ORA_AI_COMPREHENSIVE_PLAN.md

START ORCHESTRATION. Monitor the board and spawn agents for ready tasks!
`;
    
    console.log('📄 Adding orchestrator instructions...');
    const orchResp = await postJSON('/api/projects/3/context', {
      document_type: 'orchestrator',
      title: 'Orchestrator Agent Instructions',
      content: orchestratorInstructions,
      file_path: null
    });
    console.log(`✅ Orchestrator instructions added (ID: ${orchResp.id})`);
    
    console.log('\n🎉 All context documents added successfully!');
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

addContext();
