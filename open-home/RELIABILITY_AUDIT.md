Great stack. You’ve already solved the hard audio UX issues; what’s left is mostly **failure isolation + self-healing**.  
Here’s the reliability audit, prioritized for “Echo-like consistency.”

---

## P0 (fix first): things that currently cause flaky/missed/false behavior

### 1) **Mic failures kill the whole client**
**Where:** `read_samples()` raises `RuntimeError`; `main()` has no inner recovery, so process exits.

**Why it hurts:** One USB hiccup / `arecord` exit = dead assistant until service restart.

**Fix:**
- Wrap the wake loop in a mic-supervisor retry block.
- On read timeout/EOF, terminate mic process and reopen with backoff.
- Add read timeout (via `select`) so stalled pipe doesn’t block forever.

---

### 2) **STT errors are treated as “user said nothing”**
**Where:** `transcribe()` returns `""` on HTTP/network errors; `is_nonspeech("")` ends conversation silently.

**Why it hurts:** Network blip looks like ignored user speech.

**Fix:**
- Make `transcribe()` return tri-state: `{ok,text}` vs `{error}`.
- On STT error: speak short failure (“I’m having trouble hearing right now.”), then exit turn.
- Keep empty text only for true no-speech cases.

---

### 3) **Timeout budget mismatch creates ghost/late actions**
**Where:** client `/agent` timeout = 30s; hub `ccut()` = 45s + web search (some fetches no timeout).

**Why it hurts:** Client times out and tells user hub failed, but hub may still execute actions later.

**Fix:**
- Hard end-to-end budget, e.g. 10–12s total for `/agent`.
- Reduce `ccut` timeout (< client timeout, e.g. 7–8s).
- Add timeouts to *all* web fetches (open-meteo + duckduckgo currently unbounded).
- If over budget, skip second LLM roundtrip and return explicit failure.

---

### 4) **Music pause/resume state is wrong in edge cases**
**Where:** `pause_music()` pauses Spotify + SC, but `resume_music()` resumes only Spotify.

**Why it hurts:** If SoundCloud was playing, it may never resume. Also stale `music` cache can cause accidental autoplay on resume.

**Fix:**
- Capture **exact playback snapshot at wake** (`spotify_playing`, `sc_playing`) with a forced fresh check.
- Pause only active sources.
- Resume exactly those active sources, unless user command explicitly paused/stopped.
- Don’t rely on cached `music_playing()` for resume decisions.

---

### 5) **Hub action result checks are too optimistic**
**Where:** `_hub_set_color()` returns `True` without checking HTTP status (401/500 still treated success).

**Why it hurts:** Assistant says “Okay…” but nothing happened.

**Fix:**
- Centralize hub HTTP helper with:
  - status check
  - 401 re-login retry
  - JSON parse guard
- Use it for `_hub_set_color`, room power, party, etc.

---

## P1 (next): latency spikes and hidden command failures

### 6) **Wake loop can stall on `music_playing()` subprocess polls**
**Where:** `music_playing()` runs `soloist ctl now`/`sc-ctl status` with `timeout=2` from hot wake loop.

**Why it hurts:** 2s stalls in detection path = delayed/missed wake behavior under command slowness.

**Fix:**
- Move music-state polling to background thread with cached atomic state.
- Wake loop reads cache only (non-blocking).
- If keeping inline, cut timeout to ~200–300ms and never block detection.

---

### 7) **`pw-record`/`arecord` stderr pipe can block child**
**Where:** `open_mic()` uses `stderr=PIPE`, never drained.

**Why it hurts:** If stderr fills, capture can freeze.

**Fix:** set `stderr=subprocess.DEVNULL` (or dedicated drain thread).

---

### 8) **Keepalive restart can leak orphaned child processes**
**Where:** `_start_keepalive()` restarts on exception but doesn’t always `wait()` old process.

**Why it hurts:** Over time: zombie/leaked `pw-play`, unpredictable audio behavior.

**Fix:**
- Keep process handle, on exception `terminate/kill + wait`.
- Add heartbeat timestamp; main thread watchdog restarts keepalive if stale.

---

### 9) **No automatic BT speaker recovery path**
**Where:** playback failures are logged but no reconnect attempt.

**Why it hurts:** Temporary BT disconnect = persistent “assistant is speaking into void.”

**Fix:**
- On consecutive `pw-play` failures: run `bluetoothctl connect <MAC>`, restart keepalive, retry playback once.
- Add periodic sink presence check (`wpctl status` contains `SPK_NODE`).

---

### 10) **Command wrappers in hub hide failures**
**Where:** `run()` returns `""` on error; `doMusic()` still returns success phrases.

**Why it hurts:** False confirmations (“paused”) when command failed.

**Fix:**
- Return `{ok, code, stdout, stderr}` from `run`.
- `doMusic()` replies based on `ok`.
- For `soloist` failure: one auto-retry after `systemctl --user restart soloist`.

---

## P2 (polish but meaningful)

### 11) Replace `time.time()` timers with `time.monotonic()`
Avoid NTP clock jumps affecting grace/silence timing.

### 12) Better `/agent` fallback semantics
If LLM JSON parse fails, do **not** default to “Okay.”  
Return explicit error or fallback deterministic intent parser for core commands.

### 13) Add explicit state machine enum + logs
`IDLE -> WAKE_ACK -> LISTENING -> THINKING -> SPEAKING -> IDLE`  
This makes race/edge debugging much easier and prevents accidental resume paths.

---

## Minimal concrete patch set to do this week
1. Mic supervisor + read timeout + stderr DEVNULL.  
2. STT tri-state error handling.  
3. Unified deadline/timeout budget across client+hub.  
4. Source-aware pause/resume snapshot logic.  
5. Robust hub request helper (status + 401 retry).  
6. Command result truthfulness in `voiceagent.ts`.

If you want, I can draft exact drop-in code for the top 3 (`read_samples` timeout/supervisor, STT tri-state, and source-aware pause/resume) in your current file structure.
