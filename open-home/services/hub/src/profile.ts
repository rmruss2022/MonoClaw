/**
 * User profile — what the home knows about you.
 *
 * Populated by the intake form (/profile) and used to personalize briefings,
 * scenes, suggestions, and the assistant's voice. Local‑first and durable:
 * stored in the hub's crash‑safe store, never leaves the box.
 */
import { durableStore } from "./durableStore.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

export interface Profile {
  name?: string;
  pronouns?: string;
  city?: string;                 // for weather + local context
  units?: "metric" | "imperial";
  assistantName?: string;        // what to call the assistant (default "Jarvis")
  wakeTime?: string;             // "07:00"
  sleepTime?: string;            // "23:00"
  householdSize?: number;
  interests?: string[];          // music, cooking, fitness, tech, news…
  dietary?: string[];            // vegan, gluten-free… (shared with the cooking agent)
  briefingTopics?: string[];     // weather, headlines, calendar, markets, sports, commute…
  notes?: string;                // anything else the home should remember
  custom?: Record<string, string>;
  updatedAt?: number;
  completedAt?: number;
}

const store = durableStore<Profile>(DATA_DIR, "user-profile.json", "profile");
let profile: Profile = store.load({});

const clean = (p: Partial<Profile>): Partial<Profile> => {
  const src = (p ?? {}) as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const k of ["name", "pronouns", "city", "assistantName", "wakeTime", "sleepTime", "notes"]) {
    const v = src[k];
    if (typeof v !== "string") continue;
    const s = v.trim().slice(0, 500);
    if (s) out[k] = s;
  }
  if (src.units === "metric" || src.units === "imperial") out.units = src.units;
  if (src.householdSize !== undefined) {
    const n = Number(src.householdSize);
    if (Number.isFinite(n)) out.householdSize = Math.min(50, Math.max(1, Math.round(n)));
  }
  for (const k of ["interests", "dietary", "briefingTopics"]) {
    const v = src[k];
    const arr = Array.isArray(v) ? v : typeof v === "string" ? v.split(",") : null;
    if (!arr) continue;
    out[k] = arr.filter((x): x is string => typeof x === "string").map((x) => x.trim()).filter(Boolean).slice(0, 30);
  }
  const c = src.custom;
  if (c && typeof c === "object" && !Array.isArray(c)) {
    const custom: Record<string, string> = {};
    for (const [k, v] of Object.entries(c)) if (typeof v === "string") custom[k] = v;
    out.custom = custom;
  }
  return out as Partial<Profile>;
};

export function get(): Profile { return profile; }

export function update(patch: Partial<Profile>): Profile {
  profile = { ...profile, ...clean(patch), updatedAt: Date.now() };
  if (!profile.completedAt && isComplete(profile)) profile.completedAt = Date.now();
  store.save(profile);
  return profile;
}

export function reset(): void { profile = {}; store.save(profile); }

export function isComplete(p: Profile = profile): boolean {
  return !!(p.name && p.city);
}

export const assistantName = (): string => profile.assistantName?.trim() || "Jarvis";

/** A compact one‑liner the agent/briefings can drop into an LLM prompt. */
export function contextLine(): string {
  const p = profile;
  if (!p.name && !p.city) return "The user hasn't filled out their profile yet.";
  const bits: string[] = [];
  if (p.name) bits.push(`name ${p.name}${p.pronouns ? ` (${p.pronouns})` : ""}`);
  if (p.city) bits.push(`in ${p.city}`);
  if (p.units) bits.push(p.units);
  if (p.householdSize) bits.push(`household of ${p.householdSize}`);
  if (p.interests?.length) bits.push(`likes ${p.interests.join(", ")}`);
  if (p.dietary?.length) bits.push(`diet ${p.dietary.join(", ")}`);
  if (p.notes) bits.push(`notes: ${p.notes}`);
  return bits.join("; ");
}
