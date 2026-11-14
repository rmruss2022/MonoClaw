#!/usr/bin/env python3
"""
OpenHome voice client — turns a Raspberry Pi (+ mic + speaker) into a hands-free
voice assistant for the home.

Flow:
  openWakeWord spots the wake word on the mic
    -> we record until you stop talking (WebRTC VAD endpointing)
    -> ElevenLabs Scribe transcribes the clip locally
    -> POST the text to the hub's /agent (it decides + RUNS smart-home actions)
    -> DUCK any music on the room speaker, speak the reply with ElevenLabs, restore.

Capture is via `arecord` through ALSA's `plug` layer, so any USB array mic works.
Reply audio + the wake-ack beep play to the room speaker (the X10) via PipeWire.

Verbose logs (timestamped) go to VOICE_LOG (default /home/pi/.openhome/voice.log)
and stdout. Set VOICE_DEBUG=0 to quiet the per-frame detail.

Config (environment): see README / voice.env.example.
"""
import base64
import glob
import io
import json
import os
import re
import select
import subprocess
import threading
import time
import wave
from datetime import datetime

import numpy as np
import requests
import webrtcvad
import openwakeword
from openwakeword.model import Model as WakeModel

SR = 16000
BLOCK = 1280
VAD_FRAME = 320

HUB = os.environ.get("OPENHOME_HUB_URL", "http://localhost:4700").rstrip("/")
XI_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
EL_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
EL_STT_MODEL = os.environ.get("ELEVENLABS_STT_MODEL", "scribe_v1")
OWW_MODEL = os.environ.get("OWW_MODEL", "hey_jarvis")
WAKE_THRESHOLD = float(os.environ.get("WAKE_THRESHOLD", "0.5"))
# Adaptive wake modes: the room is clean when music is paused/stopped, swamped when
# it's playing. We KNOW the playback state (we drive Soloist), so lower the bar +
# require a few consecutive frames while music plays (compensate masking, reject
# one-frame lyric spikes); keep the snappy baseline when it's quiet.
WAKE_THRESHOLD_MUSIC = float(os.environ.get("WAKE_THRESHOLD_MUSIC", "0.25"))
WAKE_CONFIRM_MUSIC = int(os.environ.get("WAKE_CONFIRM_MUSIC", "2"))   # consecutive frames in music mode
MUSIC_POLL_S = float(os.environ.get("MUSIC_POLL_S", "3"))             # how often to recheck playback state
WAKE_DIAG = float(os.environ.get("WAKE_DIAG", "0"))                   # if >0, log wake scores >= this (incl. sub-threshold) for tuning
# Multi-turn: after a reply, keep listening (no wake word) for a follow-up. If the
# user stays silent this many seconds, the conversation ends and we go back to the
# wake word. MAX_TURNS caps a runaway back-and-forth.
FOLLOWUP_WAIT_S = float(os.environ.get("FOLLOWUP_WAIT_S", "3.5"))
MAX_TURNS = int(os.environ.get("MAX_TURNS", "6"))
FOLLOWUP_SETTLE_S = float(os.environ.get("FOLLOWUP_SETTLE_S", "0.5"))   # let reply's BT tail land, then flush it
BEEP_SETTLE_S = float(os.environ.get("BEEP_SETTLE_S", "0.3"))           # let a beep land in the pipe, then flush it
# Grace: after the beep, how long to wait for you to START talking before giving up.
# Longer with music (you often need a beat to react over the sound).
WAKE_GRACE_S = float(os.environ.get("WAKE_GRACE_S", "2.5"))
WAKE_GRACE_MUSIC_S = float(os.environ.get("WAKE_GRACE_MUSIC_S", "4.0"))
SILENCE_MS = int(os.environ.get("SILENCE_MS", "800"))
MAX_UTTER_S = float(os.environ.get("MAX_UTTER_S", "12"))
# Energy gate: a frame must be at least this loud (int16 RMS) to count as speech,
# so ducked music/ambient (which webrtcvad alone flags as "speech") isn't recorded
# as if you were talking. Tune with the logged recorded-rms values.
VOICE_RMS_FLOOR = float(os.environ.get("VOICE_RMS_FLOOR", "450"))
MIC_ALSA = os.environ.get("MIC_ALSA", "plughw:CARD=A21,DEV=0")
MIC_GAIN = float(os.environ.get("MIC_GAIN", "1.0"))   # digital boost for far-field pickup
SPK_NODE = os.environ.get("SPK_NODE", "bluez_output.F4_4E_FD_49_83_98.1")
DUCK_LEVEL = int(os.environ.get("DUCK_LEVEL", "25"))
SPEAK_DUCK_LEVEL = int(os.environ.get("SPEAK_DUCK_LEVEL", "35"))   # (legacy) music level while WE speak a reply
SPEAK_GAIN = float(os.environ.get("SPEAK_GAIN", "1.0"))           # PCM gain (TTS is already near full-scale)
SPEAK_SINK_VOL = float(os.environ.get("SPEAK_SINK_VOL", "0.9"))   # raise the X10 output to this while speaking, then restore
# The X10's Bluetooth AVRCP volume drifts DOWN on its own between interactions, which
# makes the brief voice inaudible (continuous music survives). Re-assert the speaker to
# this fixed level at the start of every wake so the voice is always at a proper volume.
SPEAKER_VOL = float(os.environ.get("SPEAKER_VOL", "0.9"))
# Loudness-compress the TTS so speech is as PRESENT as the beep/music. Speech has a low
# average level (quiet gaps between words), so at a given volume it's ~3x quieter than
# continuous audio and gets lost. Soft tanh knee raises RMS + soft-limits peaks. ~6 makes
# speech rms match the beep/music. This is how Alexa/Google make their TTS cut through.
SPEECH_COMPRESS = float(os.environ.get("SPEECH_COMPRESS", "6"))
# Overall voice loudness (0-1). Compression sets DENSITY (cut-through); this sets LEVEL
# relative to the music. Lower = quieter voice. One-number dial for "voice too loud/soft".
VOICE_LEVEL = float(os.environ.get("VOICE_LEVEL", "0.7"))
LOG_FILE = os.environ.get("VOICE_LOG", "/home/pi/.openhome/voice.log")
DEBUG = os.environ.get("VOICE_DEBUG", "1") != "0"
LOG_MAX_BYTES = int(os.environ.get("VOICE_LOG_MAX_BYTES", "5242880"))
_log_lock = threading.Lock()

