#!/usr/bin/env python3
"""
OpenHome voice client — turns a Raspberry Pi (+ mic + speaker) into a hands-free
voice assistant for the home.

Flow:
  openWakeWord spots the wake word on the mic
    -> we record until you stop talking (WebRTC VAD endpointing)
    -> POST the clip to the hub's /agent/audio  (it transcribes with Gemini,
       decides with Claude, and RUNS the smart-home actions)
    -> speak the hub's reply with ElevenLabs.

The brain, speech-to-text and home-control all live in the hub already; this is
just the ears and the mouth. Pair it with a far-field mic that has AEC (e.g. the
ReSpeaker Mic Array v2.0) so it can still hear you over its own music/voice.

Config (environment):
  OPENHOME_HUB_URL     hub base URL            (default http://localhost:4700)
  ELEVENLABS_API_KEY   required to speak
  ELEVENLABS_VOICE_ID  ElevenLabs voice id     (default Rachel)
  ELEVENLABS_MODEL     tts model               (default eleven_turbo_v2_5)
  OWW_MODEL            wake-word model/path     (default 'hey_jarvis'; see README
                       for a custom 'Hey OpenHome' model)
  WAKE_THRESHOLD       0..1 wake sensitivity    (default 0.5)
  SILENCE_MS           end-of-speech silence    (default 800)
  MIC_DEVICE/SPK_DEVICE  sounddevice name/index (optional)
"""
import base64
import io
import os
import time
import wave

import numpy as np
import requests
import sounddevice as sd
import webrtcvad
from openwakeword.model import Model as WakeModel

SR = 16000                         # hub wants 16k mono; openWakeWord is 16k too
BLOCK = 1280                       # 80 ms — openWakeWord's native frame
VAD_FRAME = 320                    # 20 ms — WebRTC VAD frame (640 bytes int16)

HUB = os.environ.get("OPENHOME_HUB_URL", "http://localhost:4700").rstrip("/")
XI_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel
EL_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
OWW_MODEL = os.environ.get("OWW_MODEL", "hey_jarvis")
WAKE_THRESHOLD = float(os.environ.get("WAKE_THRESHOLD", "0.5"))
SILENCE_MS = int(os.environ.get("SILENCE_MS", "800"))
MAX_UTTER_S = float(os.environ.get("MAX_UTTER_S", "12"))
MIC_DEVICE = os.environ.get("MIC_DEVICE") or None
SPK_DEVICE = os.environ.get("SPK_DEVICE") or None

vad = webrtcvad.Vad(2)             # 0..3, higher = more aggressive filtering
wake = WakeModel(wakeword_models=[OWW_MODEL])


def beep(freq=660, ms=120, vol=0.25):
    """A short tone to acknowledge the wake word (so you know it's listening)."""
    t = np.arange(int(SR * ms / 1000)) / SR
    tone = (np.sin(2 * np.pi * freq * t) * vol * 32767).astype(np.int16)
    try:
        sd.play(tone, SR, device=SPK_DEVICE)
        sd.wait()
    except Exception:
        pass


def speak(text):
    """Speak a reply via ElevenLabs (streamed raw PCM, so no decoder needed)."""
    if not text:
        return
    if not XI_KEY:
        print("[voice] (no ELEVENLABS_API_KEY) would say:", text)
        return
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/stream?output_format=pcm_16000",
            headers={"xi-api-key": XI_KEY, "content-type": "application/json"},
            json={
                "text": text,
                "model_id": EL_MODEL,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
            },
            timeout=30,
        )
        r.raise_for_status()
        pcm = np.frombuffer(r.content, dtype=np.int16)
        sd.play(pcm, SR, device=SPK_DEVICE)
        sd.wait()
    except Exception as e:
        print("[voice] TTS error:", e)


def record_utterance(stream):
    """Capture from `stream` until ~SILENCE_MS of silence (or MAX_UTTER_S)."""
    frames, silence_ms, started = [], 0, time.time()
    while True:
        block, _ = stream.read(VAD_FRAME)
        pcm = bytes(block)
        frames.append(pcm)
        try:
            voiced = vad.is_speech(pcm, SR)
        except Exception:
            voiced = True
        silence_ms = 0 if voiced else silence_ms + 20
        if silence_ms >= SILENCE_MS and len(frames) > 12:
            break
        if time.time() - started > MAX_UTTER_S:
            break
    return b"".join(frames)


def to_wav(pcm_bytes):
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm_bytes)
    w.close()
    return buf.getvalue()


def ask_hub(wav_bytes):
    b64 = base64.b64encode(wav_bytes).decode()
    r = requests.post(
        f"{HUB}/agent/audio",
        json={"audio": b64, "mime": "audio/wav"},
        timeout=45,
    )
    r.raise_for_status()
    return r.json()


def main():
    print(f"[voice] hub={HUB} wake={OWW_MODEL} voice={VOICE} — listening")
    with sd.RawInputStream(
        samplerate=SR, channels=1, dtype="int16", blocksize=BLOCK, device=MIC_DEVICE
    ) as stream:
        while True:
            block, _ = stream.read(BLOCK)
            samples = np.frombuffer(bytes(block), dtype=np.int16)
            scores = wake.predict(samples)
            if scores and max(scores.values()) >= WAKE_THRESHOLD:
                print("[voice] wake word detected")
                beep()
                pcm = record_utterance(stream)
                try:
                    out = ask_hub(to_wav(pcm))
                except Exception as e:
                    print("[voice] hub error:", e)
                    speak("Sorry, I couldn't reach the hub.")
                    _reset_wake()
                    continue
                if not out.get("ok", True):
                    speak("The assistant is not available right now.")
                    _reset_wake()
                    continue
                reply = out.get("reply") or "Okay."
                print(f"[voice] heard={out.get('transcript')!r} reply={reply!r}")
                speak(reply)
                _reset_wake()


def _reset_wake():
    """Clear the wake-word buffer so our own speech/beep can't re-trigger it."""
    try:
        wake.reset()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
