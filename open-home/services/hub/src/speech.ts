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

// Music level while we speak, as a percentage. The voice has to win against a
// playlist at 100% on a Bluetooth speaker across the room; 25 keeps the jazz
// present underneath instead of cutting it to silence.
const DUCK = Number(process.env.OPEN_HOME_SPEAK_DUCK ?? 25);
// mpv's software gain for the voice itself. TTS output is mastered much
// quieter than streamed music, so matching levels is not enough.
const VOICE_GAIN = String(process.env.OPEN_HOME_SPEAK_GAIN ?? 130);

function sh(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, {
      env: { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || "/run/user/1000" },
    });
    p.on("exit", () => resolve());
    p.on("error", () => resolve());
  });
}

/**
 * Duck the music WITHOUT ducking ourselves.
 *
 * `soloist ctl volume 25` looked like the obvious way to do this — it is what
 * the old voice client used — but measurement shows it attenuates *every*
 * stream on the sink, not just Spotify's. The voice came up at 25% too and the
 * report was inaudible under the very music it was meant to talk over.
 *
 * So instead: snapshot the playback streams that exist before we speak, lower
 * exactly those through PipeWire, and restore them afterwards. Our own stream
 * is created after the snapshot, so it is never in the set and plays at full
 * volume. Identifying the music by "what was already playing" also avoids
 * matching on application name, which is useless here — SoundCloud playback is
 * mpv too, and PipeWire does not report a process id for any of them.
 */
async function musicStreams(): Promise<number[]> {
  const dump = await run_("pw-dump", []);
  try {
    return (JSON.parse(dump) as any[])
      .filter((n) =>
        n?.type === "PipeWire:Interface:Node" &&
        String(n?.info?.props?.["media.class"] ?? "").startsWith("Stream/Output/Audio"))
      .map((n) => n.id as number);
  } catch {
    return [];
  }
}

async function setStreamVolumes(ids: number[], level: number): Promise<void> {
  for (const id of ids) await sh("wpctl", ["set-volume", String(id), String(level)]);
}

/**
 * Our voice announces itself as `openhome-voice`, not `mpv`.
 *
 * WirePlumber's restore-stream remembers a volume per application name and
 * re-applies it to every new stream from that app. An earlier version of this
 * code ducked by app-wide volume, which taught it "mpv = 25%" — so every
 * subsequent utterance came back at 25% no matter what we did to the music,
 * and the fix looked like it was failing. A dedicated name gives the voice its
 * own slot, which nothing else writes to.
 *
 * SoundCloud playback is also mpv, so sharing a slot with it would be wrong
 * even without that history.
 */
const VOICE_APP = "openhome-voice";

async function unduckVoice(): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt++) {
    const dump = await run_("pw-dump", []);
    try {
      const hit = (JSON.parse(dump) as any[]).find((n) =>
        n?.type === "PipeWire:Interface:Node" &&
        n?.info?.props?.["application.name"] === VOICE_APP);
      if (hit?.id != null) { await sh("wpctl", ["set-volume", String(hit.id), "1.0"]); return; }
    } catch { /* pw-dump raced a graph change */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  console.log("[speech] voice stream never appeared — level not corrected");
}

function run_(cmd: string, args: string[]): Promise<string> {
  return new Promise((resolve) => {
    const p = spawn(cmd, args, {
      env: { ...process.env, XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || "/run/user/1000" },
    });
    let out = "";
    p.stdout?.on("data", (d) => { out += d; });
    p.on("exit", () => resolve(out));
    p.on("error", () => resolve(""));
  });
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
  // Snapshot before we make any noise of our own.
  const music = await musicStreams();
  await setStreamVolumes(music, DUCK / 100);
  try {
    await new Promise<void>((resolve) => {
      // mpv to the PipeWire default sink, which is the Bluetooth speaker. No
      // video, no terminal UI, and it exits on its own when the clip ends.
      // --volume above 100 is software gain, which TTS needs to sit over music.
      const p = spawn("mpv", ["--no-video", "--really-quiet", "--no-terminal", `--volume=${VOICE_GAIN}`, file], {
        env: {
          ...process.env,
          XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || "/run/user/1000",
          PIPEWIRE_PROPS: `{ application.name = ${VOICE_APP} node.name = ${VOICE_APP} }`,
        },
      });
      current = p;
      unduckVoice().catch(() => {});
      p.on("exit", () => { if (current === p) current = null; resolve(); });
      p.on("error", (err) => { console.log("[speech] mpv:", err.message); if (current === p) current = null; resolve(); });
    });
  } finally {
    // Always restore, even if playback threw or was killed by a newer
    // utterance — otherwise the music stays quiet for the rest of the day.
    await setStreamVolumes(music, 1.0);
  }
  unlink(file).catch(() => {});
  console.log(`[speech] spoke ${text.length} chars via ${provider()} (music ducked to ${DUCK}%)`);
}
