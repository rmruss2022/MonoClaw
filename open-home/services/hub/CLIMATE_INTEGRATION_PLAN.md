# Thermostat Integration — Plan & Test Matrix

Goal: a real thermostat can be **discovered → added to a room → connected → fully
integrated** across the whole app (Climate tab, Control/device screen, dashboard count,
voice/agent, scenes), hardened and browser-verified.

## Current state (audit)

Complete (Climate tab, `localClimate.ts` + `climate.ts` + `climate.html`):
- Discover (ESPHome mDNS / Matter), onboard **with a room**, rename, move room, reconnect
  supervisor, remove.
- Control: set target (dial drag / ±), set mode (off/heat/cool/auto/fan), mode-aware action.
- Persisted to `.data/local-climate.json`; shown in `/hub/status` services.

Gaps (whole-home integration):
1. **Device visibility** — real thermostats are absent from `/devices`, so the **Control
   (House) screen** and **dashboard device count** don't see them (only the mock shows).
2. **Agent / voice + scenes** — the NLU ("set it to 68", "good night") and scenes only
   mutate the mock `thermostat_main`; a real onboarded thermostat is never driven.
3. **Hardening** — control accepts unvalidated `mode` and non-finite / out-of-range
   `targetF`; `/climate/command` doesn't validate inputs.

## Design

### 1. Device visibility (`climate.deviceRows()` → `/devices`)
- `climate.deviceRows()` returns real thermostats normalized to the `home.Device` shape
  (`type:"thermostat"`, room, icon, `state:{temp,target,mode}`).
- `/devices` merges them and, when ≥1 real thermostat exists, **hides the mock**
  `thermostat_main` so there's exactly one canonical thermostat per device. Count reflects it.

### 2. Agent / voice + scenes → real primary (`climate.syncMockToPrimary()`)
- `climate.primary()` = first real thermostat (or null).
- The NLU/scenes keep writing to the mock `thermostat_main` (the command buffer). At each
  agent/control/scene HTTP entry point we **snapshot the mock thermostat state before, and
  if it changed, mirror `{mode,targetF}` to the primary** via `localClimate.control`.
- Snapshot-diff avoids clobbering: unrelated actions (e.g. "kitchen light on") don't touch
  the thermostat, so no stray sync overwrites a dial change.

### 3. Hardening
- `localClimate.control` + `climate.control`: whitelist `mode` ∈ {off,heat,cool,auto,fan};
  reject non-finite `targetF`; clamp to `[minF,maxF]`.
- `/climate/command`: guard `set-temp` (finite number) and `set-mode` (valid mode) before
  dispatch; unknown ids return a clean hint.

## Test matrix

Integration (`test-climate.sh`, curl against a live hub):
- onboard ESPHome thermostat → appears in `/climate/state` with the chosen **room**.
- set-temp / set-mode reflect in state; mode-aware action correct.
- **Edge**: bad mode rejected; NaN / 999° clamped; unknown id → clean hint.
- `/devices` includes the real thermostat and **hides the mock** once one exists; count ok.
- Agent: `POST /agent {"text":"set the thermostat to 66"}` → primary thermostat targetF=66.
- Scene: `good_night` → primary thermostat mode/target mirrored.
- reconnect / remove work; after remove, mock reappears in `/devices`.

Browser (Playwright, desktop + iPhone 390px):
- `/climate` renders the dial; drag the ring changes target and the POST fires.
- Mode chips switch mode + arc color; ± buttons step target.
- Wizard: ESPHome → manual add → name & room → done; new thermostat appears and is selected.
- No horizontal overflow at 390px; screenshot captured.

## Acceptance
All integration assertions green, both browser flows pass with screenshots, committed to
`openhome-mvp`, looped until clean.
