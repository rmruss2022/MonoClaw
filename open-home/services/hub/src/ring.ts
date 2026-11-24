/**
 * Ring control — a wearable trigger for the home.
 *
 * Design: the ring is a *trigger*, not a microphone. A cheap BLE "scrolling
 * ring" (or NFC ring, or the app) fires a button; the hub maps that button to
 * an action — run a scene, toggle lights, send a canned command to the AI, or
 * "wake" the assistant so a room device starts listening. Keeping the mic in
 * the room (not on the ring) sidesteps the hard hardware problems (tiny mic,
 * tiny battery) while still giving you "press to control the home / wake Jarvis".
 *
 * Transport is pluggable and model-agnostic:
 *   - BLE: an OPTIONAL, lazily-imported @abandonware/noble central subscribes to
 *     the ring's HID notifications. Raw report bytes are learned (see learn()),
 *     so ANY ring works without knowing its key codes in advance. If noble isn't
 *     installed or there's no Bluetooth adapter (e.g. the cloud hub), BLE quietly
 *     disables and the HTTP path still works.
 *   - HTTP: POST /ring/press { button } drives the exact same logic, so an NFC
 *     tap from a phone, the app, or a test can trigger actions immediately.
 *
 * Actions are executed through handlers injected by index.ts (wire()), so this
 * module stays decoupled from home/lights/voice — matching the hub's module style.
 *
 * Config persists in the crash-safe durable store (survives power loss).
 */
import { durableStore } from "./durableStore.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

/** Logical buttons. Cheap rings usually expose 2–5 distinct reports; learn maps them. */
export type RingButton = "single" | "double" | "long" | "up" | "down" | "next" | "prev" | "extra";
export const BUTTONS: RingButton[] = ["single", "double", "long", "up", "down", "next", "prev", "extra"];

export interface RingConfig {
  enabled: boolean;
  /** Match a BLE peripheral by case-insensitive name substring (e.g. "ring", "ABShutter"). */
  deviceName: string;
  /** Optional exact BLE address/uuid to pin a specific ring. */
  deviceId: string;
  /** button -> action string. Action forms:
   *   scene:<id> | control:<action> | agent:<text> | wake | webhook:<url> | none */
  mappings: Partial<Record<string, string>>;
  /** Learned raw HID report hex -> logical button, so any ring works. */
  codes: Record<string, string>;
}

const DEFAULT: RingConfig = {
  enabled: false,
  deviceName: "ring",
  deviceId: "",
  mappings: {
    single: "wake",             // press to wake the assistant (room device listens)
    double: "control:lights",   // double-press = toggle all lights
    long: "control:goodnight",  // hold = goodnight scene
    up: "control:music",        // toggle music
    down: "control:away",       // away scene
  },
  codes: {},
};

const store = durableStore<RingConfig>(DATA_DIR, "ring.json", "ring");
let cfg: RingConfig = { ...DEFAULT, ...store.load(DEFAULT) };
cfg.mappings = { ...DEFAULT.mappings, ...(cfg.mappings || {}) };
cfg.codes = cfg.codes || {};
const save = () => store.save(cfg);

export function config(): RingConfig { return { ...cfg, mappings: { ...cfg.mappings }, codes: { ...cfg.codes } }; }

// ---- action wiring (injected by index.ts) ------------------------------
export interface RingActions {
  scene: (id: string) => unknown;
  control: (action: string) => unknown;
  agent: (text: string) => Promise<unknown> | unknown;
  /** Fire the "wake / start listening" signal (index.ts publishes a bus event). */
  wake: () => void;
  publish: (type: string, payload?: unknown) => void;
  log?: (msg: string) => void;
}
let actions: RingActions | null = null;
export function wire(a: RingActions): void { actions = a; }
const log = (m: string) => (actions?.log ? actions.log(m) : console.log(`[ring] ${m}`));

// ---- state -------------------------------------------------------------
let connected = false;
let pendingLearn: string | null = null;     // a RingButton awaiting its next raw report
let lastPress: { button: string; action?: string; source: string; ts: number } | null = null;

export function state() {
  return {
    config: { enabled: cfg.enabled, deviceName: cfg.deviceName, deviceId: cfg.deviceId, mappings: cfg.mappings },
    learnedCodes: Object.keys(cfg.codes).length,
    connected,
    bleAvailable: bleStatus.available,
    bleReason: bleStatus.reason,
    learning: pendingLearn,
    lastPress,
    buttons: BUTTONS,
    actionHelp: "scene:<id> | control:<action> | agent:<text> | wake | webhook:<url> | none",
  };
}

