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

// Music level while we speak, as a percentage OF AMPLITUDE — see sliderFor().
// The voice has to win against a playlist at 100% on a Bluetooth speaker
// across the room, but the jazz should still be there underneath.
const DUCK = Number(process.env.OPEN_HOME_SPEAK_DUCK ?? 22);
// mpv's software gain for the voice itself. TTS output is mastered much
// quieter than streamed music, so matching levels is not enough.
const VOICE_GAIN = String(process.env.OPEN_HOME_SPEAK_GAIN ?? 130);
// Music level while the house is LISTENING. Lower than the speaking duck: the
// microphone has to pick a voice out of whatever is playing, and it is across
// the room from the speaker. Low, not off — you should still hear it playing.
const LISTEN_DUCK = Number(process.env.OPEN_HOME_LISTEN_DUCK ?? 15);

/**
 * Percent of amplitude -> the number `wpctl set-volume` wants.
 *
 * These are not the same scale, which is a trap worth spelling out because it
 * cost us an inaudible duck. Measured on this Pi against a live Spotify stream:
 *
 *     wpctl set-volume 72 1.00   ->  channelVolumes [1.0,      1.0     ]
 *     wpctl set-volume 72 0.63   ->  channelVolumes [0.250047, 0.250047]
 *     wpctl set-volume 72 0.25   ->  channelVolumes [0.015625, 0.015625]
 *
 * wpctl's argument is a perceptual slider; PipeWire stores amplitude, and the
 * slider is cubed on the way in. So "duck to 25%" set the music to 1.6% of
 * amplitude — about -36 dB, which is silence, not background. Asking for 25%
 * of amplitude means handing wpctl 0.63.
 */
const sliderFor = (pct: number) => Math.cbrt(Math.max(0, Math.min(100, pct)) / 100);

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

// Stream ids from the most recent graph read.
//
// Reading the graph is not cheap here: open-home-hub carries CPUQuota=30%, and
// a pw-dump plus a JSON.parse of the whole graph inside that budget measures
// 600 ms — sometimes 1.4 s. That is the delay between the wake cue and the
// music dropping, and no amount of running it earlier fixes it.
//
// So ducking fires at the ids we already know about FIRST, which is a single
// wpctl, then reconciles against a fresh read. Stream ids are stable for the
// life of a playback session, so the guess is right almost always and wrong
// only harmlessly: wpctl says "Node N not found" for a dead id and we catch
// any genuinely new stream a moment later.
let knownStreams: number[] = [];

/** One pw-dump, parsed once: every playback stream with its perceptual level. */
async function snapshot(): Promise<StreamNode[]> {
  const dump = await run_("pw-dump", []);
  try {
    const out = (JSON.parse(dump) as any[])
      .filter((n) => n?.type === "PipeWire:Interface:Node" &&
        String(n?.info?.props?.["media.class"] ?? "").startsWith("Stream/Output/Audio") &&
        // Soloist exposes two nodes per playback and only one of them has a
        // volume control; wpctl answers "Node N does not support volume" for
        // the other. Keeping it in the set made every duck log a phantom
        // stream it had not actually changed.
        Array.isArray(n?.info?.params?.Props?.[0]?.channelVolumes) &&
        // Never our own voice. run() avoids it by snapshotting before mpv
        // starts, but anything that reads the graph DURING speech would
        // otherwise remember the voice as something to duck next time.
        n.info.props["application.name"] !== VOICE_APP)
      .map((n) => ({
        id: n.id as number,
        name: String(n.info.props["application.name"] ?? n.info.props["node.name"] ?? "?"),
        // Stored as amplitude; report the perceptual level, which is what the
        // numbers we set are in. See sliderFor().
        level: Math.cbrt(n.info.params.Props[0].channelVolumes[0] ?? 0),
      }));
    knownStreams = out.map((n) => n.id);
    return out;
  } catch {
    return [];
  }
}

// Report amplitude, which is the same unit the DUCK numbers are in. Reporting
// the perceptual value instead made "ducked to 22%" and "Spotify=0.60" look
// like a contradiction when they are the same thing.
const describe = (ns: StreamNode[]) =>
  ns.map((n) => `${n.name}=${(n.level ** 3 * 100).toFixed(0)}%`).join(" ") || "(no streams)";