_AENV = {**os.environ, "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")}


def log(*a, level="INFO"):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} [{level}] " + " ".join(str(x) for x in a)
    print(line, flush=True)
    try:
        with _log_lock:
            # Keep one bounded backup; serialize rotation with background logging.
            if LOG_MAX_BYTES > 0 and os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= LOG_MAX_BYTES:
                os.replace(LOG_FILE, LOG_FILE + ".1")
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
    except Exception:
        pass


def dbg(*a):
    if DEBUG:
        log(*a, level="DEBUG")


# --- hub auth (cookie is Secure, so we send the token as an explicit header) ----
HUB_PW = os.environ.get("OPEN_HOME_PASSWORD", "")
SESSION = requests.Session()
HUB_TOKEN = None


def hub_login():
    global HUB_TOKEN
    if not HUB_PW:
        log("hub login skipped: no OPEN_HOME_PASSWORD", level="WARN")
        return
    try:
        r = SESSION.post(f"{HUB}/login", data={"password": HUB_PW},
                         headers={"Accept": "application/json"}, timeout=10)
        HUB_TOKEN = (r.json() or {}).get("token")
        log(f"hub login -> {r.status_code}, token={'yes' if HUB_TOKEN else 'NO'}")
    except Exception as e:
        log("hub login error:", e, level="ERROR")


def _auth_headers():
    return {"Cookie": f"oh_auth={HUB_TOKEN}"} if HUB_TOKEN else {}


def _hub_request(method, path, **kwargs):
    """Reject HTTP, authentication and malformed/application-level failures alike."""
    for attempt in range(2):
        r = SESSION.request(method, f"{HUB}{path}", headers=_auth_headers(), **kwargs)
        if r.status_code == 401 and attempt == 0:
            hub_login()
            continue
        r.raise_for_status()
        result = r.json()
        if not isinstance(result, dict) or result.get("ok") is False:
            raise ValueError(f"hub command failed: {result}")
        return result


vad = webrtcvad.Vad(3)   # most aggressive: better at ignoring music bleed, ends sooner


def _resolve_oww_model(name):
    if os.path.sep in name or name.endswith(".onnx"):
        return name
    base = os.path.join(os.path.dirname(openwakeword.__file__), "resources", "models")
    hits = sorted(glob.glob(os.path.join(base, name + "*.onnx")))
    return hits[0] if hits else name


log(f"loading wake model '{OWW_MODEL}' …")
# Speex noise suppression cleans music/room bleed out of the mic frames before
# they hit the wake model → higher, steadier wake scores without touching the threshold.
_SPEEX_NS = os.environ.get("SPEEX_NS", "1") not in ("0", "false", "no", "")
try:
    wake = WakeModel(wakeword_model_paths=[_resolve_oww_model(OWW_MODEL)],
                     enable_speex_noise_suppression=_SPEEX_NS)
    log(f"wake model loaded (speex_ns={'on' if _SPEEX_NS else 'off'})")
except Exception as e:
    log(f"speex NS unavailable ({e}); loading without it", level="WARN")
    wake = WakeModel(wakeword_model_paths=[_resolve_oww_model(OWW_MODEL)])


