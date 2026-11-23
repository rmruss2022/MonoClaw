/**
 * Speaking out loud, from the hub.
 *
 * Until now the only thing that talked was the Pi's own voice client, over
 * ElevenLabs — so when that account ran out of credits the house went mute,
 * and anything triggered from the phone or the web app was silent by design.
 * This puts speech in the hub, where every surface can reach it.
 *
 * OpenAI TTS is the default because the key is already here for Whisper;
 * ElevenLabs is kept as an override for when its credits come back, since its
 * voices are better.
 */
import { spawn } from "node:child_process";
import { writeFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const OPENAI_KEY = process.env.OPENAI_API_KEY || "";
const ELEVENLABS_KEY = process.env.ELEVENLABS_API_KEY || "";
const ELEVENLABS_VOICE = process.env.ELEVENLABS_VOICE_ID || "";
const OPENAI_VOICE = process.env.OPEN_HOME_TTS_VOICE || "onyx";
// Prefer ElevenLabs only when explicitly asked for: it is the nicer voice but
// the account has been empty, and a failed first attempt costs several seconds
// of silence before the fallback is even tried.
const PREFER = (process.env.OPEN_HOME_TTS || (OPENAI_KEY ? "openai" : "elevenlabs")).toLowerCase();

export function enabled(): boolean { return !!(OPENAI_KEY || ELEVENLABS_KEY); }
export function provider(): string {
  if (PREFER === "elevenlabs" && ELEVENLABS_KEY) return "ElevenLabs";
  if (OPENAI_KEY) return "OpenAI TTS";
  if (ELEVENLABS_KEY) return "ElevenLabs";
  return "none";
}

async function synthOpenAI(text: string): Promise<Buffer> {
  const r = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: { Authorization: `Bearer ${OPENAI_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "gpt-4o-mini-tts", voice: OPENAI_VOICE, input: text, response_format: "mp3" }),
  });
  if (!r.ok) throw new Error(`openai_tts_${r.status}: ${(await r.text()).slice(0, 160)}`);
  return Buffer.from(await r.arrayBuffer());
}

async function synthElevenLabs(text: string): Promise<Buffer> {
  const voice = ELEVENLABS_VOICE || "21m00Tcm4TlvDq8ikWAM";
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voice}?output_format=mp3_44100_64`, {
    method: "POST",
    headers: { "xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ text, model_id: process.env.ELEVENLABS_MODEL || "eleven_turbo_v2_5" }),
  });
  if (!r.ok) throw new Error(`elevenlabs_tts_${r.status}: ${(await r.text()).slice(0, 160)}`);
  return Buffer.from(await r.arrayBuffer());
}

/** Strip things that sound wrong read aloud: emoji, markdown, bare URLs. */
function speakable(text: string): string {
  return text
    .replace(/https?:\/\/\S+/g, "")
    .replace(/[*_`#>]/g, "")
    // Emoji and pictographs — "☀️ Good morning" should not become "sun with
    // rays good morning", and most engines read them as nothing useful.
    .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{2190}-\u{21FF}]/gu, "")
    .replace(/\n{2,}/g, ". ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

let current: ReturnType<typeof spawn> | null = null;

/** Stop whatever is being spoken right now. */
export function stop(): void {
  if (current) { try { current.kill("SIGTERM"); } catch { /* already gone */ } current = null; }
}

// One utterance at a time, newest wins. Two overlapping replies are worse than
// a truncated one, and the morning report is long enough to collide with
// anything said after it.
let queue: Promise<void> = Promise.resolve();

export function speak(text: string): Promise<void> {
  const clean = speakable(text);
  if (!clean || !enabled()) return Promise.resolve();
  queue = queue.catch(() => {}).then(() => run(clean));
  return queue;
}

async function run(text: string): Promise<void> {
  let audio: Buffer;
  try {
    audio = PREFER === "elevenlabs" && ELEVENLABS_KEY
      ? await synthElevenLabs(text)
      : OPENAI_KEY ? await synthOpenAI(text) : await synthElevenLabs(text);
  } catch (e) {
    console.log("[speech] synth failed:", (e as Error).message);
    // One fallback to the other provider before giving up silently.
    try {
      audio = OPENAI_KEY && PREFER === "elevenlabs" ? await synthOpenAI(text) : await synthElevenLabs(text);
    } catch (e2) {
      console.log("[speech] fallback failed:", (e2 as Error).message);
      return;
    }
  }

  const file = join(tmpdir(), `oh-speak-${Date.now()}.mp3`);
  await writeFile(file, audio);
  stop();
  await new Promise<void>((resolve) => {
    // mpv to the PipeWire default sink, which is the Bluetooth speaker. No
    // video, no terminal UI, and it exits on its own when the clip ends.
    const p = spawn("mpv", ["--no-video", "--really-quiet", "--no-terminal", file], {
      env: { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || "/run/user/1000" },
    });
    current = p;
    p.on("exit", () => { if (current === p) current = null; resolve(); });
    p.on("error", (err) => { console.log("[speech] mpv:", err.message); if (current === p) current = null; resolve(); });
  });
  unlink(file).catch(() => {});
  console.log(`[speech] spoke ${text.length} chars via ${provider()}`);
}
