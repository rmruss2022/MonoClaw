# OpenClaw Service Port Map

**Last Updated:** 2026-02-16 01:15 AM EST

## Active Services

| Port  | Service Name           | Directory Path                              | Status    |
|-------|------------------------|---------------------------------------------|-----------|
| 18790 | Voice Server           | `~/.openclaw/voice-server/`                | ✅ Running |
| 18791 | Jobs Tracker           | `~/.openclaw/workspace/jobs/`              | ✅ Running |
| 3000  | To-Do Studio (Frontend)| `~/Desktop/todo-service/frontend/`         | ✅ Running |
| 3004  | Raves (SQLite)         | `~/.openclaw/workspace/raves/`             | ✅ Running |
| 4001  | To-Do Studio (Backend) | `~/Desktop/todo-service/backend/`          | ✅ Running |
| 18794 | Token Tracker          | `~/.openclaw/workspace/tokens/`            | ✅ Running |
| 18795 | Mission Control        | `~/.openclaw/workspace/mission-control/`   | ✅ Running |
| 18796 | Activity Hub           | `~/.openclaw/workspace/activity-hub/`      | ✅ Running |
| 18797 | Moltbook               | `~/.openclaw/workspace/moltbook-dashboard/`| ✅ Running |
| 18798 | Agent Swarm Dashboard  | `~/.openclaw/workspace/agent-swarm-template/` | ✅ Running |
| 18799 | Vision Controller      | `~/.openclaw/workspace/vision-controller/` | ✅ Running |
| 18800 | Context Manager        | `~/.openclaw/workspace/context-manager/`   | ✅ Running |
| 18801 | Cannon Celebration     | `~/.openclaw/workspace/cannon/`            | ✅ Running |
| 18802 | MonoClaw Dashboard     | `~/.openclaw/workspace/MonoClaw/monoclaw-dashboard/` | ✅ Running |
| 18803 | Skill Builder          | `~/.openclaw/workspace/skill-builder/dashboard/` | ⚠️ Manual Start |
| 9000  | Vision Backend API     | `~/.openclaw/workspace/vision-controller/backend/` | ✅ Running |
| 4000  | Ora AI Backend         | `~/Desktop/Feb26/ora-ai-api/`              | ⚠️ Manual Start |
| 19006 | Ora AI Frontend        | `~/Desktop/Feb26/ora-ai/`                  | ⚠️ Manual Start |

## Deprecated/Duplicate Directories

These directories should NOT be used (duplicates):
- ❌ `~/.openclaw/workspace/monoclaw-dashboard/` (use MonoClaw/monoclaw-dashboard instead)

## Notes

- **Skill Builder** requires Next.js: Run `cd ~/.openclaw/workspace/skill-builder/dashboard && npm run dev`
- **Ora AI** services are project-specific, not always-on services
- **Vision Backend** is auto-started by the Vision Controller frontend service

## Port Range

- **18790-18809**: Reserved for OpenClaw services
- **9000-9099**: Backend APIs and specialized services  
- **4000-4099**: Project-specific backends
- **19000-19099**: Development/Expo services

## Starting All Services

```bash
# Start all auto-start services (already configured in launchd/manual starts)
cd ~/.openclaw/workspace/mission-control && node server.js &
cd ~/.openclaw/workspace/agent-swarm-template && node server.js &
cd ~/.openclaw/workspace/cannon && node server.js &
cd ~/.openclaw/workspace/vision-controller && node server.js &
```

## Checking for Port Conflicts

```bash
for port in 18790 18791 18793 18794 18795 18796 18797 18798 18799 18800 18801 18802 18803; do
  echo -n "Port $port: "
  curl -s -o /dev/null -w "%{http_code}" --max-time 1 http://localhost:$port/ && echo " ✅" || echo " ❌"
done
```
