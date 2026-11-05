# services/hub

The brain of open-home: HTTP/WebSocket API, the event bus, the rules engine, and the
agent loop that runs the home.

## Run

```bash
npm install          # from repo root
npm run dev --workspace services/hub
# → http://localhost:4700/health
```

Endpoints (skeleton):
- `GET /health` — liveness
- `GET /devices` — device registry (stub until device-gateway is wired)
- `GET /events/recent` — recent event bus activity

## Config
| Env | Default | Purpose |
|-----|---------|---------|
| `OPEN_HOME_PORT` | `4700` | HTTP port |
| `OPEN_HOME_MODEL` | `ollama:llama3.1 (local)` | Agent model. Set to a cloud model only to opt in. |

## Next
See [`../../ROADMAP.md`](../../ROADMAP.md) Phase 1: MQTT bus, first camera adapter,
storage, and the local agent tool loop.
