# 🦞 Agent Swarm with Discord Integration

Multi-agent orchestration system with real-time Discord communication and human-in-the-loop oversight.

## What This Is

An **autonomous agent swarm** that:
- Breaks down projects into tasks
- Spawns specialized AI agents (backend, frontend, QA, etc.)
- Coordinates work via **Discord channels**
- Lets you **watch and guide** agents in real-time
- Manages Kanban board automatically
- Reports progress and asks for help when stuck

## Key Features

✅ **Discord-First Communication**
- Auto-creates channels for each project
- Agents post status updates every 15 min
- Agents ask questions when blocked
- Humans can intervene at any time
- Full transparency (watch agents collaborate)

✅ **Multi-Agent Orchestration**
- Orchestrator manages Kanban board
- Spawns specialized worker agents
- Handles dependencies and parallelization
- Retries failures with context
- Escalates blockers to humans

✅ **Human-in-the-Loop**
- Monitor from Discord mobile app
- Guide agents via @mentions
- Approve major decisions
- Intervene when needed
- Stay in control

## Architecture

```
┌─────────────────────────────────────────────┐
│           Discord Server                    │
│  📋 #project-board  💬 #general            │
│  🔧 #backend        🎨 #frontend           │
│  🧪 #qa             🚨 #alerts             │
│  📊 #status         ❓ #questions           │
└─────────────────────────────────────────────┘
         ↑                    ↑
         │ post/read          │
         │                    │
┌────────┴────────┐    ┌──────┴──────┐
│  Orchestrator   │    │   Worker    │
│     Agent       │───→│   Agents    │
│  (coordinates)  │    │  (execute)  │
└─────────────────┘    └─────────────┘
         ↑                    ↑
         │                    │
         └────────┬───────────┘
                  │
         ┌────────┴────────┐
         │  Server API     │
         │  (SQLite +      │
         │   Express)      │
         └─────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd ~/.openclaw/workspace/agent-swarm-template
npm install
```

### 2. Setup Discord

```bash
npm run setup
```

This will guide you through:
- Creating a Discord application
- Adding a bot
- Inviting bot to your server
- Getting bot token and server ID

### 3. Start Server

```bash
npm start
# or
node server-enhanced.js
```

Server runs on **http://localhost:18798**

### 4. Open Dashboard

Open `dashboard.html` in your browser or visit http://localhost:18798

### 5. Create Project

1. Click "New Project"
2. Enter project details
3. Click "Create"
4. **Discord channels are auto-created!**

### 6. Watch in Discord

Open Discord, go to your server. You'll see a new category with channels:
- 📋 project-board
- 💬 general
- 🔧 backend
- 🎨 frontend
- 🧪 qa
- 🚨 alerts
- 📊 status
- ❓ questions
- 📝 decisions

## How It Works

### Creating a Project

When you create a project:

1. **Server creates database entry**
2. **Discord bot creates channels** (category + 9 channels)
3. **Webhooks are created** for each channel
4. **Discord metadata saved** to database
5. **Initial message posted** to #project-board

### Spawning Orchestrator

The orchestrator is the "manager" agent:

```javascript
sessions_spawn({
  task: `[Full orchestrator task from orchestrator-agent-task.md]
  
  // Includes:
  // - Discord webhooks for all channels
  // - Server API endpoints
  // - Main coordination loop
  // - Agent spawning logic
  // - Discord monitoring
  `,
  label: "Orchestrator - Project Name",
  model: "anthropic/claude-sonnet-4-5",
  thinking: "high",
  cleanup: "keep",
  runTimeoutSeconds: 14400  // 4 hours
})
```

### Orchestrator Loop

```
1. Check Discord #alerts for urgent issues
2. Check Discord #questions for @orchestrator mentions
3. Fetch current project state from API
4. Process completed tasks (move through Kanban)
5. Identify ready tasks (dependencies met)
6. Spawn worker agents for ready tasks (max 3 parallel)
7. Post Kanban update to Discord #project-board
8. Check for @matthew mentions (human intervention)
9. Sleep 60s, repeat
```

### Worker Agents

Each task gets a specialized agent:

- **Backend Agent** - Writes backend code (Python, Node, etc.)
- **Frontend Agent** - Builds UI components (React, Vue, etc.)
- **QA Agent** - Tests code, reports bugs
- **DevOps Agent** - Deployment scripts, infrastructure
- **Database Agent** - Schema design, migrations

Worker agents:
- Post status to Discord every 15 min
- Ask questions in #questions when blocked
- Collaborate via @mentions
- Report completion with summary

### Discord Communication Examples

**Agent Status Update:**
```
[#status] 🔧 Backend Agent: Auth API - 60% complete
          Working on JWT token generation
```

**Agent Question:**
```
[#questions] ❓ Backend Agent: @orchestrator
             Should I use PostgreSQL or MongoDB for user storage?
```

**Orchestrator Response:**
```
[#questions] @backend-agent Use PostgreSQL.
             We need relational data for dashboard queries.
```

**Human Intervention:**
```
[#general] @orchestrator PAUSE all agents.
           @backend-agent Post your current schema to #backend.
           I need to review before you continue.
```

**Orchestrator Acknowledgment:**
```
[#general] ⏸️  All agents paused.
           Waiting for @matthew review.
```

