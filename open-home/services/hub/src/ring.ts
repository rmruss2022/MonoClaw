/**
 * The ring, as far as the house is concerned.
 *
 * Two jobs: hold what the ring last told us, and turn a gesture into something
 * happening in the room.
 *
 * WAKING THE VOICE AGENT IS THE HARD PART, and it is worth explaining because
 * it is not obvious. The wake word does not run here — it runs in
 * thin_client.py, which owns the microphone and sits in a loop reading 80 ms
 * frames. The hub has no way to reach into that loop over HTTP.
 *
 * The options were: have the client poll an endpoint (hundreds of needless
 * requests, and latency bounded by the poll interval), have the hub write a
 * file the client stats (same latency problem, plus disk), or give the client
 * something it can check for free on every frame it already reads.
 *
 * So: a UDP datagram to localhost. The client binds a socket and does a
 * non-blocking read once per frame — which costs a syscall it was going to make
 * anyway — and a tap lands within one frame, 80 ms. No polling, no disk, and
 * the whole existing turn machinery (cue, duck, capture, agent, speak) runs
 * exactly as if the wake word had fired, because as far as the client is
 * concerned it did.
 *
 * Fire-and-forget on purpose: if the voice client is not running, the datagram
 * goes nowhere and we say so rather than hanging on a gesture.
 */
import { createSocket } from "node:dgram";
import * as speech from "./speech.ts";
import * as voiceagent from "./voiceagent.ts";

const WAKE_HOST = process.env.OPEN_HOME_WAKE_HOST || "127.0.0.1";
const WAKE_PORT = Number(process.env.OPEN_HOME_WAKE_PORT ?? 4799);

/** What a hold gesture does. A scene id, or "" to disable it. */
const HOLD_SCENE = process.env.OPEN_HOME_RING_HOLD_SCENE ?? "";

export type GestureKind =
  | "tap" | "double_tap" | "triple_tap" | "hold"
  | "music_enter" | "music_volume" | "music_exit";

export interface RingState {
  seen: boolean;
  at: number;
  rssi?: number;
  battery?: number;
  charging?: boolean;
  /** Whether it is actually on a hand. Gates the automation that cares. */
  worn?: boolean;
  steps?: number;
  heartRate?: number;
  firmware?: string;
  lastGesture?: { kind: GestureKind; at: number; value?: number };
  /** Monotonic counters, so a client can tell "new" from "same again". */
  gestures: Record<string, number>;
  musicMode: boolean;
}

const state: RingState = { seen: false, at: 0, gestures: {}, musicMode: false };

export function get(): RingState {
  return { ...state, gestures: { ...state.gestures } };
}

/** Telemetry from whichever client owns the connection (Pi now, phone later). */
export function report(patch: Partial<RingState>): RingState {
  Object.assign(state, patch, { seen: true, at: Date.now() });
  return get();
}

/**
 * Wake the voice client.
 *
 * Returns false only if we could not even send — not whether anyone listened,
 * which UDP cannot tell us. Honest about the distinction rather than claiming
 * success.
 */
export function wakeVoice(why: string): boolean {
  try {
    const sock = createSocket("udp4");
    const msg = Buffer.from(JSON.stringify({ wake: why, at: Date.now() }));
    sock.send(msg, WAKE_PORT, WAKE_HOST, (err) => {
      if (err) console.log("[ring] wake datagram failed:", err.message);
      sock.close();
    });
    console.log(`[ring] wake -> ${WAKE_HOST}:${WAKE_PORT} (${why})`);
    return true;
  } catch (e) {
    console.log("[ring] wake failed:", (e as Error)?.message);
    return false;
  }
}

/**
 * A gesture happened. Do the thing.
 *
 * Deliberately a small, fixed vocabulary rather than anything configurable-by-
 * the-model: a gesture has to do the same thing every time or it is not a
 * control, it is a surprise.
 */
export async function gesture(kind: GestureKind, value?: number): Promise<string> {
  state.gestures[kind] = (state.gestures[kind] ?? 0) + 1;
  state.lastGesture = { kind, at: Date.now(), value };
  state.at = Date.now();
  state.seen = true;

  switch (kind) {
    case "double_tap":
      // The headline feature. Also opens music mode on the ring side, which is
      // why this does not also change the volume.
      return wakeVoice("ring double tap") ? "waking Jarvis" : "could not reach the voice client";

    case "triple_tap": {
      // The one I argued was more useful than the wake: shutting it up. Saying
      // "stop" over a loud speaker fights the speaker; a tap does not.
      const wasSpeaking = speech.speaking();
      speech.stop();
      return wasSpeaking ? "stopped talking" : "nothing was playing";
    }

    case "hold": {
      if (!HOLD_SCENE) return "hold is not bound to anything";
      const r = await voiceagent.runControl(HOLD_SCENE);
      return r ? r.label : `no scene "${HOLD_SCENE}"`;
    }

    case "music_enter":
      state.musicMode = true;
      return "music mode";

    case "music_exit":
      state.musicMode = false;
      return "music mode off";

    case "music_volume": {
      // The ring sends a signed ANGLE from where the hand started, never a
      // volume — the firmware has no business knowing what a volume is.
      //
      // One step per event, rather than computing an absolute level. The ring
      // only emits an event every few degrees of new rotation, so rolling
      // further produces more steps: it behaves like a knob without anyone
      // needing to know the current volume to set the next one. That also
      // reuses the volume fast path, which is already tested against the real
      // sink, instead of a second code path that could disagree with it.
      const deg = Number(value ?? 0);
      const r = await voiceagent.fastPath(
        deg > 0 ? "turn the volume up" : "turn the volume down");
      const label = r?.actions?.[0] ?? `volume ${deg > 0 ? "up" : "down"}`;
      return `${label} (${deg > 0 ? "+" : ""}${deg.toFixed(0)}°)`;
    }

    case "tap":
      // A single tap is deliberately inert. It is the gesture most likely to
      // happen by accident — knocking your hand on a desk — and binding it to
      // anything would make the ring feel haunted.
      return "ignored (single taps are not bound)";
  }
  return "unknown gesture";
}

/** Has the ring said anything recently enough to trust? */
export function fresh(withinMs = 10 * 60_000): boolean {
  return state.seen && Date.now() - state.at < withinMs;
}
