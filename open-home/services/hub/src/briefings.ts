/**
 * Custom daily briefings / reports.
 *
 * Define as many briefings as you like — a morning one, an evening wind‑down,
 * a "work focus" report — each a named set of sections (greeting, weather,
 * headlines, calendar, agenda, a quote, or your own custom prompt). Trigger by
 * voice ("good morning", "evening briefing", "give me my focus briefing") or
 * from the app, and the hub composes a warm, spoken‑friendly script.
 *
 * Definitions persist in the hub's crash‑safe durable store. Composition pulls
 * live weather (wttr.in, no key) and personalizes from the user profile; the
 * narrative is written by Claude when a key is present, with a templated
 * fallback otherwise.
 */
import { durableStore } from "./durableStore.ts";
import * as profile from "./profile.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY || "";
const CLAUDE_MODEL = process.env.OPEN_HOME_BRIEFING_MODEL || process.env.CLAUDE_MODEL || "claude-haiku-4-5-20251001";

export type TimeOfDay = "morning" | "afternoon" | "evening" | "night" | "any";
export type SectionType = "greeting" | "weather" | "headlines" | "calendar" | "agenda" | "quote" | "reminders" | "custom";

export interface Section { type: SectionType; prompt?: string; }

export interface Briefing {
  id: string;
  name: string;
  timeOfDay: TimeOfDay;
  phrases: string[];           // extra voice triggers, e.g. ["morning briefing"]
  sections: Section[];
  voice: boolean;              // speak it aloud when triggered
  enabled: boolean;
  createdAt: number;
}

const store = durableStore<Briefing[]>(DATA_DIR, "briefings.json", "briefings");

const SEEDS: Briefing[] = [
  {
    id: "morning", name: "Morning", timeOfDay: "morning",
    phrases: ["good morning", "morning briefing", "my morning briefing"],
    sections: [{ type: "greeting" }, { type: "weather" }, { type: "calendar" }, { type: "headlines" }, { type: "agenda" }],
    voice: true, enabled: true, createdAt: Date.now(),
  },
  {
    id: "evening", name: "Evening", timeOfDay: "evening",
    phrases: ["good evening", "evening briefing", "wind down"],
    sections: [{ type: "greeting" }, { type: "calendar", prompt: "tomorrow" }, { type: "weather", prompt: "tomorrow" }, { type: "reminders" }, { type: "quote" }],
    voice: true, enabled: true, createdAt: Date.now(),
  },
];

let briefings: Briefing[] = (() => {
  const loaded = store.load([]);
  return loaded.length ? loaded : SEEDS;
})();
const save = () => store.save(briefings);
const id = () => `brf_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;

// ---- CRUD --------------------------------------------------------------
export function list(): Briefing[] { return briefings.slice(); }
export function getBriefing(key: string): Briefing | undefined {
  const q = key.trim().toLowerCase();
  return briefings.find((b) => b.id === q) || briefings.find((b) => b.name.toLowerCase() === q);
}

const SECTION_TYPES = new Set<SectionType>(["greeting", "weather", "headlines", "calendar", "agenda", "quote", "reminders", "custom"]);
const TODS = new Set<TimeOfDay>(["morning", "afternoon", "evening", "night", "any"]);

function cleanSections(v: unknown): Section[] | undefined {
  if (!Array.isArray(v)) return undefined;
  return v
    .map((s: any): Section => {
      const out: Section = { type: s?.type };
      if (typeof s?.prompt === "string") out.prompt = s.prompt.slice(0, 300);
      return out;
    })
    .filter((s) => SECTION_TYPES.has(s.type))
    .slice(0, 12);
}

function cleanPhrases(v: unknown): string[] | undefined {
  if (!Array.isArray(v)) return undefined;
  return v.filter((x): x is string => typeof x === "string").map((x) => x.trim()).filter(Boolean).slice(0, 10);
}

function cleanTod(v: unknown): TimeOfDay | undefined {
  return TODS.has(v as TimeOfDay) ? (v as TimeOfDay) : undefined;
}

export function upsert(input: Partial<Briefing> & { name: string }): Briefing {
  const sections = cleanSections(input.sections), phrases = cleanPhrases(input.phrases), timeOfDay = cleanTod(input.timeOfDay);
  const name = String(input.name).trim().slice(0, 80);
  const existing = input.id ? briefings.find((b) => b.id === input.id) : undefined;
  if (existing) {
    Object.assign(existing, {
      name: name || existing.name,
      timeOfDay: timeOfDay ?? existing.timeOfDay,
      phrases: phrases ?? existing.phrases,
      sections: sections?.length ? sections : existing.sections,
      voice: typeof input.voice === "boolean" ? input.voice : existing.voice,
      enabled: typeof input.enabled === "boolean" ? input.enabled : existing.enabled,
    });
    save(); return existing;
  }
  const b: Briefing = {
    id: input.id || id(), name, timeOfDay: timeOfDay || "any",
    phrases: phrases || [], sections: sections?.length ? sections : [{ type: "greeting" }],
    voice: typeof input.voice === "boolean" ? input.voice : true,
    enabled: typeof input.enabled === "boolean" ? input.enabled : true, createdAt: Date.now(),
  };
  briefings.push(b); save(); return b;
}

export function remove(key: string): boolean {
  const before = briefings.length;
  briefings = briefings.filter((b) => b.id !== key && b.name.toLowerCase() !== key.toLowerCase());
  if (briefings.length !== before) { save(); return true; }
  return false;
}

/** Match a spoken phrase to a briefing. */
export function matchPhrase(text: string): Briefing | undefined {
  const t = text.toLowerCase();
  return briefings.filter((b) => b.enabled).find((b) => b.phrases.some((p) => t.includes(p.toLowerCase())));
}
export function forTimeOfDay(tod: TimeOfDay): Briefing | undefined {
  return briefings.find((b) => b.enabled && b.timeOfDay === tod);
}

// ---- composition -------------------------------------------------------
async function weatherFor(city: string, when = "today"): Promise<string> {
  try {
    const r = await fetch(`https://wttr.in/${encodeURIComponent(city)}?format=j1`, { signal: AbortSignal.timeout(6000) });
    if (!r.ok) return "";
    const d: any = await r.json();
    const metric = profile.get().units !== "imperial";
    const cur = d.current_condition?.[0];
    const todayW = d.weather?.[when === "tomorrow" ? 1 : 0];
    const t = (c: string, f: string) => (metric ? `${c}°C` : `${f}°F`);
    if (when === "tomorrow" && todayW) {
      return `Tomorrow in ${city}: ${todayW.hourly?.[4]?.weatherDesc?.[0]?.value || "mixed"}, high ${t(todayW.maxtempC, todayW.maxtempF)}, low ${t(todayW.mintempC, todayW.mintempF)}.`;
    }
    if (cur) {
      return `Right now in ${city}: ${cur.weatherDesc?.[0]?.value}, ${t(cur.temp_C, cur.temp_F)} (feels like ${t(cur.FeelsLikeC, cur.FeelsLikeF)})` +
        (todayW ? `, high ${t(todayW.maxtempC, todayW.maxtempF)} / low ${t(todayW.mintempC, todayW.mintempF)}.` : ".");
    }
    return "";
  } catch { return ""; }
}