/** Set every given stream to `pct` percent of amplitude. */
async function setStreamVolumes(ids: number[], pct: number): Promise<void> {
  if (!ids.length) return;
  const slider = sliderFor(pct).toFixed(3);
  // In parallel. Each wpctl is a process spawn on a Pi; doing them in sequence
  // staggered the duck across the streams, which is audible as a lurch when
  // Soloist has two.
  await Promise.all(ids.map((id) => sh("wpctl", ["set-volume", String(id), slider])));
  vlog(`set streams [${ids.join(",")}] -> ${pct}% amplitude (slider ${slider})`);
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

// Streams ducked because the house is LISTENING, not because it is speaking.
// Held across the whole turn so the music stays down from the wake cue until
// the exchange ends, instead of popping back up in every gap.
let listenDuck: number[] | null = null;

/**
 * Duck for listening — called the moment the wake word fires.
 *
 * Music at full volume while you are talking hurts twice: the mic has to pick
 * your voice out of it, and you have to talk over it. Dropping it at the cue
 * rather than when the reply begins means the room goes quiet as soon as the
 * house is paying attention.
 */
export async function duckForListening(on: boolean): Promise<void> {
  if (on) {
    if (listenDuck) return;
    const t0 = Date.now();
    const guess = knownStreams.slice();
    // The whole point: drop the music with one wpctl, before reading the graph.
    if (guess.length) {
      await setStreamVolumes(guess, LISTEN_DUCK);
      vlog(`listening: ducked [${guess.join(",")}] -> ${LISTEN_DUCK}% in ${Date.now() - t0}ms (known streams)`);
    }
    listenDuck = guess;
    // Now check we did not miss anything — a track started since the last read,
    // or nothing had ever been read. Slow, but off the critical path.
    const fresh = (await snapshot()).map((n) => n.id);
    const missed = fresh.filter((id) => !guess.includes(id));
    // The turn may have ended while we were reading the graph; do not duck
    // into a room that has already been given its music back.
    if (!listenDuck) { vlog("listening: ended before the graph read finished"); return; }
    if (missed.length) {
      await setStreamVolumes(missed, LISTEN_DUCK);
      vlog(`listening: also ducked [${missed.join(",")}] (new since last read)`);
    }
    // Keep the dead ids too: restoring one is a no-op, and dropping one we did
    // duck would leave the music quiet for the rest of the day.
    if (listenDuck) listenDuck = [...new Set([...guess, ...fresh])];
    vlog(`listening: ducked in ${Date.now() - t0}ms total`);
    return;
  }
  if (!listenDuck) return;
  const ids = listenDuck;
  listenDuck = null;
  await setStreamVolumes(ids, 100);
  vlog(`listening: restored [${ids.join(",")}]`);
}

let current: ReturnType<typeof spawn> | null = null;

/** True while audio is actually playing — the client waits on this before it
 *  listens again, or it records the house talking to itself. */
export function speaking(): boolean { return current !== null; }

// Bumped by stop(). Anything already waiting in the queue was asked for before
// the interruption, so it is no longer wanted: "Hey Jarvis — stop" during the
// morning report has to kill the sentence that is playing AND the rest of the
// briefing behind it, or the house goes quiet for a second and then carries
// blithely on, which is worse than not stopping at all.
let generation = 0;

/** Kill the player, nothing more. "Newest utterance wins" uses this. */
function kill(): void {
  if (current) { try { current.kill("SIGTERM"); } catch { /* already gone */ } current = null; }
}

/**
 * Stop whatever is being spoken right now, and drop anything queued behind it.
 *
 * Distinct from kill() on purpose: run() kills the previous utterance every
 * time it starts, and if that also bumped the generation then queuing two
 * passages back to back would silently discard the second one.
 */
export function stop(): void {
  generation++;
  kill();
  log(`stopped (generation ${generation})`);
}

// One utterance at a time, newest wins. Two overlapping replies are worse than
// a truncated one, and the morning report is long enough to collide with
// anything said after it.
let queue: Promise<void> = Promise.resolve();

export function speak(text: string): Promise<void> {
  const clean = speakable(text);
  if (!clean || !enabled()) return Promise.resolve();
  const gen = generation;
  queue = queue.catch(() => {}).then(() => {
    if (gen !== generation) { vlog(`dropped ${clean.length} chars — interrupted before it played`); return; }
    return run(clean);
  });
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
  // If the turn already ducked for listening, leave that in place and do not
  // restore it here — the client lifts it when the conversation ends.
  const music = listenDuck ? [] : graph.map((n) => n.id);
  vlog(`levels before: ${describe(graph)}${listenDuck ? " (already ducked for listening)" : ""}`);
  if (!stream) { log("no provider could synthesize"); return; }

  kill();
  // Duck and start playback together. Ducking first left the room quiet for
  // however long synthesis took, which is exactly the pause that made this
  // feel broken.
  await setStreamVolumes(music, DUCK);

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
    await setStreamVolumes(music, 100);
    await levels("after");
  }
  log(`spoke ${text.length} chars via ${provider()} in ${Date.now() - started}ms (duck=${DUCK}% gain=${VOICE_GAIN})`);
}