**Completion Report:**
```
[#status] ✅ Auth API Complete!
          
          Files:
          • output/backend/auth.py
          • output/backend/test_auth.py
          
          Endpoints:
          • POST /auth/login
          • POST /auth/logout
          • POST /auth/refresh
          
          Tests: 12/12 passing ✓
          
          Ready for frontend integration
```

## API Endpoints

### Projects

```bash
# List all projects
GET /api/projects

# Get project details
GET /api/projects/:id

# Create project (with Discord)
POST /api/projects
{
  "name": "SaaS Dashboard",
  "description": "Full-stack analytics dashboard",
  "createDiscordChannels": true  // default: true
}
```

### Tasks

```bash
# Create task (creates Discord thread)
POST /api/tasks
{
  "project_id": 1,
  "title": "Build auth API",
  "description": "JWT authentication endpoints",
  "priority": "high",
  "estimated_hours": 2,
  "tags": ["backend"]
}

# Update task state (posts to Discord)
POST /api/tasks/:id/update-state
{ "state": "in-progress" }
```

### Discord

```bash
# Send Discord message (for agents)
POST /api/discord/message
{
  "project_id": 1,
  "channel_type": "status",  // board|status|general|questions|alerts|backend|frontend|qa
  "content": "Message text",
  "username": "Agent Name",
  "embeds": [...]  // optional
}

# Read Discord messages
GET /api/discord/messages/:channel_id?limit=50
```

## File Structure

```
agent-swarm-template/
├── server-enhanced.js              # Main server with Discord
├── discord-bot.js                  # Discord API wrapper
├── orchestrator-agent-task.md      # Orchestrator prompt template
├── worker-agent-template.md        # Worker agent prompt template
├── setup-discord.sh                # Interactive setup script
├── package.json                    # Dependencies
├── dashboard.html                  # Web UI
├── swarm.db                        # SQLite database
└── .env                           # Discord credentials (gitignored)
```

## Environment Variables

```bash
# .env file (created by setup-discord.sh)
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id_here
PORT=18798
```

## Agent Templates

### Spawning Orchestrator

Use `orchestrator-agent-task.md` as a template, replacing:
- `{PROJECT_NAME}`
- `{PROJECT_ID}`
- `{PROJECT_DESCRIPTION}`
- `{DISCORD_CATEGORY_ID}`
- `{DISCORD_CHANNELS_JSON}`
- `{DISCORD_WEBHOOKS_JSON}`

### Spawning Worker Agents

Use `worker-agent-template.md` as a template, replacing:
- `{AGENT_SPECIALTY}` (Backend, Frontend, QA, etc.)
- `{PROJECT_ID}`
- `{TASK_ID}`
- `{TASK_TITLE}`
- `{TASK_DESCRIPTION}`
- `{DISCORD_WEBHOOKS}`
- `{CONTEXT_FILES_LIST}`
- `{OUTPUT_PATH}`
- `{SUCCESS_CRITERIA}`

## Benefits

### For Agents
✅ Clear communication channels
✅ Explicit coordination protocol
✅ Human guidance when stuck
✅ Peer review from other agents
✅ Shared context in Discord

### For Humans
✅ Full transparency (see everything)
✅ Mobile oversight (Discord app)
✅ Intervene at any time
✅ Guide decisions
✅ Learn how agents think

### For Projects
✅ Faster coordination (no polling lag)
✅ Better collaboration
✅ Fewer mistakes (peer review)
✅ Audit trail (Discord history)
✅ Resumable (all state in DB + Discord)

## Troubleshooting

### Discord channels not created

Check:
1. Bot has "Manage Channels" permission
2. Bot has "Manage Webhooks" permission
3. Bot is in your server
4. DISCORD_BOT_TOKEN and DISCORD_GUILD_ID are correct in .env

### Agents not posting to Discord

Check:
1. Webhooks are saved in database (check Discord columns in projects table)
2. Server is running
3. Agent task includes Discord webhook URLs
4. Network connectivity

### Bot not responding

Check:
1. Bot token is valid
2. Bot has "Read Messages" permission
3. Bot can see the channels
4. MESSAGE CONTENT INTENT is enabled in Discord Developer Portal

## Production Tips

1. **Use a dedicated Discord server** for agent swarms (not your personal server)
2. **Create separate servers** for different projects (keeps channels organized)
3. **Set up roles** for agents (Backend Agent, Frontend Agent, etc.) for easy @mentions
4. **Archive projects** when done (delete Discord category)
5. **Monitor token usage** (lots of agents = lots of API calls)
6. **Set reasonable timeouts** (don't let agents run forever)
7. **Review logs** in Discord regularly

## Future Enhancements

- [ ] Voice channels (agents with TTS)
- [ ] Slash commands for Discord control
- [ ] Agent voting on decisions
- [ ] Automatic code review
- [ ] Deploy buttons in Discord
- [ ] Cost tracking per project
- [ ] Multi-project orchestrator

## Credits

Built for OpenClaw by Matthew Russell (@rmruss2022)

Inspired by:
- Human software teams (Slack/Discord coordination)
- Kanban methodology
- Agent swarm research

## License

MIT

---

**Ready to build with AI agents?** 🦞

Run `npm run setup` to get started!