// ---- config edits ------------------------------------------------------
export function update(patch: Partial<RingConfig>): RingConfig {
  if (typeof patch.enabled === "boolean") cfg.enabled = patch.enabled;
  if (typeof patch.deviceName === "string") cfg.deviceName = patch.deviceName.slice(0, 60);
  if (typeof patch.deviceId === "string") cfg.deviceId = patch.deviceId.slice(0, 80);
  if (patch.mappings && typeof patch.mappings === "object") {
    for (const [k, v] of Object.entries(patch.mappings)) {
      if (v == null || v === "") delete cfg.mappings[k];
      else cfg.mappings[k] = String(v).slice(0, 200);
    }
  }
  save();
  return config();
}

/** Arm learn mode: the next raw BLE report (or /ring/learn-code) is bound to `button`. */
export function learn(button: string): { ok: boolean; learning?: string; error?: string } {
  const b = String(button).trim();
  if (!b) return { ok: false, error: "no_button" };
  pendingLearn = b;
  log(`learn armed for "${b}" — press that ring button now`);
  actions?.publish("ring.learning", { button: b });
  return { ok: true, learning: b };
}

/** Bind a specific raw code hex to a button (used by BLE learn, or manual). */
export function learnCode(hex: string, button: string): void {
  cfg.codes[hex] = button;
  save();
  actions?.publish("ring.learned", { hex, button });
  log(`learned ${hex} -> ${button}`);
}

export function forget(): void { cfg.codes = {}; save(); }

// ---- the core: fire a button -------------------------------------------
export async function press(button: string, source = "api"): Promise<{ ok: boolean; button: string; action?: string; result?: unknown; error?: string }> {
  const b = String(button).trim();
  const action = cfg.mappings[b];
  lastPress = { button: b, action, source, ts: Date.now() };
  if (!action || action === "none") {
    actions?.publish("ring.press", { button: b, source, action: null });
    return { ok: false, button: b, error: "unmapped" };
  }
  const i = action.indexOf(":");
  const kind = (i === -1 ? action : action.slice(0, i)).toLowerCase();
  const arg = i === -1 ? "" : action.slice(i + 1);
  let result: unknown;
  try {
    switch (kind) {
      case "scene": result = actions?.scene(arg); break;
      case "control": result = actions?.control(arg); break;
      case "agent": case "say": result = await actions?.agent(arg); break;
      case "wake": case "listen": actions?.wake(); result = { wake: true }; break;
      case "webhook": {
        if (process.env.OPEN_HOME_RING_ALLOW_PRIVATE_WEBHOOKS !== "1" && !isSafeWebhook(arg)) return { ok: false, button: b, action, error: "webhook_blocked" };
        await fetch(arg, { method: "POST", signal: AbortSignal.timeout(6000) }).catch(() => {});
        result = { webhook: arg };
        break;
      }
      default: return { ok: false, button: b, action, error: "unknown_action" };
    }
  } catch (e) {
    return { ok: false, button: b, action, error: String(e) };
  }
  actions?.publish("ring.press", { button: b, action, source });
  log(`press ${b} (${source}) -> ${action}`);
  return { ok: true, button: b, action, result };
}

function isSafeWebhook(raw: string): boolean { let u: URL; try { u = new URL(raw); } catch { return false; } if (u.protocol !== "http:" && u.protocol !== "https:") return false; const h = u.hostname.toLowerCase().replace(/^\[|\]$/g, ""); if (h === "localhost" || h.endsWith(".localhost") || h.endsWith(".local") || h.endsWith(".internal")) return false; if (h === "::1" || h === "::" || h.startsWith("fe80:") || h.startsWith("fc") || h.startsWith("fd")) return false; const m = h.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/); if (m) { const [a, b] = [Number(m[1]), Number(m[2])]; if (a === 0 || a === 10 || a === 127 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127)) return false; } return true; }

// ---- BLE transport (optional, lazily loaded) ---------------------------
const bleStatus: { available: boolean; reason: string } = { available: false, reason: "not_started" };
let noble: any = null;
let activePeripheral: any = null;

