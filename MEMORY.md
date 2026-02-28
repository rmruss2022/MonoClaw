# Long-Term Memory

## Agent Swarm Architecture (Feb 11, 2026)

**Vision**: Distributed workforce of specialized agents working in cascade to build production products overnight.

**Core Components**:
- **Orchestrator Agent**: Maintains kanban board, spawns specialists, receives results
- **Specialized Agents**: Product, Research, Architect, Dev, QA, PM
- **Workflow**: Spawn → Complete → Update Board → Spawn Next
- **Communication**: `sessions_spawn`, `sessions_send`, agent-to-agent messaging

**Kanban States**: todo → in-progress → ready → qa → complete

**Use Case**: "Build SaaS dashboard" spawns Product Agent → Dev Agents (parallel) → QA Agent → Deploy Agent, all while user sleeps.

## Model Configuration (Feb 11, 2026)

**Default Model**: nvidia/moonshotai/kimi-k2.5
- Context: 256K tokens
- Reasoning: Enabled
- Cost: Free via NVIDIA API
- **When to use**: Default for all agents, sub-agents, hooks

**Legacy Options**:
- `anthropic/claude-sonnet-4-5` (alias: sonnet) - previous default
- `anthropic/claude-opus-4-6` (alias: opus) - for complex analysis

## Job Search Pipeline

**Status**: Active job search, multiple opportunities in pipeline
**Location**: Jobs dashboard at http://localhost:3003
**Memory**: Check daily memory files for interview details and follow-ups

## Technical Preferences

**Voice Output**: Manual curl to voice server required for webchat (auto-hooks disabled due to chunking issues). Always post complete response text to http://127.0.0.1:18790/speak

**Cron Wake Mode**: Use "now" for time-critical jobs (not "next-heartbeat") to ensure reliable execution.

**Email Filtering**: Only announce urgent categories (jobs, appointments, financial). Silence marketing/promotional.

## System Architecture

**Environment Security** (Updated Feb 20, 2026):
- **API Keys**: Stored in `~/.openclaw/.env` (600 permissions)
- **Gateway Launch**: Via wrapper script `~/.openclaw/gateway-wrapper.sh` that sources .env
- **LaunchAgent**: `~/Library/LaunchAgents/ai.openclaw.gateway.plist` - no keys exposed
- **Why**: Removed hardcoded keys from openclaw.json and plist files for security

**Gmail Integration** (Updated Feb 12, 2026):
- **Polling-based** (not push) - Every 10 minutes via cron
- **Cron ID**: `3956a4f1-f07b-4ce6-869d-5d69664debb2`
- **Why**: Push hooks caused 38 parallel processes → session store lock contention
- **Solution**: Single isolated agent processes emails sequentially
- **Model**: nvidia/moonshotai/kimi-k2.5 (free)
- **Delivery**: Urgent emails only to Telegram (5574760589)
- **Trade-off**: 10-min delay acceptable for non-critical emails

## Active Services & Dashboards

**Core Infrastructure:**
- **Voice Server** (port 18790) - Edge TTS, manual posting for webchat
- **Activity Tracker V3** (LaunchAgent) - Polls session transcripts every 5s
- **Token Tracker** (port 18791) - Cost tracking, $558.63/month current
- **ActivityHub/ActivityClaw** (port 18796) - Activity monitoring & logging
- **ContextClaw** (port 18792) - Context management

**Command & Control:**
- **Mission Control** (port 18795) - Central hub, links to all dashboards
- **MonoClaw Dashboard** (port 18802) - System overview

**Project Dashboards:**
- **Agent Swarm Dashboard** (port 18798) - Kanban board for agent orchestration
- **Jobs Dashboard** (port 3003) - Job application tracking
- **Raves Dashboard** (port 3004) - Social/events tracking
- **Moltbook Dashboard** (port 18794) - [Purpose TBD]
- **Arbitrage Scanner** (port 3005) - Prediction market arbitrage detection
- **Vision Controller** (port 18799 + backend 9000) - Gesture detection via webcam + gesture window manager (headless mode via `run_headless.py`)

**Automation:**
- **Daily Blog Generator** - Cron job at 6:00 PM, auto-generates & deploys posts
- **Gmail Scanner** - Cron job every 10 minutes, alerts urgent emails via Telegram
- **LaunchAgents** - Activity tracker, token collector, voice server

## Projects Active

