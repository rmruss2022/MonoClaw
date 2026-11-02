# Foreman — per-project agents, scheduled jobs, a supervising "doctor", and a UI

> Architecture spec for Matthew's idea (Nov 1, 2026): *"agents per project, sent
> through Telegram channels; a bot-doctor schedules each job and makes sure the
> agents stay on track and complete them; see it all in a UI for success +
> debugging."* This documents what OpenClaw already gives us, the thin layer to
> build (Foreman), and the recommended defaults. Nothing is built yet — this is
> the plan to green-light.

## TL;DR
~70% of this already exists natively in OpenClaw. The missing piece is an
**orchestration + supervision layer** ("Foreman") that turns messages-in-channels
into tracked, scheduled, verified jobs — plus a dashboard.

## Execution substrate: SUBAGENTS, not per-project configured agents (decided Nov 2)
A job = a **spawned subagent session**, not a standing configured agent. This is the
better model and what Foreman uses:
- `sessions_spawn(cwd=<project repo>, label="<project>:<jobId>", cleanup:keep,
  mode:run)` launches a background worker with its **own session key**.
- It is **tracked** (`subagents list` / `sessions_list`), **saved** (`cleanup:keep`
  persists the transcript), and **revisited** (`sessions_history` to read, 
  `sessions_send` to continue). That is the trackable/saveable/revisitable unit — free.
- Subagents **don't need their own bot or Telegram channel**; they only need a repo
  `cwd`. This dissolves the Telegram routing fork below for most projects.

**Configured agents (atlas/ora/builder…) stay OPTIONAL** — use one only when a
project wants a *persistent identity* with its own standing channel/brain. Default
is: Foreman spawns a subagent into the project's repo per job.

**Knobs to tune** (`agents.defaults.subagents`): currently `maxConcurrent: 8`
(≤8 jobs run at once) and `archiveAfterMinutes: 60` (a run drops off the *active*
list after 60 min — the saved transcript still persists; raise this for long jobs).

## What already exists (native — do NOT rebuild)
- **Agents per project** — isolated agentIds each with their own workspace/brain.
  Today: `main`, `sage` (career-coach), `atlas` (tech-lead), `ora` (ora-health),
  `builder`. Config: `agents.list[]` (`id`, `workspace`, `agentDir`, `model`).
- **A Telegram channel per agent** — separate bot accounts already routed to their
  agent: `ora`, `atlas`, `raveplanner`, `builder`, `default`
  (`channels.telegram.accounts.*`). So "send a project agent through its own
  channel" already works via account→agent routing.
- **Routing bindings** — `peer.kind`/`peer.id` → agent, incl. Telegram **forum
  topics** (`agent:main:telegram:group:-100…:topic:42`). This is how one bot +
  many topics can each hit a different agent. (See docs: channels/channel-routing.)
- **Scheduler** — the native `cron` tool schedules jobs, runs isolated agent turns,
  and delivers results to a Telegram channel.
- **The "doctor" pattern** — Night Sweep's gated pipeline (gather → plan →
  implement → **doctor verifies (tsc / ast / health-check)** → commit → deploy →
  escalate on fail) is exactly the supervisor model. Reuse its doctors.
- **A dormant UI** — the Agent Swarm dashboard (port 18798) was built as a kanban
  for agent orchestration; revive/replace it as the Foreman UI.

## The gap to build: Foreman
A thin Node/Python service (loopback port + bedrock tunnel at
`foreman.bedrock.casa`) that owns a **job store** and a **supervision loop**.

### Components
1. **Project roster** — `foreman/projects.json`: `{id, agentId, telegram: {account|
   group+topic}, repoDir, deployCmd, doctorCmd}` per project. Seed from the existing
   5 agents; add `creator-cut`, `openhome`, `nightbloom`(recilia), `slipstream`,
   `rolodex`, `tripsync` as agents (mirror the atlas/ora config block).
2. **Job intake** — a message in a project's channel/topic becomes a **job**
   (`id, project, text, status=queued, created, by`). Captured via the OpenClaw
   message hook or a Foreman-owned inbound webhook; simplest v1 = a `/job <text>`
   convention Foreman watches.
