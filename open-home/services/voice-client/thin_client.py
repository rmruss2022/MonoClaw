#!/usr/bin/env python3
"""
openhome voice client — thin.

The only thing that happens on this box is the wake word. Everything after it
is the hub's job: /agent/audio transcribes, decides and speaks the answer on
the room speaker. That is deliberate — the previous client carried its own
speech-to-text, its own text-to-speech and its own ducking, so every fix had
to be made twice and the two drifted. One brain, one audio path.

Flow:
    arecord -> openWakeWord ("hey jarvis") -> record until you stop talking
            -> POST the wav to the hub -> the hub answers out loud.

Run:
    /opt/openhome-voice/.venv/bin/python thin_client.py
Config: /home/pi/.openhome/voice.env (see VoiceConfig below).
"""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import time
import wave
from collections import deque

import numpy as np
import requests

RATE = 16_000
FRAME = 1280                      # 80 ms at 16 kHz — openWakeWord's frame size
MIC = os.environ.get("MIC_ALSA", "plughw:CARD=A21,DEV=0")
HUB = os.environ.get("OPEN_HOME_URL", "http://127.0.0.1:4700").rstrip("/")
PASSWORD = os.environ.get("OPEN_HOME_PASSWORD", "")
# openWakeWord 0.4.0 takes model FILE PATHS, not names, and ships the models
# inside the package — "hey_jarvis_v0.1.onnx" is already on disk. (0.5+ has
# download_models() and name-based loading, but it needs tflite-runtime, which
# has no wheel for this Pi's Python 3.13. 0.4.0 is ONNX-only, which is exactly
# what works here.)
WAKE_MODEL = os.environ.get("WAKE_MODEL", "hey_jarvis")
WAKE_THRESHOLD = float(os.environ.get("WAKE_THRESHOLD", "0.5"))

# How long to keep listening after the wake word, and when to decide you have
# stopped talking. The grace is generous because people pause before speaking.
MAX_UTTERANCE_S = float(os.environ.get("MAX_UTTERANCE_S", "12"))
ONSET_GRACE_S = float(os.environ.get("ONSET_GRACE_S", "5.0"))
SILENCE_END_S = float(os.environ.get("SILENCE_END_S", "1.0"))
# Frames quieter than this count as silence. Measured room noise sits near
# -29 dBFS, so this is comfortably below speech and above the noise floor.
SILENCE_RMS = float(os.environ.get("SILENCE_RMS", "180"))
# After the hub answers, ignore the mic: the reply is playing on the speaker
# in this room and we would otherwise transcribe ourselves.
COOLDOWN_S = float(os.environ.get("COOLDOWN_S", "1.5"))
# A conversation is capped so a misheard follow-up cannot trap the mic open.
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))
# After the house asks you something it waits this long for an answer before
# giving up and going back to the wake word.
FOLLOWUP_GRACE_S = float(os.environ.get("FOLLOWUP_GRACE_S", "6.0"))


def log(*a: object) -> None:
    print(f"[voice {time.strftime('%H:%M:%S')}]", *a, flush=True)


class Hub:
    """The hub session. Re-authenticates on 401 rather than dying."""

    def __init__(self) -> None:
        self.s = requests.Session()
        self.token = ""

    def login(self) -> bool:
        if not PASSWORD:
            return True  # hub has no gate configured
        try:
            r = self.s.post(f"{HUB}/login", data={"password": PASSWORD},
                            headers={"Accept": "application/json"}, timeout=8)
            self.token = (r.json() or {}).get("token", "")
            if self.token:
                self.s.cookies.set("oh_auth", self.token)
            return bool(self.token)
        except Exception as e:
            log("login failed:", e)
            return False

    def wait_until_quiet(self, timeout_s: float = 180.0) -> None:
        """Block until the house has finished speaking.

        The hub does not wait for playback before replying — a two minute
        report would hold the request open — so the client has to. Reopening
        the mic early means transcribing our own voice off the speaker."""
        deadline = time.time() + timeout_s
        # Give playback a moment to start, or we would see "not speaking" in
        # the gap between the HTTP reply and the first audio frame.
        time.sleep(0.6)
        while time.time() < deadline:
            try:
                if not self.s.get(f"{HUB}/speak/status", timeout=4).json().get("speaking"):
                    return
            except Exception:
                return
            time.sleep(0.3)

    def send_audio(self, wav: bytes) -> dict | None:
        body = {"audio": base64.b64encode(wav).decode(), "mime": "audio/wav"}
        for attempt in (1, 2):
            try:
                r = self.s.post(f"{HUB}/agent/audio", json=body, timeout=120)
                if r.status_code == 401 and attempt == 1:
                    self.login()
                    continue
                return r.json()
            except Exception as e:
                log("hub error:", e)
                return None
        return None


def to_wav(frames: list[np.ndarray]) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.concatenate(frames).astype(np.int16).tobytes())
    return buf.getvalue()


def reset(oww) -> None:
    """Clear the score history so one wake word cannot fire twice."""
    try:
        oww.reset()
    except AttributeError:
        # 0.4.0 has no reset(); clearing the per-model buffers does the same.
        for buf in getattr(oww, "prediction_buffer", {}).values():
            buf.clear()


