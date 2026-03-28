# 🏥 AuthAgent — Autonomous Prior Authorization Engine

> **The first fully agentic prior authorization platform built for providers.**
> Not a workflow tool. Not a dashboard. An agent that does the work.

---

## What Is This?

AuthAgent is an AI-powered prior authorization (PA) system that autonomously:

1. **Detects** which orders require prior authorization
2. **Drafts** clinical justification letters using patient chart data
3. **Predicts** approval probability per payer before submission
4. **Submits** to payer portals and clearinghouses
5. **Monitors** status and auto-appeals denials with payer-specific argumentation

**The market gap:** Every existing tool (Waystar, Cohere, Rhyme) automates submission workflow. None of them autonomously draft clinical justifications, predict denial likelihood per payer, or run fully autonomous appeals. That's the entire business.

---

## Quick Start

```bash
git clone <repo-url>
cd auth-agent
npm install
cp .env.example .env        # add your Anthropic API key (optional for demo)
npm run docker:up            # starts Postgres + Redis
npm run migrate              # creates database schema
npm run seed                 # loads 20 demo PA scenarios
npm run dev                  # starts API (:3011) + UI (:3010)
# Open http://localhost:3010
```

> Demo mode is enabled by default (`DEMO_MODE=true` in `.env`). All AI features work with synthetic data — no real PHI, no external API calls.

---

## Project Structure

```
auth-agent/
├── packages/
│   ├── api/                 ← Express backend (port 3011)
│   │   └── src/
│   │       ├── agents/      ← AI agents (extract, justify, score, appeal)
│   │       ├── routes/      ← REST API endpoints
│   │       ├── fhir/        ← CoverMyMeds integration
│   │       ├── jobs/        ← Background status poller
│   │       ├── services/    ← Business logic (status machine, payer service)
│   │       ├── migrations/  ← PostgreSQL schema
│   │       └── seeds/       ← Demo data seeder
│   └── ui/                  ← Next.js 14 frontend (port 3010)
│       ├── app/             ← Pages (dashboard, new PA wizard, PA detail, payers, intelligence)
│       ├── components/      ← Shared UI components
│       └── lib/             ← API client + React Query hooks
├── data/samples/            ← 10 synthetic clinical note samples
├── docs/                    ← Business plan, roadmap, demo script
└── docker-compose.yml       ← Postgres + Redis
```

---

## The Vision in One Paragraph

A physician orders an MRI. AuthAgent detects it requires PA from United. It reads the patient's chart, sees they have lower back pain with 6 weeks of failed conservative treatment, and knows United requires documentation of failed PT before approving lumbar MRIs. It drafts the justification letter citing that specific clinical history. It scores the approval probability at 87% based on historical United patterns for this code. It submits. If denied, it auto-generates an appeal citing the exact MCG criteria and payer policy language that wins this denial type. The physician did nothing except order the MRI.

---

## Key Files to Read First

1. `docs/BUSINESS_PLAN.md` — Why this business, market size, how we make money
2. `docs/MVP_SCOPE.md` — The exact thing we're building right now
3. `docs/DATA_STRATEGY.md` — How we get real data without EHR integrations yet
4. `docs/ROADMAP.md` — What comes after the MVP

---

*Built by Claw + Matthew, starting March 2026.*
