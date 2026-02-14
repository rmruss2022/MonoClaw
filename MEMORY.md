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

## Job Search Pipeline (Active: Feb 11, 2026)

**⚠️ Friday 2/13 - Back-to-Back Interviews**:
- Traba: 11:30 AM-12:30 PM with Austin Carter (Systems Design, Google Meet)
- Cerula: 1:00 PM-2:00 PM with Ayush Mathur (30-min gap only!)

**Live Coding Stage**:
- Figure: Awaiting confirmation after Greenhouse booking (recommend Tue 2/17 10 AM or 2 PM, AI prohibited)

**Technical Rounds**:
- Gloss Genius: CoderPad pair programming (Python/medium LeetCode level), awaiting scheduling via Gem

**Pipeline**:
- PayMe/Kinetic: Project assignment coming from Jack Ablon (EOD 2/12)
- Outtake: Awaiting follow-up from Anna Healy (Integrity Power Search)
- **Fun.xyz** (NEW 2/12): Product Engineer, React/TypeScript SDK focus. Daniel Earnshaw (EO Talent) - calendly.com/daniel-eostalent/30min

**Recruiter Contacts**:
- Shirly Ribak (Rare Capital): shirly@rare-capital.com
- Holly Wendt (Figure): hwendt@figure.com
- Brianna Lechner (Gloss Genius): b.lechner@glossgenius.com
- Emily Ku (Figure): eku@figure.com

## Technical Preferences

**Voice Output**: Manual curl to voice server required for webchat (auto-hooks disabled due to chunking issues). Always post complete response text to http://127.0.0.1:18790/speak

**Cron Wake Mode**: Use "now" for time-critical jobs (not "next-heartbeat") to ensure reliable execution.

**Email Filtering**: Only announce urgent categories (jobs, appointments, financial). Silence marketing/promotional.

## System Architecture

**Gmail Integration** (Updated Feb 12, 2026):
- **Polling-based** (not push) - Every 10 minutes via cron
- **Cron ID**: `3956a4f1-f07b-4ce6-869d-5d69664debb2`
- **Why**: Push hooks caused 38 parallel processes → session store lock contention
- **Solution**: Single isolated agent processes emails sequentially
- **Model**: nvidia/moonshotai/kimi-k2.5 (free)
- **Delivery**: Urgent emails only to Telegram (5574760589)
- **Trade-off**: 10-min delay acceptable for non-critical emails

## Projects Active

**Agent Swarm Dashboard** (Feb 11, 2026)
- Status: Backend complete, validation testing in progress
- Location: `/Users/matthew/.openclaw/workspace/agent-swarm-template/`
- URL: http://localhost:3001/dashboard.html
- Stack: React + Tailwind + Express + SQLite
- Features: Kanban board, agent tracking, activity log, REST API
- Database: swarm.db (SQLite) with 4 tables
- Demo project: iOS Banking App (12 tasks, 25% complete)
- Test project: CLI Weather Dashboard (Project ID 2, awaiting task creation fix)
- Known issue: POST /api/tasks returns null (blocking validation)
- Next: Fix task API, spawn agents, test Product→Dev→QA pipeline, report via Telegram

## Projects Completed

**Daylight Energy Management** (Feb 10, 2026)
- Status: Production deployment complete
- URL: https://web-production-970f8.up.railway.app/
- Stack: Django + React + PostgreSQL + Redis + Railway
- Result: 136/136 tests passing, live data visualization working