3. **Dispatch + schedule** — Foreman **spawns a subagent** for the job
   (`sessions_spawn`, `cwd`=project repo, `label`=`<project>:<jobId>`, `cleanup:keep`,
   `mode:run`), moving it `queued → running`. The subagent's session key is stored on
   the job so it can be tracked/resumed. Scheduled jobs use the native cron
   (`schedule.at`/`cron`) which fires the same spawn.
4. **Doctor (the supervisor)** — on completion (or a timeout heartbeat) Foreman runs
   the project's `doctorCmd` (tsc / build / health-check), marks `done`/`failed`,
   **nudges** stuck/idle agents, and **escalates to Matthew** on failure or stall.
   Reuses `nightsweep` doctors.
5. **UI** (`foreman.bedrock.casa`) — per-project lanes (kanban), job states
   (queued/running/done/failed), live logs, doctor verdicts, timings, and a
   "re-run / nudge / cancel" control. Success + debugging in one view.

### Job lifecycle
`queued → dispatched → running → (doctor) → done | failed | stalled`
- `stalled` = no agent progress within N min → Foreman nudges, then escalates.
- every transition is logged with timestamp + agent/session id for debugging.

### Data model (v1: sqlite `foreman/data/foreman.db`)
- `projects(id, agent_id, channel, repo_dir, doctor_cmd, deploy_cmd)`
- `jobs(id, project_id, text, status, session_key, created, started, finished,
   doctor_verdict, error, created_by)`
- `job_events(id, job_id, ts, kind, detail)`  — the debug timeline.

## Telegram mapping (mostly moot under the subagent model)
Since jobs are subagents (no per-project bot needed), you can drive everything from
**one chat** and watch lanes in the UI. Optional nicety if you still want per-project
threads:
- **(A) One "Claw Projects" supergroup + one forum topic per project** — single bot,
  routed to each agent by topic binding. Cleanest: all projects in one chat, one
  place to watch, trivial to add a project. **← recommended.**
- (B) Separate bot per project (today's model) — works, but many bots/tokens/chats
  to juggle and a new bot per new project.
- (C) Hybrid — supergroup+topics for most, dedicated bots for high-traffic ones
  (openhome, ora).

## Build phases
- **Phase 1 — DONE (Nov 2):** live per-project kanban in Dash (`dash.bedrock.casa`,
  bottom) reading OpenClaw's `subagent_runs` (read-only) via `/api/foreman` in
  `portfolio/server.py`; roster = `foreman/projects.json` (all ~11 projects);
  jobs lane by the `slug:jobid` label convention; running/queued/done/failed
  counts; 2.5s poll; click-to-expand.
- **Phase 2 — DONE (Nov 2): the doctor + intake.**
  - **Doctor** = `foreman/doctor.py`, a ~12s poll loop (systemd
    `foreman-doctor.service`, unit versioned at `foreman/foreman-doctor.service`).
    On each finished job it runs that project's `doctorCmd` (from the roster) in
    its `repoDir`, once per `run_id`, and writes a verdict to
    `foreman/data/verdicts.json` (`{ok: true|false|null, note, …}`). The Dash
    endpoint merges verdicts → each card shows **✓ verified / ✗ <reason> /
    · checking…**; `ok:null` = skipped (no badge), projects with no `doctorCmd`
    are never badged. Read-only on the OpenClaw DB; never writes it.
  - **Intake** = the `job <project>: <task>` convention. `foreman/job.py`
    validates the project against the roster, mints the canonical
    `slug:jobid` label + repo cwd, and the agent spawns the subagent
    (`mode=run, cleanup=keep`). Drive everything from one chat; watch lanes light up.
- **Phase 3 (next):** SLAs/stall-nudging, retries + "re-run/nudge/cancel" controls
  on the cards, auth on the dashboard, optional per-project deploy hooks, metrics,
  and a Telegram-topic-per-project intake (the supergroup option above).

## Default I'll proceed with unless told otherwise
**Subagent-first**: Foreman spawns a tracked subagent per job into the project repo
(no per-project bots). Drive from one chat; watch lanes in the UI. Build **Phase 1**
first: job store + spawn/dispatch + doctor + UI, proven on 2-3 real repos
(creator-cut / tripsync / openhome). Say "build foreman" to start.

## Native references
- docs/channels/channel-routing.md (bindings, topic session keys)
- docs/agent-runtime-architecture.md ; agents.list[] config
- `cron` tool (scheduler) ; `nightsweep/` (doctor pattern) ; Agent Swarm dashboard :18798
