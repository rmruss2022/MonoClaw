/**
 * Hub identity + health — powers the in-app hub onboarding ("find your hub →
 * pair → name your home"). The app is served BY the hub, so onboarding here is
 * about confirming the hub is healthy, surfacing its services, and letting you
 * name your home — the front door a top-tier app opens with.
 *
 * Home name + setup-complete flag persist to <data>/home.json.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import os from "node:os";
import * as spotify from "./spotify.ts";
import * as snapcast from "./snapcast.ts";
import * as localAudio from "./localAudio.ts";
import * as localLights from "./localLights.ts";
import * as home from "./home.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);
const STORE = new URL("../.data/home.json", import.meta.url);

interface HomeCfg { homeName: string; setupComplete: boolean; hubName: string; pairedAt: number }
function load(): HomeCfg { try { return JSON.parse(readFileSync(STORE, "utf8")); } catch { return { homeName: "", setupComplete: false, hubName: "", pairedAt: 0 }; } }
function save(c: HomeCfg) { try { mkdirSync(DATA_DIR, { recursive: true }); writeFileSync(STORE, JSON.stringify(c)); } catch (e) { console.log("[hub] save:", (e as Error).message); } }
let cfg = load();

const START = Date.now();

function lanIp(): string {
  const ifs = os.networkInterfaces();
  for (const name of Object.keys(ifs)) {
    for (const a of ifs[name] || []) {
      if (a.family === "IPv4" && !a.internal) return a.address;
    }
  }
  return "127.0.0.1";
}

export function config(): HomeCfg { return { ...cfg }; }

export function setHomeName(name: string): HomeCfg {
  cfg.homeName = String(name || "").slice(0, 60) || cfg.homeName;
  if (!cfg.hubName) cfg.hubName = `openhome · ${os.hostname()}`;
  if (!cfg.pairedAt) cfg.pairedAt = Date.now();
  save(cfg); return { ...cfg };
}
export function completeSetup(): HomeCfg { cfg.setupComplete = true; if (!cfg.pairedAt) cfg.pairedAt = Date.now(); save(cfg); return { ...cfg }; }
export function resetSetup(): HomeCfg { cfg = { homeName: "", setupComplete: false, hubName: "", pairedAt: 0 }; save(cfg); return { ...cfg }; }

/** Full hub status for the onboarding + status screens. */
export async function status(modelLabel: string) {
  const lights = localLights.list();
  const lightCaps = await localLights.capabilities();
  const audioCaps = await localAudio.capabilities();
  const speakers = localAudio.list();
  const snap = snapcast.cached();
  const sum = home.summary();
  return {
    hub: {
      name: cfg.hubName || `openhome · ${os.hostname()}`,
      host: os.hostname(),
      ip: lanIp(),
      platform: `${os.type()} ${os.arch()}`,
      uptimeSec: Math.round(process.uptime()),
      onlineSec: Math.round((Date.now() - START) / 1000),
      model: modelLabel,
      version: "0.1.0",
      online: true,
    },
    home: { name: cfg.homeName, setupComplete: cfg.setupComplete, pairedAt: cfg.pairedAt },
    services: [
      { key: "lights", label: "Lighting", ok: true, detail: `ESPHome ✓${lightCaps.matter ? " · Matter ✓" : " · Matter needs controller"}`, count: lights.length },
      { key: "speakers", label: "Speakers", ok: true, detail: `Wi-Fi ✓${audioCaps.bluetooth ? " · Bluetooth ✓" : " · no BT radio"}`, count: speakers.length },
      { key: "music", label: "Music", ok: spotify.connected(), detail: spotify.connected() ? "Spotify connected" : "Sign in to Spotify" },
      { key: "sync", label: "Multi-room sync", ok: snap.available, detail: snap.available ? `Snapcast · ${snap.clients} clients` : "Start Snapcast on the hub" },
      { key: "agent", label: "Assistant", ok: true, detail: modelLabel },
    ],
    counts: { devices: sum.devices, lights: lights.length, speakers: speakers.length },
  };
}