def _run(cmd, timeout=6):
    """Run a CLI, return (rc, stderr). Logs failures."""
    try:
        p = subprocess.run(cmd, env=_AENV, timeout=timeout,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if p.returncode != 0:
            log(f"cmd failed rc={p.returncode}: {' '.join(cmd)} | {p.stderr.decode('utf8','ignore')[:120]}", level="WARN")
        return p.returncode, p.stderr.decode("utf8", "ignore")
    except Exception as e:
        log(f"cmd error: {' '.join(cmd)} | {e}", level="WARN")
        return -1, str(e)


MIC_PW_SOURCE = os.environ.get("MIC_PW_SOURCE", "").strip()


_music_state = {"on": False, "t": 0.0}
_music_sources = {"spotify": False, "soundcloud": False}
MIC_READ_TIMEOUT_S = float(os.environ.get("MIC_READ_TIMEOUT_S", "2.0"))
MIC_REOPEN_BACKOFF_S = float(os.environ.get("MIC_REOPEN_BACKOFF_S", "0.8"))
MIC_REOPEN_BACKOFF_MAX_S = float(os.environ.get("MIC_REOPEN_BACKOFF_MAX_S", "8.0"))


def music_playing(fresh=False):
    """True when the X10 is actively playing music. Cached; polls Soloist (and the
    SoundCloud mpv helper) at most every MUSIC_POLL_S so the wake loop stays cheap."""
    now = time.time()
    if (not fresh) and now - _music_state["t"] < MUSIC_POLL_S:
        return _music_state["on"]
    _music_state["t"] = now
    if fresh:
        # Unknown/error is never permission to auto-resume a source.
        _music_sources.update(spotify=False, soundcloud=False)
    on = False
    try:
        p = subprocess.run(["soloist", "ctl", "now"], env=_AENV, timeout=2 if fresh else 0.25,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out = p.stdout.decode("utf8", "ignore").lower()
        on = p.returncode == 0 and bool(re.search(r"\bplaying\b", out)) and "paused" not in out
        _music_sources["spotify"] = on
    except Exception:
        on = False if fresh else _music_state["on"]
    if fresh or not on:
        # SoundCloud path (sc-play via mpv) counts as music too
        try:
            q = subprocess.run(["sc-ctl", "status"], env=_AENV, timeout=2 if fresh else 0.25,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out = q.stdout.decode("utf8", "ignore").lower()
            _music_sources["soundcloud"] = q.returncode == 0 and bool(re.search(r"\bplaying\b", out)) and "paused" not in out
            if _music_sources["soundcloud"]:
                on = True
        except Exception:
            pass
    if on != _music_state["on"]:
        log(f"mode -> {'MUSIC' if on else 'QUIET'} "
            f"(thr {WAKE_THRESHOLD_MUSIC if on else WAKE_THRESHOLD}, "
            f"confirm {WAKE_CONFIRM_MUSIC if on else 1})")
    _music_state["on"] = on
    return on


_keepalive = {"process": None, "heartbeat": 0.0}
_speaker_lock = threading.Lock()
_speaker_failures = 0
_speaker_last_reconnect = 0.0


def _recover_speaker(reconnect=False):
    """Resolve the same BT device's current sink after profile/node recreation."""
    global SPK_NODE, _speaker_last_reconnect
    with _speaker_lock:
        mac = re.search(r"([0-9A-Fa-f]{2}(?:_[0-9A-Fa-f]{2}){5})", SPK_NODE)
        address = os.environ.get("SPK_MAC", mac.group(1).replace("_", ":") if mac else "")
        try:
            if reconnect and address and time.monotonic() - _speaker_last_reconnect > 15:
                _speaker_last_reconnect = time.monotonic()
                _run(["bluetoothctl", "connect", address], timeout=5)
            p = subprocess.run(["pw-dump"], env=_AENV, timeout=3,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            p.check_returncode()
            nodes = json.loads(p.stdout)
            sinks = [(n.get("info") or {}).get("props", {}) for n in nodes]
            sinks = [s for s in sinks if s.get("media.class") == "Audio/Sink"]
            found = next((s for s in sinks if s.get("node.name") == SPK_NODE), None)
            if found is None and address:
                found = next((s for s in sinks if address.replace(":", "_").lower()
                              in str(s.get("node.name", "")).lower()), None)
            if found is None:
                return False
            previous = SPK_NODE
            SPK_NODE = found["node.name"]
            if previous != SPK_NODE:
                _restart_keepalive()
            return True
        except Exception as e:
            log("speaker recovery:", e, level="WARN")
            return False


def _restart_keepalive():
    p = _keepalive["process"]
    if p is not None and p.poll() is None:
        # Killing the child releases a writer blocked in flush; its owner reaps it.
        try:
            p.kill()
        except OSError:
            pass


def _start_keepalive():
    """Hold a CONTINUOUS inaudible stream to the X10 so its Bluetooth sink never goes
    idle. Without this the beep is heard (plays instantly on wake) but the voice — played
    a few seconds later, after recording your command — falls into an idled BT sink and is
    attenuated/lost. Verified: keeps the voice at full strength from the first word."""
    def run():
        chunk = (np.random.randint(-3, 4, SR // 2, dtype=np.int16)).tobytes()   # ~0.5s, ~-80dB (inaudible)
        while True:
            p = None
            try:
                p = subprocess.Popen(
                    ["pw-play", "--target", SPK_NODE, "--rate", str(SR),
                     "--channels", "1", "--format", "s16", "--raw", "-"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, env=_AENV)
                _keepalive.update(process=p, heartbeat=time.monotonic())
                while True:
                    p.stdin.write(chunk)       # blocks when the pipe fills → self-throttling, gapless
                    p.stdin.flush()
                    _keepalive["heartbeat"] = time.monotonic()
            except Exception as e:
                log("keepalive dropped, restarting:", e, level="WARN")
            finally:
                try:
                    _close_process(p)
                except (OSError, ValueError):
                    pass
                _keepalive["process"] = None
                time.sleep(1)
    def watchdog():
        last_sink_check = 0.0
        while True:
            time.sleep(2)
            if _keepalive["process"] is not None and time.monotonic() - _keepalive["heartbeat"] > 5:
                log("keepalive stalled; restarting", level="WARN")
                _restart_keepalive()
            if time.monotonic() - last_sink_check > 30:
                last_sink_check = time.monotonic()
                if not _recover_speaker():
                    _recover_speaker(reconnect=True)
                    _restart_keepalive()
    threading.Thread(target=run, daemon=True).start()
    threading.Thread(target=watchdog, daemon=True).start()
    log("keepalive stream started (keeps the X10 Bluetooth sink alive)")


def _soloist_now():
    """Current Spotify track as 'Title by Artist' (for spoken 'Now playing …')."""
    try:
        p = subprocess.run(["soloist", "ctl", "now"], env=_AENV, timeout=3,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        lines = p.stdout.decode("utf8", "ignore").strip().splitlines()
        if not lines:
            return None
        line = lines[0].strip()
        if " - " in line:
            title, artist = line.split(" - ", 1)
            title = title.strip()[:45]
            artist = artist.split(",")[0].strip()[:30]   # first/primary artist only, capped
            return f"{title} by {artist}" if artist else title
        return (line[:60] or None)
    except Exception:
        return None


def _open_mic_once():
    # When MIC_PW_SOURCE is set we capture from a PipeWire node (the AEC'd
    # echo-cancel source) so the music the X10 is playing is already subtracted
    # out of the frames. Otherwise fall back to raw ALSA via arecord.
    if MIC_PW_SOURCE:
        log(f"opening mic: pw-record --target {MIC_PW_SOURCE} @ {SR}Hz mono (AEC path)")
        return subprocess.Popen(
            ["pw-record", "--target", MIC_PW_SOURCE, "--rate", str(SR),
             "--channels", "1", "--format", "s16", "--raw", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_AENV,
        )
    log(f"opening mic: arecord -D {MIC_ALSA} @ {SR}Hz mono")
    return subprocess.Popen(
        ["arecord", "-q", "-D", MIC_ALSA, "-f", "S16_LE", "-r", str(SR),
         "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_AENV,
    )


def flush_mic(mic):
    """Discard any audio buffered while we were playing a reply/beep, so a follow-up
    turn records FRESH input instead of transcribing the tail of our own speech
    (which arecord kept capturing into the pipe meanwhile — e.g. 'Okay, Liz')."""
    try:
        fd = mic.stdout.fileno()
        n = 0
        while select.select([fd], [], [], 0)[0]:
            d = os.read(fd, 65536)
            if not d:
                break
            n += len(d)
        if n:
            dbg(f"flushed {n} buffered mic bytes ({n/(SR*2):.2f}s)")
    except Exception as e:
        log("mic flush err:", e, level="WARN")


def _close_process(p):
    if p is None:
        return
    try:
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=1)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    finally:
        for stream in (p.stdin, p.stdout, p.stderr):
            if stream:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass


def open_mic(previous=None):
    """Retry capture startup and recurring failures without killing the assistant."""
    backoff = getattr(previous, "_reopen_backoff", MIC_REOPEN_BACKOFF_S)
    if previous is not None:
        try:
            _close_process(previous)
        except (OSError, ValueError):
            pass
        time.sleep(backoff)
        backoff = min(MIC_REOPEN_BACKOFF_MAX_S, backoff * 2)
    while True:
        try:
            mic = _open_mic_once()
            mic._reopen_backoff = backoff
            return mic
        except (OSError, ValueError) as e:
            log("mic open failed:", e, level="WARN")
            time.sleep(backoff)
            backoff = min(MIC_REOPEN_BACKOFF_MAX_S, backoff * 2)


def read_samples(mic, n):
    need = n * 2
    buf = b""
    deadline = time.monotonic() + MIC_READ_TIMEOUT_S
    while len(buf) < need:
        try:
            fd = mic.stdout.fileno()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("mic read timeout")
            rdy, _, _ = select.select([fd], [], [], remaining)
            if not rdy:
                raise RuntimeError("mic read timeout")
            # Buffered read(size) may wait for more bytes even after select succeeds.
            chunk = os.read(fd, need - len(buf))
        except (OSError, ValueError) as e:
            raise RuntimeError(f"mic pipe error: {e}") from e
        if not chunk:
            err = b""
            try:
                err = mic.stderr.read() or b""
            except Exception:
                pass
            raise RuntimeError("mic stream ended: " + err.decode("utf8", "ignore")[:160])
        buf += chunk
    arr = np.frombuffer(buf, dtype=np.int16)
    mic._reopen_backoff = MIC_REOPEN_BACKOFF_S
    if MIC_GAIN != 1.0:
        arr = np.clip(arr.astype(np.float32) * MIC_GAIN, -32768, 32767).astype(np.int16)
    return arr


def _play_to_room(pcm_i16, what="audio"):
    global _speaker_failures
    path = "/tmp/openhome-voice-out.wav"
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm_i16.astype(np.int16).tobytes())
    secs = len(pcm_i16) / SR
    t0 = time.time()
    rc, _ = _run(["pw-play", "--target", SPK_NODE, path], timeout=max(10, int(secs) + 10))
    if rc != 0:
        _speaker_failures += 1
        _recover_speaker(reconnect=_speaker_failures >= 2)
        _restart_keepalive()
        rc, _ = _run(["pw-play", "--target", SPK_NODE, path], timeout=max(10, int(secs) + 10))
        if rc != 0:
            _speaker_failures += 1
            _recover_speaker(reconnect=True)
    if rc == 0:
        _speaker_failures = 0
    log(f"play {what}: {secs:.1f}s -> X10 (pw-play rc={rc}, {time.time()-t0:.1f}s)")


def _get_sink_vol():
    try:
        p = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], env=_AENV,
                           timeout=3, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        m = re.search(r"([0-9]+\.[0-9]+)", p.stdout.decode("utf8", "ignore"))
        return float(m.group(1)) if m else None
    except Exception:
        return None


def _set_sink_vol(v):
    _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{max(0.0, min(1.0, v)):.2f}"])


def duck(on, level=None):
    # DUCK_LEVEL (low, ~6%) is for LISTENING — the mic needs the music out of the way.
    # SPEAK_DUCK_LEVEL (higher, ~35%) is for when WE speak a short confirmation: the
    # music stays clearly audible under our voice instead of being cut to near-silent.
    lvl = (level if level is not None else DUCK_LEVEL) if on else 100
    log(f"duck {'ON' if on else 'OFF'} -> music vol {lvl}")
    _run(["soloist", "ctl", "volume", str(lvl)])
    _run(["sc-ctl", "vol", str(lvl)])


def pause_music(snapshot=None):
    # PAUSE (not duck) the music during a wake interaction. A ducked-but-still-active
    # music stream blocks the (later) voice from mixing out to the Bluetooth sink; pausing
    # it lets the voice through. The keepalive stream keeps the sink awake while paused.
    log("music -> pause (for listen + speak)")
    if snapshot is None or snapshot.get("spotify"):
        _run(["soloist", "ctl", "pause"])
    if snapshot is None or snapshot.get("soundcloud"):
        _run(["sc-ctl", "pause"])


def resume_music(snapshot=None):
    log("music -> resume")
    if snapshot is None or snapshot.get("spotify"):
        _run(["soloist", "ctl", "play"])
    if snapshot and snapshot.get("soundcloud"):
        _run(["sc-ctl", "resume"])


def beep(freq=660, ms=120, vol=0.25):
    t = np.arange(int(SR * ms / 1000)) / SR
    tone = (np.sin(2 * np.pi * freq * t) * vol * 32767).astype(np.int16)
    _play_to_room(tone, what="beep")


def _say(text):
    """Low-level: fetch TTS and play it at a clear, BOOSTED level. Does NOT touch the
    music — the caller owns pausing/resuming so audio is sequenced correctly."""
    if not text:
        return
    if not XI_KEY:
        log("(no ELEVENLABS_API_KEY) would say:", text, level="WARN")
        return
    log(f"TTS request: {text!r}")
    t0 = time.time()
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/stream?output_format=pcm_16000",
            headers={"xi-api-key": XI_KEY, "content-type": "application/json"},
            json={"text": text, "model_id": EL_MODEL,
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
            timeout=30,
        )
        if r.status_code != 200:
            log(f"TTS HTTP {r.status_code}: {r.text[:160]}", level="ERROR")
            return
        pcm = np.frombuffer(r.content, dtype=np.int16)
        if SPEECH_COMPRESS and SPEECH_COMPRESS > 1.0:
            x = pcm.astype(np.float32) / 32768.0
            x = np.tanh(x * SPEECH_COMPRESS) / np.tanh(SPEECH_COMPRESS)   # dense/loud, soft-limited
            pcm = (x * 32767 * VOICE_LEVEL).astype(np.int16)
        log(f"TTS ok: {len(r.content)} bytes ({len(pcm)/SR:.1f}s) in {time.time()-t0:.1f}s")
    except Exception as e:
        log("TTS error:", e, level="ERROR")
        return
    # Play exactly like the beep (plain pw-play) — NO wpctl sink-volume change. Changing
    # a Bluetooth sink's volume fires an AVRCP command that can mute/glitch the X10 right
    # as a short clip plays, which was swallowing the announcement.
    _play_to_room(pcm, what="reply")


def speak(text):
    """Speak a reply the industry-standard way (Music Assistant / AudioFocus pattern):
    PAUSE the music so nothing competes, play the voice boosted, then RESUME the music
    after we finish. So the voice is always clear and the song never plays under it."""
    if not text:
        return
    # Just play the voice over the (already ducked, STILL PLAYING) music. We must NOT
    # pause or zero the music: on this Bluetooth speaker that makes the sink go idle and
    # the voice becomes inaudible. Keeping music playing quietly keeps the sink alive so
    # the voice is always heard (same reason the beep is only audible while music plays).
    _say(text)


def transcribe(wav_bytes):
    """Return text (including true silence as ''), or None on STT failure."""
    if not XI_KEY:
        return None
    t0 = time.time()
    try:
        r = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": XI_KEY},
            data={"model_id": EL_STT_MODEL},
            files={"file": ("speech.wav", wav_bytes, "audio/wav")},
            timeout=30,
        )
        if r.status_code != 200:
            log(f"STT HTTP {r.status_code}: {r.text[:160]}", level="ERROR")
            return None
        text = (r.json().get("text") or "").strip()
        log(f"STT ok: {text!r} in {time.time()-t0:.1f}s")
        return text
    except Exception as e:
        log("STT error:", e, level="ERROR")
        return None


NONSPEECH = ("", "clicking", "silence", "blank_audio", "background noise", "music")

_ANNOT = re.compile(r"\[[^\]]*\]")


def strip_annotations(text):
    """Drop STT annotation tags like [beeping], [background noise], [pause] while keeping
    any real spoken words. The wake beep bleeds into the recording and Scribe tags it
    '[beeping]' — without this a real command after the tag (e.g. '[beeping] Shut up')
    would be thrown away as non-speech."""
    return _ANNOT.sub(" ", text or "").replace("  ", " ").strip()


def is_nonspeech(text):
    core = strip_annotations(text)
    return (not core) or core.strip("[]").strip().lower() in NONSPEECH


ROOMS = ("living room", "kitchen", "bedroom", "bathroom", "office", "dining room",
         "dining", "garage", "hallway", "basement", "den", "nursery")


def _detect_room(t):
    for r in ROOMS:
        if r in t:
            return r.title()
    return None


def _hub_room_power(room, on):
    """Flip all lights in a room on/off directly via the hub — no LLM. Returns the
    number of lights that matched (0 = nothing, so the caller falls back to the LLM)."""
    try:
        result = _hub_request("POST", "/lights/command",
                         json={"cmd": "room-power", "room": room, "on": on},
                         timeout=6)
        hint = str(result.get("hint", ""))
        m = re.search(r"(\d+)\s*light", hint)
        return int(m.group(1)) if m else 0
    except Exception as e:
        log("lights cmd error:", e, level="WARN")
        return 0


COLORS = {
    "warm white": (255, 180, 107), "warm": (255, 180, 107), "cool white": (200, 220, 255),
    "white": (255, 255, 255), "red": (255, 0, 0), "crimson": (220, 20, 60),
    "orange": (255, 80, 0), "amber": (255, 140, 0), "yellow": (255, 230, 0),
    "gold": (255, 200, 0), "lime": (120, 255, 0), "green": (0, 255, 0),
    "teal": (0, 180, 180), "cyan": (0, 255, 255), "blue": (0, 0, 255),
    "sky blue": (80, 180, 255), "purple": (160, 0, 255), "violet": (160, 0, 255),
    "magenta": (255, 0, 160), "pink": (255, 60, 160), "hot pink": (255, 0, 120),
}


def _detect_color(t):
    for name in sorted(COLORS, key=len, reverse=True):   # "warm white" before "white"
        if name in t:
            return name, COLORS[name]
    return None, None


def _hub_room_lights(room):
    """Real light ids in a room (via the hub), so we can target them for color."""
    try:
        lights = _hub_request("GET", "/lights/state", timeout=6).get("lights", [])
        return [l["id"] for l in lights
                if l.get("real") and room.lower() in str(l.get("room", "")).lower()]
    except Exception as e:
        log("lights state error:", e, level="WARN")
        return []


def _hub_set_color(lid, rgb):
    try:
        _hub_request("POST", "/lights/command",
                     json={"cmd": "color", "id": lid, "rgb": {"r": rgb[0], "g": rgb[1], "b": rgb[2]}},
                     timeout=6)
        return True
    except Exception as e:
        log("color cmd error:", e, level="WARN")
        return False


def _hub_party(on):
    try:
        _hub_request("POST", "/lights/command", json={"cmd": "party", "on": on}, timeout=8)
        return True
    except Exception as e:
        log("party cmd error:", e, level="WARN")
        return False


# Fast-intent labels that keep the conversation open (invite a follow-up). Everything
# else is a one-shot action: do it, (optionally confirm), and go back to the wake word.
CONVERSATIONAL_FAST = {"greeting"}


def fast_intent(text, snapshot=None):
    """Common commands handled LOCALLY (no LLM round-trip) for instant response.
    Returns None (→ route to LLM), a string label (acted, stay silent), or a
    (label, say) tuple (acted, speak this short confirmation)."""
    t = (text or "").lower().strip().strip(".!?,")
    words = set(t.split())
    # Dismissals: user wants it to go quiet. Handle LOCALLY so we DON'T route to the
    # LLM (which would cheerfully talk back — the opposite of "shut up").
    if t in ("shut up", "shutup", "shush", "hush", "quiet", "be quiet", "stop talking",
             "stop speaking", "never mind", "nevermind", "cancel", "forget it",
             "that's all", "thats all", "nothing", "go away", "shut up jarvis"):
        return "dismiss"
    # Party mode: flash the lights to the music. "party" / "disco" / "rave" / "light show".
    if "party" in t or "disco" in t or "rave" in t or "light show" in t:
        off = any(w in t for w in ("off", "stop", "end", "over", "no more", "normal"))
        if not _hub_party(not off):
            return ("party-error", "Sorry, I couldn't change party mode.")
        return ("party-off" if off else "party", "Party's over." if off else "Party mode!")
    # Lights: turn a room's lights on/off directly via the hub (instant). Requires a
    # command cue (not a question like "is the light on?"). Falls back to the LLM if
    # nothing matched (unknown room / dimming / colors).
    _light_cmd = ("turn" in words or "switch" in words or "put" in words
                  or t.startswith("lights ") or "lights on" in t or "lights off" in t)
    if "light" in t and ("on" in words or "off" in words) and _light_cmd:
        on = not ("off" in words)
        room = _detect_room(t) or "Living Room"
        if _hub_room_power(room, on) > 0:
            return (f"lights-{'on' if on else 'off'}", f"Okay, {room.lower()} lights {'on' if on else 'off'}.")
        return None
    # Lights color: "turn the living room lights red", "make the lights blue", etc.
    if "light" in t and ("turn" in words or "make" in words or "set" in words
                         or "change" in words or t.startswith("lights ")):
        cname, crgb = _detect_color(t)
        if cname:
            room = _detect_room(t) or "Living Room"
            ids = _hub_room_lights(room)
            results = [_hub_set_color(lid, crgb) for lid in ids]
            if results and all(results):
                return (f"lights-{cname}", f"Okay, {room.lower()} lights {cname}.")
            return None
    # Greetings → instant canned reply
    if t in ("hello", "hi", "hey", "yo", "sup", "hey jarvis", "hi jarvis", "hello jarvis",
             "hey there", "what's up", "whats up", "how's it going", "hows it going"):
        return ("greeting", "Hey! What can I do for you?")
    # Time / date → local clock, no LLM
    if t in ("what time is it", "what's the time", "whats the time", "time", "tell me the time",
             "do you have the time", "got the time", "what time is it now"):
        return ("time", f"It's {datetime.now().strftime('%-I:%M %p')}.")
    if t in ("what's the date", "whats the date", "what is the date", "what day is it",
             "what's today", "whats today", "what's today's date", "whats todays date"):
        return ("date", f"It's {datetime.now().strftime('%A, %B %-d')}.")
    if ("skip" in t or "next" in words) and "playlist" not in t:
        before = _soloist_now()
        _run(["soloist", "ctl", "next"])            # advances the track (and auto-plays it)…
        _run(["soloist", "ctl", "pause"])           # …so re-pause it: announcement stays clean + audible
        nowp = None
        for _ in range(6):                          # poll up to ~1.2s for the new track name
            time.sleep(0.2)
            cur = _soloist_now()
            if cur and cur != before:
                nowp = cur
                break
        log(f"skip: new track = {nowp!r}")
        if nowp:
            _say(f"Now playing {nowp}.")            # voice over PAUSED music (sink kept alive) → audible
        return ("skip", None)                       # terminal → finally resumes → new song from ~0:00
    if t in ("pause", "stop", "pause music", "stop music", "stop the music", "pause the music",
             "pause it", "stop it", "pause the song", "stop the song"):
        _run(["soloist", "ctl", "pause"]); _run(["sc-ctl", "pause"]); return "pause"
    if t in ("resume", "unpause", "continue", "play", "keep playing", "resume music",
             "play music", "resume the music", "keep the music going"):
        resume_music(snapshot if snapshot and any(snapshot.values()) else None)
        return "resume"
    if any(p in t for p in ("louder", "volume up", "turn it up", "turn up", "crank it", "bump it up")):
        _run(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "0.12+"]); return "vol-up"
    if any(p in t for p in ("quieter", "volume down", "turn it down", "turn down", "lower it", "lower the volume", "too loud")):
        _run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.12-"]); return "vol-down"
    return None


def agent_call(text):
    payload = {"text": text}
    r = SESSION.post(f"{HUB}/agent", json=payload, headers=_auth_headers(), timeout=12)
    if r.status_code == 401:
        log("hub 401 — re-authenticating", level="WARN")
        hub_login()
        r = SESSION.post(f"{HUB}/agent", json=payload, headers=_auth_headers(), timeout=12)
    r.raise_for_status()
    out = r.json()
    log(f"hub /agent {r.status_code}: reply={out.get('reply')!r}")
    return out


def to_wav(pcm_bytes):
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm_bytes)
    w.close()
    return buf.getvalue()


def record_utterance(mic, wait_s=None):
    """Record one utterance.
      - Wait up to `wait_s` for speech to BEGIN (onset); if nothing, return b"".
      - A frame only counts as speech if webrtcvad says so AND its energy is above
        VOICE_RMS_FLOOR — this keeps ducked MUSIC (which VAD alone flags as speech)
        from being recorded as if it were you talking.
      - Once speech begins, record until SILENCE_MS of quiet, capped at MAX_UTTER_S
        FROM ONSET (so a worst-case bleed can never run the full wait+record)."""
    frames, silence_ms, started = [], 0, time.time()
    onset_t = None
    frame_ms = VAD_FRAME * 1000 // SR
    while True:
        samples = read_samples(mic, VAD_FRAME)
        pcm = samples.tobytes()
        try:
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        except Exception:
            rms = 1e9
        try:
            speech = vad.is_speech(pcm, SR)
        except Exception:
            speech = True
        voiced = speech and rms >= VOICE_RMS_FLOOR   # energy gate rejects ducked music/ambient
        if onset_t is None:
            if voiced:
                onset_t = time.time()
                frames.append(pcm)
            elif (time.time() - started) > (wait_s if wait_s is not None else MAX_UTTER_S):
                return b""                            # never started talking → end quietly
            continue                                  # trim leading silence/music before onset
        frames.append(pcm)
        silence_ms = 0 if voiced else silence_ms + frame_ms
        if silence_ms >= SILENCE_MS and len(frames) > 12:
            break
        if (time.time() - onset_t) > MAX_UTTER_S:
            dbg("record hit MAX_UTTER_S cap")
            break
    dur = len(frames) * VAD_FRAME / SR
    raw = b"".join(frames)
    try:
        peak = int(np.abs(np.frombuffer(raw, dtype=np.int16)).max())
        arms = int(np.sqrt(np.mean(np.frombuffer(raw, dtype=np.int16).astype(np.float32) ** 2)))
    except Exception:
        peak = arms = 0
    log(f"recorded {dur:.1f}s peak={peak}/32767 ({peak*100//32767}%) rms={arms}")
    return raw


def main():
    log(f"starting: hub={HUB} wake={OWW_MODEL} mic={MIC_ALSA} spk={SPK_NODE} "
        f"voice={VOICE} duck={DUCK_LEVEL} log={LOG_FILE}")
    hub_login()
    _start_keepalive()   # keep the X10 BT sink alive so the voice is never eaten by idle
    mic = open_mic()
    log("listening — say the wake word")
    confirm = 0
    try:
        while True:
            try:
                samples = read_samples(mic, BLOCK)
            except RuntimeError as e:
                log("mic recovery:", e, level="WARN")
                mic = open_mic(mic)
                confirm = 0
                _reset_wake()
                continue
            scores = wake.predict(samples)
            top = max(scores.values()) if scores else 0.0
            music = music_playing()
            thr = WAKE_THRESHOLD_MUSIC if music else WAKE_THRESHOLD
            need = WAKE_CONFIRM_MUSIC if music else 1
            if WAKE_DIAG and top >= WAKE_DIAG:
                log(f"wake score={top:.2f} (thr={thr:.2f}, mode={'music' if music else 'quiet'}) "
                    f"{'FIRE' if top >= thr else 'miss'}")
            if top < thr:
                confirm = 0
                continue
            confirm += 1
            if confirm < need:
                continue        # need a few consecutive frames in music mode
            confirm = 0
            if True:
                log(f"WAKE detected (score={top:.2f}, mode={'music' if music else 'quiet'}, thr={thr:.2f})")
                music = music_playing(fresh=True)
                snapshot = dict(_music_sources)
                beep()
                _reset_wake()
                if music:
                    pause_music(snapshot)   # Only sources freshly observed playing may resume.
                resume = True
                try:
                    # Conversation: first turn after the wake word, then keep listening
                    # for follow-ups (no wake word) until the user goes quiet.
                    for turn in range(MAX_TURNS):
                        # Same "prepare to listen" recipe every turn: let any playback
                        # (wake beep, or our reply + follow-up beep) finish landing in
                        # the single capture pipe, FLUSH it so the buffer starts clean,
                        # then record ONE utterance with an onset grace window. One
                        # lane, one buffer, one message at a time — no overlap.
                        grace = WAKE_GRACE_MUSIC_S if music else WAKE_GRACE_S
                        if turn == 0:
                            time.sleep(BEEP_SETTLE_S)      # let the wake beep land
                            flush_mic(mic)                 # clean start
                        else:
                            time.sleep(FOLLOWUP_SETTLE_S)  # let the reply's BT-delayed tail land
                            flush_mic(mic)                 # drop it (don't transcribe our own reply)
                            beep()                         # cue: talk now
                            time.sleep(BEEP_SETTLE_S)      # let the beep land
                            flush_mic(mic)                 # drop the beep too
                        try:
                            pcm = record_utterance(mic, wait_s=grace)
                        except RuntimeError as e:
                            log("mic recovery during recording:", e, level="WARN")
                            mic = open_mic(mic)
                            break   # Discard the interrupted utterance, then return to wake detection.
                        if not pcm:
                            log(f"no speech within {grace:.1f}s grace — ending"
                                + (" conversation" if turn else ""))
                            break
                        text = transcribe(to_wav(pcm))
                        if text is None:
                            speak("I'm having trouble hearing right now.")
                            break
                        if is_nonspeech(text):
                            log(f"non-speech ({text!r}) — ignoring")
                            break   # silence/noise ends the conversation
                        clean = strip_annotations(text)   # drop [beeping] etc., keep real words
                        if clean != text:
                            log(f"cleaned transcript: {text!r} -> {clean!r}")
                        text = clean
                        fi = fast_intent(text, snapshot)
                        if fi:
                            label, say = fi if isinstance(fi, tuple) else (fi, None)
                            log(f"FAST intent '{label}' — no LLM, instant")
                            if label == "dismiss":
                                break   # explicit end: go quiet, no follow-up
                            if label in ("pause", "resume"):
                                resume = False   # The explicit transport command already ran.
                            if say:
                                speak(say)
                            # Action commands (skip/pause/lights/volume/time…) are one-shot:
                            # do it and go back to sleep — NO follow-up beep. Only things
                            # that invite more (a greeting) keep the conversation open.
                            if label in CONVERSATIONAL_FAST:
                                continue
                            break
                        try:
                            out = agent_call(text)
                        except Exception as e:
                            log("hub error:", e, level="ERROR")
                            speak("Sorry, I couldn't reach the hub.")
                            break
                        speak(out.get("reply") or "Okay.")
                        if re.search(r"\b(pause[ds]?|stop(?:ped)?|resume[ds]?|play(?:ing)?)\b", text, re.I) and out.get("actions"):
                            resume = False   # Do not undo an explicit hub media command.
                        # If the agent actually DID something (played music, lights, a
                        # scene…) it's a one-shot command → sleep. A pure conversational
                        # reply (no action) keeps the turn open for a natural back-and-forth.
                        if out.get("actions"):
                            break
                finally:
                    if music and resume:
                        resume_music(snapshot)
                    _reset_wake()
                    log("ready — listening again")
    finally:
        try:
            _close_process(mic)
        except Exception:
            pass


def _reset_wake():
    try:
        wake.reset()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log("FATAL:", e, level="ERROR")
        raise
