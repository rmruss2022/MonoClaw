/**
 * Speaking out loud, from the hub.
 *
 * Until now the only thing that talked was the Pi's own voice client, over
 * ElevenLabs — so when that account ran out of credits the house went mute,
 * and anything triggered from the phone or the web app was silent by design.
 * This puts speech in the hub, where every surface can reach it.
 *
 * ElevenLabs is the default voice — it is the one this house is used to.
 * OpenAI TTS is the automatic fallback, which matters because the failure has
 * already happened: the ElevenLabs account emptied mid-day and reported it as
 * a 401, which reads like bad auth rather than no credit.
 */
import { spawn } from "node:child_process";
import { Readable } from "node:stream";

const OPENAI_KEY = process.env.OPENAI_API_KEY || "";
const ELEVENLABS_KEY = process.env.ELEVENLABS_API_KEY || "";
const ELEVENLABS_VOICE = process.env.ELEVENLABS_VOICE_ID || "";
const OPENAI_VOICE = process.env.OPEN_HOME_TTS_VOICE || "onyx";
// ElevenLabs is the voice this house is used to, so it wins when a key is
// present. OpenAI remains the automatic fallback for the failure that has
// already happened once: the account running out of credits mid-day, which
// surfaces as a 401 that reads like bad auth.
const PREFER = (process.env.OPEN_HOME_TTS || (ELEVENLABS_KEY ? "elevenlabs" : "openai")).toLowerCase();

// Set OPEN_HOME_SPEAK_VERBOSE=0 to quieten this down once it is boring again.
const VERBOSE = process.env.OPEN_HOME_SPEAK_VERBOSE !== "0";
const log = (...a: unknown[]) => console.log("[speech]", ...a);
const vlog = (...a: unknown[]) => { if (VERBOSE) console.log("[speech]", ...a); };

export function enabled(): boolean { return !!(OPENAI_KEY || ELEVENLABS_KEY); }
export function provider(): string {
  if (PREFER === "elevenlabs" && ELEVENLABS_KEY) return "ElevenLabs";
  if (OPENAI_KEY) return "OpenAI TTS";
  if (ELEVENLABS_KEY) return "ElevenLabs";
  return "none";
}

/**
 * Open a STREAMING synthesis response.
 *
 * Both providers can start sending mp3 frames before the whole passage is
 * rendered, and we hand that straight to mpv's stdin. Waiting for the complete
 * file meant the morning report — over two minutes of audio — sat in silence
 * for fifteen seconds with the music already ducked. Streaming turns that into
 * about a second.
 */
async function openStream(text: string, which: "elevenlabs" | "openai"): Promise<{ body: ReadableStream<Uint8Array>; t0: number }> {
  const t0 = Date.now();
  if (which === "elevenlabs") {
    const voice = ELEVENLABS_VOICE || "21m00Tcm4TlvDq8ikWAM";
    const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voice}/stream?output_format=mp3_44100_64`, {
      method: "POST",
      headers: { "xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        model_id: process.env.ELEVENLABS_MODEL || "eleven_turbo_v2_5",
        // Render the opening as soon as possible rather than optimising the
        // whole passage first — the first chunk is what you are waiting on.
        optimize_streaming_latency: Number(process.env.ELEVENLABS_LATENCY ?? 3),
      }),
    });
    if (!r.ok || !r.body) throw new Error(`elevenlabs_tts_${r.status}: ${(await r.text()).slice(0, 160)}`);
    vlog(`stream elevenlabs voice=${voice} chars=${text.length} headers in ${Date.now() - t0}ms`);
    return { body: r.body, t0 };
  }
  const r = await fetch("https://api.openai.com/v1/audio/speech", {
    method: "POST",
    headers: { Authorization: `Bearer ${OPENAI_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "gpt-4o-mini-tts", voice: OPENAI_VOICE, input: text, response_format: "mp3" }),
  });
  if (!r.ok || !r.body) throw new Error(`openai_tts_${r.status}: ${(await r.text()).slice(0, 160)}`);
  vlog(`stream openai voice=${OPENAI_VOICE} chars=${text.length} headers in ${Date.now() - t0}ms`);
  return { body: r.body, t0 };
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
interface StreamNode { id: number; name: string; level: number }

/** One pw-dump, parsed once: every playback stream with its linear level. */
async function snapshot(): Promise<StreamNode[]> {
  const dump = await run_("pw-dump", []);
  try {
    return (JSON.parse(dump) as any[])
      .filter((n) => n?.type === "PipeWire:Interface:Node" &&
        String(n?.info?.props?.["media.class"] ?? "").startsWith("Stream/Output/Audio"))
      .map((n) => ({
        id: n.id as number,
        name: String(n.info.props["application.name"] ?? n.info.props["node.name"] ?? "?"),
        // PipeWire stores a cubic value; the cube root is the linear level.
        level: Math.cbrt(n.info?.params?.Props?.[0]?.channelVolumes?.[0] ?? 0),
      }));
  } catch {
    return [];
  }
}

const describe = (ns: StreamNode[]) =>
  ns.map((n) => `${n.name}=${n.level.toFixed(2)}`).join(" ") || "(no streams)";

async function setStreamVolumes(ids: number[], level: number): Promise<void> {
  for (const id of ids) await sh("wpctl", ["set-volume", String(id), String(level)]);
  if (ids.length) vlog(`set streams [${ids.join(",")}] -> ${level}`);
}

