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
import threading
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
SILENCE_END_S = float(os.environ.get("SILENCE_END_S", "0.6"))
# Speech must stand this many times above the measured room noise to count.
# A fixed number cannot work — the floor moves with the music, the fridge and
# the time of day — and setting it below ambient means end-of-speech never
# fires and every utterance runs to the cap.
SPEECH_OVER_NOISE = float(os.environ.get("SPEECH_OVER_NOISE", "2.2"))
# Floor and ceiling for the derived threshold, so a freak-quiet or very loud
# moment cannot make it useless.
SILENCE_RMS_MIN = float(os.environ.get("SILENCE_RMS_MIN", "300"))
SILENCE_RMS_MAX = float(os.environ.get("SILENCE_RMS_MAX", "4000"))
# After the hub answers, ignore the mic: the reply is playing on the speaker
# in this room and we would otherwise transcribe ourselves.
COOLDOWN_S = float(os.environ.get("COOLDOWN_S", "1.5"))
# A conversation is capped so a misheard follow-up cannot trap the mic open.
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))
# After the house asks you something it waits this long for an answer before
# giving up and going back to the wake word.
FOLLOWUP_GRACE_S = float(os.environ.get("FOLLOWUP_GRACE_S", "6.0"))
# How long to wait for playback to BEGIN before assuming there is none. Must
# exceed synthesis time (~1s) or the client races the reply it just asked for.
SPEECH_START_WAIT_S = float(os.environ.get("SPEECH_START_WAIT_S", "6.0"))
# Bluetooth lag: the speaker is still emitting after the player process exits.
SPEECH_TAIL_S = float(os.environ.get("SPEECH_TAIL_S", "0.6"))
# Wake-word threshold while the house is SPEAKING, for interrupting it. Higher
# than the idle one: the mic is hearing our own voice out of the same speaker,
# and a false positive cuts a reply off mid-word.
BARGE_THRESHOLD = float(os.environ.get("BARGE_THRESHOLD", "0.65"))


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

    def listening(self, on: bool) -> None:
        """Tell the hub to duck (or restore) the music while we listen."""
        try:
            self.s.post(f"{HUB}/speak/listening", json={"on": on}, timeout=4)
        except Exception as e:
            log("duck call failed:", e)

    def stop_speaking(self) -> None:
        """Cut the reply off mid-sentence — and drop anything queued behind it."""
        try:
            self.s.post(f"{HUB}/speak/stop", json={}, timeout=4)
        except Exception as e:
            log("stop call failed:", e)

    def wake_actions(self) -> None:
        """Everything the hub should do the instant the wake word fires.

        Run on a thread, because `beep()` blocks for the length of the cue plus
        the Bluetooth latency — call this after it and the music stays at full
        volume for most of a second while you are already talking, which is
        exactly the lag that felt broken. Overlapping the two means the duck
        lands *during* the blip.

        Stopping speech is unconditional and harmless when nothing is playing:
        it is what makes "Hey Jarvis" an interrupt. Saying the wake word while
        the morning report is grinding on should shut it up immediately, not
        after the paragraph.
        """
        self.stop_speaking()
        self.listening(True)

    def _speaking(self) -> bool:
        try:
            return bool(self.s.get(f"{HUB}/speak/status", timeout=4).json().get("speaking"))
        except Exception:
            return False

    def wait_until_quiet(self, listener: "BargeIn | None" = None,
                         timeout_s: float = 300.0) -> "tuple[float, bool]":
        """Block until the house has actually finished speaking.

        Two phases, and the first one is the whole point. The hub answers the
        HTTP request BEFORE it starts playing — synthesis takes about a second
        — so polling "are you speaking?" straight away sees False, returns
        immediately, and the client reopens the mic into the reply. That is not
        a theoretical race: it put the house in a feedback loop, transcribing
        its own voice as the next question for six turns running.

        So: wait for speech to START, then wait for it to STOP, then let the
        Bluetooth tail drain before trusting the mic again.

        If a `listener` is given, the mic keeps running through all of it and
        the wake word is still live — so you can talk over the reply instead of
        waiting it out. Returns (seconds, interrupted).
        """
        t0 = time.time()

        def hold(until: float, while_speaking: bool) -> bool:
            """Wait, watching for the wake word. True if it fired."""
            last_poll = 0.0
            while time.time() < until:
                if listener is not None:
                    if listener.poll():
                        return True
                else:
                    time.sleep(0.15)
                # The status poll is cheap but not free, and the mic has to stay
                # at real time or wake detection falls behind the room.
                if time.time() - last_poll > 0.3:
                    last_poll = time.time()
                    if self._speaking() is not while_speaking:
                        return False
            return False

        if hold(t0 + SPEECH_START_WAIT_S, while_speaking=False):
            return time.time() - t0, True
        if hold(time.time() + timeout_s, while_speaking=True):
            return time.time() - t0, True

        # The speaker is several hundred ms behind the process exiting.
        time.sleep(SPEECH_TAIL_S)
        return time.time() - t0, False

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


