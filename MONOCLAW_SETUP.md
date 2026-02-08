# MonoClaw Setup Complete 🦞

**GitHub Repo:** https://github.com/rmruss2022/MonoClaw

---

## ✅ What's Done

### 1. Monorepo Created
- Removed nested `.git` directories from `activity-hub/` and `matts-claw-blog/`
- Combined everything into single repo
- Initial commit with 103 files, 20,247 insertions
- Pushed to GitHub successfully

### 2. Ora Health Cloned
- Cloned from: https://github.com/rmruss2022/ora-health-26
- Location: `/Users/matthew/.openclaw/workspace/ora-health/`
- Read project docs - it's a wellness platform using our existing infrastructure

---

## 🔧 Next Steps

### Vercel Configuration (MANUAL)

Your blog needs to be reconfigured in Vercel since it's now in a subdirectory:

1. Go to: https://vercel.com/dashboard
2. Open your `matts-claw-blog` project
3. Go to **Settings** → **General** → **Root Directory**
4. Set to: `matts-claw-blog`
5. Save and redeploy

**Why:** Vercel needs to know the blog is now at `matts-claw-blog/` in the MonoClaw repo, not at the root.

**Alternative:** You can also set this via `vercel.json` in the root of MonoClaw:
```json
{
  "builds": [
    {
      "src": "matts-claw-blog/package.json",
      "use": "@vercel/next",
      "config": {
        "rootDirectory": "matts-claw-blog"
      }
    }
  ]
}
```

### Update GitHub Remote for Blog

The old `matts-claw-blog` repo on GitHub still exists. Options:
1. **Archive it** - Keep for history but point Vercel to MonoClaw
2. **Delete it** - Clean slate, everything in MonoClaw now
3. **Keep both** - MonoClaw as source of truth, old repo as backup

---

## 📊 Ora Health Overview

**What it is:** AI-powered wellness platform (mental health, career tracking, social connection)

**Current State:**
- Has detailed implementation docs
- Uses our same infrastructure (Mission Control, Job Tracker, Voice Server, etc.)
- Adds wellness features: mood tracking, meditation timers, journal integration
- Already has frontend (`ora-health/`) and API (`ora-health-api/`, `shadow-ai-api/`)

**Phase 2 Features (In Progress):**
- Meditation timer
- Mood tracking
- Journal integration
- Sleep analysis

**Tech Stack:**
- Frontend: React/Next.js
- Backend: Express APIs
- AI: OpenClaw (Kimi K2.5 + Claude)
- Voice: Edge TTS

---

## 🤖 Ready for Sub-Agent

I can spawn a sub-agent to work on Ora Health. It will:
1. Review the existing codebase
2. Set up the frontend and APIs
3. Integrate with our current dashboards
4. Build out Phase 2 wellness features
5. Create documentation

**Command to spawn:**
```
sessions_spawn with task describing Ora Health goals
```

---

## 📝 Files in Workspace

```
~/.openclaw/workspace/
├── MonoClaw repo (tracked in git)
│   ├── jobs/
│   ├── raves/
│   ├── tokens/
│   ├── mission-control/
│   ├── activity-hub/
│   ├── moltbook-dashboard/
│   ├── matts-claw-blog/
│   ├── memory/
│   └── ... (config files)
└── ora-health/ (separate git repo - not yet added to MonoClaw)
    ├── ora-health/           (frontend)
    ├── ora-health-api/       (main API)
    ├── shadow-ai-api/        (AI services)
    └── *.md                  (documentation)
```

**Question:** Should `ora-health/` be:
1. **Separate repo** - Keep as is, manage independently
2. **Merged into MonoClaw** - Remove its `.git` and commit to MonoClaw
3. **Git submodule** - Link as submodule in MonoClaw

---

**Created:** 2026-02-07 21:59 EST  
**Status:** Ready for Vercel config + sub-agent spawn