/** Scan for nearby BLE peripherals so the user can pick their ring. */
export async function scan(seconds = 6): Promise<{ ok: boolean; reason?: string; devices?: Array<{ id: string; name: string; rssi: number }> }> {
  const n = await loadNoble();
  if (!n) return { ok: false, reason: bleStatus.reason };
  const found = new Map<string, { id: string; name: string; rssi: number }>();
  const onDiscover = (p: any) => {
    const name = p.advertisement?.localName || "";
    found.set(p.id || p.uuid, { id: p.id || p.uuid, name, rssi: p.rssi });
  };
  n.on("discover", onDiscover);
  try { await n.startScanningAsync([], true); } catch (e) { return { ok: false, reason: String(e) }; }
  await new Promise((r) => setTimeout(r, Math.min(20, Math.max(2, seconds)) * 1000));
  try { await n.stopScanningAsync(); } catch {}
  n.removeListener("discover", onDiscover);
  return { ok: true, devices: [...found.values()].sort((a, b) => b.rssi - a.rssi) };
}

async function loadNoble(): Promise<any> {
  if (noble) return noble;
  try {
    const mod = await import(/* @vite-ignore */ "@abandonware/noble");
    noble = (mod as any).default ?? mod;
    bleStatus.available = true; bleStatus.reason = "ok";
    return noble;
  } catch (e) {
    bleStatus.available = false;
    bleStatus.reason = "noble_not_installed";
    log(`BLE unavailable (${bleStatus.reason}); HTTP /ring/press still works. Install @abandonware/noble on the hub for live ring support.`);
    return null;
  }
}

/** Start the BLE listener. Safe to call anywhere — no-ops cleanly without BLE. */
export async function startBle(): Promise<{ ok: boolean; reason?: string }> {
  if (!cfg.enabled) { bleStatus.reason = "disabled"; return { ok: false, reason: "disabled" }; }
  const n = await loadNoble();
  if (!n) return { ok: false, reason: bleStatus.reason };

  n.on("stateChange", async (s: string) => {
    if (s === "poweredOn" && cfg.enabled) { try { await n.startScanningAsync([], true); } catch {} }
    else { try { await n.stopScanningAsync(); } catch {} }
  });

  n.on("discover", async (p: any) => {
    const name = (p.advertisement?.localName || "").toLowerCase();
    const matchName = cfg.deviceName && name.includes(cfg.deviceName.toLowerCase());
    const matchId = cfg.deviceId && (p.id === cfg.deviceId || p.uuid === cfg.deviceId);
    if (!(matchId || (matchName && !cfg.deviceId))) return;
    try { await n.stopScanningAsync(); } catch {}
    await connectPeripheral(p, n);
  });

  if (n.state === "poweredOn") { try { await n.startScanningAsync([], true); } catch {} }
  log(`BLE listening for ring "${cfg.deviceName || cfg.deviceId}"`);
  return { ok: true };
}

async function connectPeripheral(p: any, n: any): Promise<void> {
  try {
    activePeripheral = p;
    p.once("disconnect", () => {
      connected = false; activePeripheral = null;
      actions?.publish("ring.disconnected", {});
      log("ring disconnected — rescanning");
      if (cfg.enabled) setTimeout(() => { n.startScanningAsync([], true).catch(() => {}); }, 1500);
    });
    await p.connectAsync();
    connected = true;
    actions?.publish("ring.connected", { id: p.id, name: p.advertisement?.localName || "" });
    const { characteristics } = await p.discoverAllServicesAndCharacteristicsAsync();
    // Subscribe to every notify/indicate characteristic; ring HID reports arrive here.
    for (const c of characteristics) {
      if ((c.properties || []).some((x: string) => x === "notify" || x === "indicate")) {
        c.on("data", (buf: Buffer) => onReport(buf));
        try { await c.subscribeAsync(); } catch {}
      }
    }
    log(`ring connected (${p.advertisement?.localName || p.id})`);
  } catch (e) {
    connected = false; activePeripheral = null;
    log(`ring connect failed: ${e}`);
    if (cfg.enabled) setTimeout(() => { n.startScanningAsync([], true).catch(() => {}); }, 2000);
  }
}

/** Decode a raw HID report: learn it if armed, else map to a button and fire. */
function onReport(buf: Buffer): void {
  // Ignore all-zero "key released" frames which most HID rings send between presses.
  if (!buf || buf.length === 0 || buf.every((x) => x === 0)) return;
  const hex = Buffer.from(buf).toString("hex");
  if (pendingLearn) {
    const button = pendingLearn; pendingLearn = null;
    learnCode(hex, button);
    return;
  }
  const button = cfg.codes[hex];
  if (button) { void press(button, "ble"); }
  else { actions?.publish("ring.raw", { hex }); } // surface unknown codes so the UI can offer "learn this"
}