async function claudeText(system: string, user: string): Promise<string> {
  if (!ANTHROPIC_KEY) return "";
  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "content-type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01" },
      body: JSON.stringify({ model: CLAUDE_MODEL, max_tokens: 500, system, messages: [{ role: "user", content: user }] }),
      signal: AbortSignal.timeout(12000),
    });
    if (!res.ok) return "";
    const data: any = await res.json();
    return (data?.content ?? []).map((b: any) => b?.text).filter(Boolean).join("").trim();
  } catch { return ""; }
}

const SECTION_HINT: Record<SectionType, string> = {
  greeting: "a short, warm greeting that uses the user's name if known",
  weather: "the weather (use the live weather line provided; don't invent numbers)",
  headlines: "a couple of things worth knowing today, kept brief and non-partisan",
  calendar: "what's on the user's calendar (say it's clear if nothing is provided)",
  agenda: "one encouraging line to set up the day / a small focus suggestion",
  reminders: "any reminders from the user's notes, if relevant",
  quote: "a short, uplifting line to close on",
  custom: "",
};

/** Compose a briefing into a spoken‑friendly script. */
export async function compose(b: Briefing): Promise<{ text: string; usedLive: boolean }> {
  const p = profile.get();
  const city = p.city || "";
  let weatherLine = "";
  const wantsWeather = b.sections.some((s) => s.type === "weather");
  if (wantsWeather && city) {
    const when = b.sections.find((s) => s.type === "weather")?.prompt === "tomorrow" ? "tomorrow" : "today";
    weatherLine = await weatherFor(city, when);
  }

  const sectionList = b.sections.map((s, i) => {
    const hint = s.type === "custom" ? (s.prompt || "a custom section") : SECTION_HINT[s.type];
    return `${i + 1}. ${s.type}${s.prompt && s.type !== "custom" ? ` (${s.prompt})` : ""}: ${hint}`;
  }).join("\n");

  const system = `You are the voice of "openhome", delivering a spoken ${b.timeOfDay} briefing called "${b.name}". ` +
    `Write ONE flowing spoken script (no markdown, no lists, no headers), warm and concise — about 4 to 7 sentences. ` +
    `Only include sections that have content; gracefully skip ones you can't fill.`;
  const user = `User profile: ${profile.contextLine()}.\n` +
    (weatherLine ? `Live weather: ${weatherLine}\n` : "") +
    `Deliver these sections in order:\n${sectionList}\n\nReturn only the spoken script.`;

  const llm = await claudeText(system, user);
  if (llm) return { text: llm, usedLive: !!weatherLine };

  // Fallback (no LLM key): assemble a simple templated briefing.
  const parts: string[] = [];
  const name = p.name ? `, ${p.name}` : "";
  for (const s of b.sections) {
    if (s.type === "greeting") parts.push(`Good ${b.timeOfDay === "any" ? "day" : b.timeOfDay}${name}.`);
    else if (s.type === "weather" && weatherLine) parts.push(weatherLine);
    else if (s.type === "calendar") parts.push("Your calendar looks clear.");
    else if (s.type === "agenda") parts.push("Here's to a good one.");
    else if (s.type === "reminders" && p.notes) parts.push(`A reminder: ${p.notes}.`);
    else if (s.type === "quote") parts.push("Make it a good day.");
    else if (s.type === "custom" && s.prompt) parts.push(s.prompt);
  }
  return { text: parts.join(" ") || `Good ${b.timeOfDay}${name}.`, usedLive: !!weatherLine };
}