**Doctor Strange Hand Lab** (Feb 21-28, 2026)
- Status: Complete, both modes working
- Location: `/Users/matthew/.openclaw/workspace/doctor-strange-hand-lab/`
- Stack: Vanilla JS + Vite + Three.js + MediaPipe HandLandmarker
- Run: `cd doctor-strange-hand-lab && npm run dev`
- Features:
  - **Arcane Shield mode**: Hand-tracked mandala with petal rosettes, star polygons, seed-of-life, glyphs, shards, particle system, UnrealBloomPass bloom
  - **Astral Wireframe mode**: GPU-deformed icosahedron following index finger, second hand pinch controls spin speed, palm rotation controls morph, pinch-then-open-palm triggers fragment explosion with shockwaves/tendrils/particle trails
  - Two-hand resonance bridge (lightning arc between hands in shield mode)
  - CSS `mix-blend-mode: screen` composites effects over webcam feed
- Architecture: `main.js` (renderer + frame loop), `handTracking.js` (MediaPipe), `shieldScene.js` (mandala), `wireframeScene.js` (artifact + explosion)

**Gesture Window Manager** (Feb 28, 2026)
- Status: Backend complete, tested and working
- Location: `/Users/matthew/.openclaw/workspace/vision-controller/`
- Run: `cd vision-controller/backend && python3 -u run_headless.py` (from Terminal.app for camera access)
- Test: `python3 test_snap.py` (interactive snap testing, no camera needed)
- Stack: Python + FastAPI + MediaPipe + OpenCV + PyObjC (Quartz + Accessibility API)
- Features:
  - Headless mode captures webcam directly via OpenCV, no browser needed
  - Point (1 finger) = select frontmost window + full screen snap
  - Peace (2 fingers) = half screen snap (hand position = left/right)
  - Four fingers = quarter screen snap (hand position = quadrant)
  - Open palm = deselect window
  - Auto-detects all monitors via Quartz CGDisplayBounds
  - Moves/resizes windows via macOS Accessibility API (AXUIElement)
- Display layout: External 1920x1080 at (-1920,0) LEFT, MacBook 1512x982 at (0,0) RIGHT
- Permissions: Camera + Accessibility required in System Settings
- New files: `position_tracker.py`, `window_manager.py`, `window_mode_state_machine.py`, `run_headless.py`, `test_snap.py`
- Extends existing vision-controller (added `four_fingers` gesture, window mode in main.py WebSocket handler)

**Arbitrage Scanner** (Feb 17-18, 2026)
- Status: MVP complete, needs matcher.ts rewrite
- Location: `/Users/matthew/.openclaw/workspace/arbitrage-scanner/`
- URL: http://localhost:3005/dashboard.html
- Stack: TypeScript + Node.js + SQLite + React + Tailwind
- Features: Multi-platform market scanning (Polymarket, Kalshi), fuzzy event matching, arbitrage detection
- Issue: False positives in event matching (287 matches, incorrect pairs)
- Solution: Created `CODEX_PROMPT.md` with entity-extraction algorithm spec
- File to rewrite: `src/core/matcher.ts`
- Next: Feed CODEX_PROMPT.md to Cursor for matcher rewrite

**Daily Blog System** (Feb 17, 2026)
- Status: Production, auto-generating posts
- Location: `/Users/matthew/.openclaw/workspace/matts-claw-blog/`
- Schedule: Cron job at 6:00 PM daily
- Features: Reads memory files, generates blog post, deploys to GitHub → Vercel
- Posts: 11+ total published
- Format: JSON posts with title, content, tags, image prompts

**Ora Health Community Redesign** (Feb 18, 2026)
- Status: Ready for implementation
- Location: `/Users/matthew/.openclaw/workspace/ora-health/`
- App root: `/Users/matthew/.openclaw/workspace/ora-health/ora-health/`
- Prompt: `CODEX_COMMUNITY_PROMPT.md` (8KB design spec)
- Design: Single scrollable screen with letters at top + unified feed
- Next: Open in Cursor, feed prompt to implement redesign

## Projects On Hold

**Agent Swarm Dashboard** (Feb 11, 2026)
- Status: Backend complete, paused after validation issues
- Location: `/Users/matthew/.openclaw/workspace/agent-swarm-template/`
- URL: http://localhost:18798/dashboard.html
- Known issue: POST /api/tasks returns null
- Next: Resume when needed for agent orchestration work

## Projects Completed

**Daylight Energy Management** (Feb 10, 2026)
- Status: Production deployment complete
- URL: https://web-production-970f8.up.railway.app/
- Stack: Django + React + PostgreSQL + Redis + Railway
- Result: 136/136 tests passing, live data visualization working