# A real recorded cue if one is installed, else a synthesised tone. Matthew
# downloaded a blip; it is nicer than a sine wave and, more usefully, it is
# instantly recognisable as "I am listening" rather than "something beeped".
BLIP = os.environ.get("BLIP_FILE", "/opt/openhome-voice/blip.raw")


def play_raw(data: bytes) -> None:
    """Play 16 kHz mono PCM through PipeWire.

    -D pipewire is not optional: `aplay -L` on this Pi reports the default
    device as "null — Discard all samples", so a bare aplay sends the cue
    nowhere and the wake word looks dead.
    """
    try:
        subprocess.run(
            ["aplay", "-q", "-D", "pipewire", "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw", "-"],
            input=data, timeout=3,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def tone(freq: int = 880, ms: int = 120, vol: float = 0.25) -> bytes:
    n = int(RATE * ms / 1000)
    t = np.arange(n) / RATE
    # Fade the edges or it clicks, which sounds like a fault rather than a cue.
    env = np.minimum(1.0, np.minimum(np.arange(n), n - np.arange(n)) / (RATE * 0.01))
    return (np.sin(2 * np.pi * freq * t) * env * vol * 32767).astype(np.int16).tobytes()


_blip_cache: "bytes | None" = None


def beep(freq: int = 880, ms: int = 120, vol: float = 0.25) -> None:
    """The cue that says the house is listening."""
    global _blip_cache
    if _blip_cache is None:
        try:
            with open(BLIP, "rb") as fh:
                _blip_cache = fh.read()
            log(f"wake cue: {BLIP} ({len(_blip_cache) / 32000:.2f}s)")
        except OSError:
            _blip_cache = b""
            log("wake cue: no blip file, using a tone")
    play_raw(_blip_cache or tone(freq, ms, vol))


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


class NoiseFloor:
    """Rolling estimate of the room while nobody is talking.

    Only fed from idle frames (before a wake word), which are not speech by
    definition. The median ignores the occasional door slam that would drag a
    mean upwards for minutes."""

    def __init__(self, seconds: float = 4.0) -> None:
        self.buf: deque[float] = deque(maxlen=int(seconds * RATE / FRAME))

    def add(self, v: float) -> None:
        self.buf.append(v)

    @property
    def level(self) -> float:
        return float(np.median(self.buf)) if self.buf else 0.0

    @property
    def threshold(self) -> float:
        t = self.level * SPEECH_OVER_NOISE
        return float(min(max(t, SILENCE_RMS_MIN), SILENCE_RMS_MAX))


class BargeIn:
    """The wake word, still listening while the house is talking.

    Being unable to interrupt is the difference between an assistant and a
    recording. The morning report is a couple of minutes long; if the only way
    out is to wait for it, you stop asking for it.

    The catch is that the microphone and the speaker are in the same room, so
    this model is now listening to our own voice. Hence a higher threshold than
    the idle one: a false positive here truncates a reply mid-word, which is
    more annoying than a missed interrupt.
    """

    def __init__(self, oww, key: str, threshold: float) -> None:
        self.oww = oww
        self.key = key
        self.threshold = threshold
        self.mic: "subprocess.Popen | None" = None
        self.score = 0.0

    def poll(self) -> bool:
        """Consume one frame. True if the wake word fired."""
        if self.mic is None:
            time.sleep(0.08)
            return False
        f = read_frame(self.mic)
        if f is None:
            time.sleep(0.08)
            return False
        s = self.oww.predict(f).get(self.key, 0.0)
        if s >= self.threshold:
            self.score = s
            reset(self.oww)
            return True
        return False


def rms(frame: np.ndarray) -> float:
    # float64 first: int16 squared overflows and reports silence for loud audio.
    return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))


