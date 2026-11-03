# OpenHome Voice Client

Turns a Raspberry Pi + mic + speaker into a hands-free voice assistant for your
home. It's just the **ears and mouth** — the brain already lives in the hub:

```
wake word  ──►  record (VAD)  ──►  POST hub /agent/audio  ──►  speak reply (ElevenLabs)
(openWakeWord)   (webrtcvad)        │ transcribe (Gemini)
                                    │ decide     (Claude)
                                    │ RUN actions (lights / speakers / thermostat …)
                                    └ returns {transcript, reply, actions}
```

So "Hey Jarvis, turn the living room lights to 30%" → the hub dims the real
ESPHome bulb **and** the Pi speaks the confirmation.

## Hardware

- **Raspberry Pi 4 (2 GB+)** — the hub Pi is fine; this runs alongside it.
- **Far-field mic with AEC — ReSpeaker Mic Array v2.0** (USB). The onboard XMOS
  DSP gives beamforming + noise suppression + **acoustic echo cancellation**, so
  it hears you *over* its own music/voice. It also has a **3.5 mm audio-out**, so
  a powered speaker plugs straight into it.
  - Budget alt (quiet rooms, no AEC): ReSpeaker 2-Mics Pi HAT.
- **Speaker** — any powered speaker into the mic array's 3.5 mm out, or an I²S
  amp (MAX98357A) + 4 Ω driver for an embedded build.

## Install (on the Pi)

```bash
sudo mkdir -p /opt/openhome-voice
sudo cp voice_client.py /opt/openhome-voice/
python3 -m venv /opt/openhome-voice/.venv
/opt/openhome-voice/.venv/bin/pip install -r requirements.txt
sudo apt-get install -y libportaudio2 ffmpeg   # PortAudio for sounddevice

# Config (holds your ElevenLabs key — keep it 600):
sudo cp voice.env.example /etc/openhome-voice.env
sudo nano /etc/openhome-voice.env            # set ELEVENLABS_API_KEY, hub URL
sudo chmod 600 /etc/openhome-voice.env

# Service:
sudo cp openhome-voice.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openhome-voice
journalctl -u openhome-voice -f             # watch it
```

Try it standalone first: `OPENHOME_HUB_URL=http://localhost:4700 \
ELEVENLABS_API_KEY=... /opt/openhome-voice/.venv/bin/python voice_client.py`,
then say **"Hey Jarvis"**, wait for the beep, and give a command.

## Notes

- **The hub must have Gemini enabled** (`GEMINI_TOKEN`) — that's what powers the
  speech-to-text behind `/agent/audio`. Claude (`ANTHROPIC_KEY`) handles intent.
- **Pick the mic/speaker**: `python -c "import sounddevice; print(sounddevice.query_devices())"`
  then set `MIC_DEVICE` / `SPK_DEVICE` to the ReSpeaker if it isn't the default.
- **Custom "Hey OpenHome" wake word**: train a model with
  [openWakeWord's trainer](https://github.com/dscripka/openWakeWord#training-new-models)
  (a Colab notebook, ~1 hr), drop the `.onnx` on the Pi, and point `OWW_MODEL` at
  its path. Until then `hey_jarvis` / `alexa` / `hey_mycroft` ship built-in.
- **Echo cancellation**: handled in hardware by the ReSpeaker v2.0. On a mic
  without AEC, the device will often hear its own TTS — raise `WAKE_THRESHOLD`
  and keep playback volume modest.