/** Dump every playback stream's level — the thing worth seeing when audio is wrong. */
async function levels(when: string): Promise<void> {
  if (!VERBOSE) return;
  vlog(`levels ${when}: ${describe(await snapshot())}`);
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
      if (hit?.id != null) { await sh("wpctl", ["set-volume", String(hit.id), "1.0"]); vlog(`voice node ${hit.id} -> 1.0 (after ${attempt + 1} tries)`); return; }
    } catch { /* pw-dump raced a graph change */ }
    await new Promise((r) => setTimeout(r, 80));
  }
  log("voice stream never appeared — level not corrected");
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
  const started = Date.now();
  vlog(`say ${text.length} chars, prefer=${PREFER}`);

  const order: Array<"elevenlabs" | "openai"> =
    PREFER === "elevenlabs" && ELEVENLABS_KEY
      ? (OPENAI_KEY ? ["elevenlabs", "openai"] : ["elevenlabs"])
      : OPENAI_KEY ? (ELEVENLABS_KEY ? ["openai", "elevenlabs"] : ["openai"]) : ["elevenlabs"];

  // Ask for the audio and inspect the audio graph at the SAME time. A pw-dump
  // takes well over a second on this Pi, and doing it first simply added that
  // to the delay before anything was heard — the two have nothing to do with
  // each other.
  const [graph, stream] = await Promise.all([
    snapshot(),
    (async () => {
      for (const which of order) {
        try { return await openStream(text, which); }
        catch (e) { log(`${which} failed:`, (e as Error).message); }
      }
      return null;
    })(),
  ]);
  const music = graph.map((n) => n.id);
  vlog(`levels before: ${describe(graph)}`);
  if (!stream) { log("no provider could synthesize"); return; }

  stop();
  // Duck and start playback together. Ducking first left the room quiet for
  // however long synthesis took, which is exactly the pause that made this
  // feel broken.
  await setStreamVolumes(music, DUCK / 100);

  try {
    await new Promise<void>((resolve) => {
      // Read the mp3 from stdin so playback begins on the first frames rather
      // than after the whole passage is rendered.
      // Run the player OUTSIDE the hub's cgroup.
      //
      // open-home-hub carries CPUQuota=30% — 0.3 of one core for the service
      // AND everything it spawns — because a TS recompile at restart used to
      // brown out this Pi's power rail. mpv inherited that budget and had to
      // fight node for it, which is why the voice came out chopped and why a
      // pw-dump that takes 58ms on this box appeared to take seconds. A
      // transient user scope gives playback its own slice: it needs very
      // little CPU, but it needs it reliably.
      const mpvArgs = [
        "--no-video", "--really-quiet", "--no-terminal",
        `--volume=${VOICE_GAIN}`,
        // Generous buffer: a network stream feeding a Bluetooth sink, where an
        // underrun is audible as a gap in the middle of a sentence.
        "--cache=yes", "--cache-secs=30", "--demuxer-readahead-secs=20",
        // Ride a thin cache rather than pausing to refill mid-sentence.
        "--cache-pause=no",
        "--audio-buffer=0.4",
        "--demuxer-lavf-format=mp3",
        "-",
      ];
      const p = spawn("systemd-run", [
        "--user", "--scope", "--quiet",
        `--unit=openhome-voice-${Date.now()}`,
        "--", "mpv", ...mpvArgs,
      ], {
        env: {
          ...process.env,
          XDG_RUNTIME_DIR: process.env.XDG_RUNTIME_DIR || "/run/user/1000",
          // state.restore-props = false tells WirePlumber's restore-stream
          // module to leave this stream's volume alone. Without it the voice
          // was being created at the DUCK level (measured: starts at 0.60,
          // jumps to 1.0 a third of a second later) — audible as the first
          // word or two coming in quiet and then swelling.
          PIPEWIRE_PROPS: `{ application.name = ${VOICE_APP} node.name = ${VOICE_APP} state.restore-props = false state.restore-target = false }`,
        },
        stdio: ["pipe", "ignore", "ignore"],
      });
      current = p;
      vlog(`mpv pid=${p.pid} gain=${VOICE_GAIN} (streaming)`);

      let firstByte = 0;
      Readable.fromWeb(stream!.body as any)
        .on("data", () => {
          if (!firstByte) {
            firstByte = Date.now();
            vlog(`first audio byte ${firstByte - stream!.t0}ms after request`);
          }
        })
        .on("error", (err) => { log("stream error:", err.message); try { p.stdin?.end(); } catch {} })
        .pipe(p.stdin!)
        // mpv exiting early (a newer utterance killed it) closes stdin under us.
        .on("error", () => {});

      unduckVoice().then(() => levels("speaking")).catch(() => {});
      p.on("exit", () => { if (current === p) current = null; resolve(); });
      p.on("error", (err) => { log("mpv:", err.message); if (current === p) current = null; resolve(); });
    });
  } finally {
    // Always restore, even if playback threw or was killed by a newer
    // utterance — otherwise the music stays quiet for the rest of the day.
    await setStreamVolumes(music, 1.0);
    await levels("after");
  }
  log(`spoke ${text.length} chars via ${provider()} in ${Date.now() - started}ms (duck=${DUCK}% gain=${VOICE_GAIN})`);
}