def beep(freq: int = 880, ms: int = 120, vol: float = 0.25) -> None:
    """A short tone so you KNOW it woke. The first attempt at this client had
    no cue at all: it fired correctly, Matthew heard nothing, and reasonably
    concluded the wake word was broken."""
    n = int(RATE * ms / 1000)
    t = np.arange(n) / RATE
    # Fade the edges or it clicks, which sounds like a fault rather than a cue.
    env = np.minimum(1.0, np.minimum(np.arange(n), n - np.arange(n)) / (RATE * 0.01))
    tone = (np.sin(2 * np.pi * freq * t) * env * vol * 32767).astype(np.int16)
    try:
        subprocess.run(
            ["aplay", "-q", "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw", "-"],
            input=tone.tobytes(), timeout=3,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def open_mic() -> subprocess.Popen:
    return subprocess.Popen(
        ["arecord", "-D", MIC, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw", "-q"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )


def read_frame(mic: subprocess.Popen) -> np.ndarray | None:
    raw = mic.stdout.read(FRAME * 2)  # type: ignore[union-attr]
    if not raw or len(raw) < FRAME * 2:
        return None
    return np.frombuffer(raw, dtype=np.int16)


def rms(frame: np.ndarray) -> float:
    # float64 first: int16 squared overflows and reports silence for loud audio.
    return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))


def capture(mic: subprocess.Popen, grace_s: float,
            seed: "np.ndarray | None" = None) -> "list[np.ndarray] | None":
    """Record until the speaker stops, or until `grace_s` passes with no speech.

    `seed` is the frame that triggered the wake word, kept so the first syllable
    after it is not clipped."""
    frames: list[np.ndarray] = [seed] if seed is not None else []
    started = time.time()
    last_voice = started
    heard = False
    while True:
        f = read_frame(mic)
        if f is None:
            return frames or None
        frames.append(f)
        now = time.time()
        if rms(f) > SILENCE_RMS:
            heard = True
            last_voice = now
        if now - started > MAX_UTTERANCE_S:
            break
        if heard and now - last_voice > SILENCE_END_S:
            break
        if not heard and now - started > grace_s:
            break
    return frames


def find_model(name: str) -> str:
    """Locate the bundled .onnx for a wake word, e.g. hey_jarvis -> .../hey_jarvis_v0.1.onnx."""
    import openwakeword
    root = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
    for fn in sorted(os.listdir(root)):
        if fn.startswith(name) and fn.endswith(".onnx"):
            return os.path.join(root, fn)
    raise FileNotFoundError(f"no bundled model for {name!r} in {root}")


def main() -> int:
    from openwakeword.model import Model

    model_path = find_model(WAKE_MODEL)
    log(f"mic={MIC} hub={HUB} wake={os.path.basename(model_path)} threshold={WAKE_THRESHOLD}")
    oww = Model(wakeword_model_paths=[model_path])
    # The score key is the file stem, not the friendly name we were given.
    key = os.path.basename(model_path).rsplit(".", 1)[0]
    log("scoring key:", key)

    hub = Hub()
    hub.login()

    mic = open_mic()
    log("listening")
    try:
        while True:
            frame = read_frame(mic)
            if frame is None:
                log("mic ended — reopening")
                mic.kill()
                time.sleep(1)
                mic = open_mic()
                continue

            scores = oww.predict(frame)
            if scores.get(key, 0.0) < WAKE_THRESHOLD:
                continue

            log(f"wake ({scores[key]:.2f})")
            reset(oww)
            beep()

            # A conversation, not a command. The house decides when to keep the
            # mic open — it knows whether it just asked a question or simply
            # did what it was told — so the client only obeys the `listen` flag.
            first = True
            for turn in range(MAX_TURNS):
                grace = ONSET_GRACE_S if first else FOLLOWUP_GRACE_S
                frames = capture(mic, grace, seed=frame if first else None)
                first = False
                if frames is None:
                    break

                peak = max((rms(f) for f in frames), default=0.0)
                if peak <= SILENCE_RMS:
                    log(f"nothing said (peak RMS {peak:.0f}, threshold {SILENCE_RMS:.0f})")
                    break

                wav = to_wav(frames)
                log(f"turn {turn + 1}: {len(frames) * FRAME / RATE:.1f}s, peak RMS {peak:.0f}")
                r = hub.send_audio(wav)
                if not r:
                    break
                log("heard:", json.dumps(r.get("transcript", ""))[:120])
                log("reply:", (r.get("reply") or "")[:120].replace("\n", " "))

                # Wait out the reply either way: even on the last turn we must
                # not leave the mic hot while the speaker is still talking.
                hub.wait_until_quiet()
                if not r.get("listen"):
                    log("end of turn")
                    break
                log("expecting a reply — listening again")
                # Fresh mic: whatever queued up during the answer is ours, not his.
                mic.kill()
                mic = open_mic()
                beep(freq=660, ms=90)

            time.sleep(COOLDOWN_S)
            mic.kill()
            mic = open_mic()
            reset(oww)
    except KeyboardInterrupt:
        pass
    finally:
        mic.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