def capture(mic: subprocess.Popen, grace_s: float, thresh: float,
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
        if rms(f) > thresh:
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
    floor = NoiseFloor()
    barge = BargeIn(oww, key, BARGE_THRESHOLD)

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

            # Idle frame: this is the room, not speech. Use it to learn the floor.
            floor.add(rms(frame))

            scores = oww.predict(frame)
            if scores.get(key, 0.0) < WAKE_THRESHOLD:
                continue

            t_wake = time.time()
            thresh = floor.threshold
            log(f"wake ({scores[key]:.2f})  floor {floor.level:.0f} -> threshold {thresh:.0f}")
            reset(oww)
            # Duck (and interrupt any reply still playing) IN PARALLEL with the
            # cue. aplay blocks for the length of the blip plus Bluetooth
            # latency, so doing this afterwards left the music at full volume
            # for most of a second after the beep — which is the lag you hear.
            threading.Thread(target=hub.wake_actions, daemon=True).start()
            beep()
            log(f"  +{(time.time()-t_wake)*1000:.0f}ms cue done (duck fired in parallel)")

            # A conversation, not a command. The house decides when to keep the
            # mic open — it knows whether it just asked a question or simply
            # did what it was told — so the client only obeys the `listen` flag.
            first = True
            for turn in range(MAX_TURNS):
                grace = ONSET_GRACE_S if first else FOLLOWUP_GRACE_S
                frames = capture(mic, grace, thresh, seed=frame if first else None)
                first = False
                if frames is None:
                    break

                peak = max((rms(f) for f in frames), default=0.0)
                if peak <= thresh:
                    log(f"nothing said (peak RMS {peak:.0f}, threshold {thresh:.0f})")
                    break

                t_captured = time.time()
                wav = to_wav(frames)
                log(f"turn {turn + 1}: spoke {len(frames) * FRAME / RATE:.1f}s, "
                    f"peak RMS {peak:.0f}, +{(t_captured - t_wake):.1f}s from wake")

                r = hub.send_audio(wav)
                t_replied = time.time()
                if not r:
                    break
                # The number that matters: how long from YOU stopping talking
                # to the house having an answer ready.
                log(f"  +{(t_replied - t_captured):.1f}s hub round-trip "
                    f"(stt + agent + first audio)")
                log("  heard:", json.dumps(r.get("transcript", ""))[:120])
                log("  reply:", (r.get("reply") or "")[:120].replace("\n", " "))

                # Wait out the reply either way: even on the last turn we must
                # not leave the mic hot while the speaker is still talking.
                # The wake word stays live throughout, so a long answer can be
                # cut short rather than sat through.
                if (r.get("reply") or "").strip():
                    barge.mic = mic
                    spoke_for, cut_off = hub.wait_until_quiet(barge)
                    barge.mic = None
                    log(f"  +{spoke_for:.1f}s speaking   |   total {time.time()-t_wake:.1f}s since wake")
                else:
                    # Nothing is going to play, so do not sit through the
                    # six-second "has playback started yet?" grace. "Stop"
                    # answers with silence by design.
                    spoke_for, cut_off = 0.0, False
                    log("  no reply to play — not waiting")

                if cut_off:
                    log(f"interrupted ({barge.score:.2f}) — stopping and listening")
                    hub.stop_speaking()
                    beep(freq=660, ms=90)
                    mic.kill()
                    mic = open_mic()
                    # Treat it as a fresh request, not a follow-up: you
                    # interrupted to say something new, and you get the full
                    # onset grace to say it.
                    first = True
                    frame = None
                    continue

                if not r.get("listen"):
                    log("end of turn")
                    break
                log("expecting a reply — listening again")
                # Cue FIRST, then a fresh mic. Doing it the other way round
                # meant the open mic recorded our own blip, and the hub duly
                # transcribed "[beeping]" as Matthew's answer.
                beep(freq=660, ms=90)
                mic.kill()
                mic = open_mic()

            # Conversation over — give the room its music back.
            hub.listening(False)
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
