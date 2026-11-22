/**
 * Cooking mode — the stateful half of the cooking agent.
 *
 * Drives a single active cooking session (one kitchen): step-by-step navigation,
 * named timers with live remaining time, and a durable history of attempts so we
 * can report started/finished counts and completion rate per recipe.
 *
 * Persistence uses the hub's crash-safe durableStore (survives power loss, like
 * lights/scenes). Recipe content comes from recipes.ts.
 */
import { durableStore } from "./durableStore.ts";
import * as recipes from "./recipes.ts";

const DATA_DIR = new URL("../.data/", import.meta.url);

export interface CookTimer {
  id: string;
  label: string;
  durationSec: number;
  startedAt: number;
  endsAt: number;
  done: boolean;
}

export type CookStatus = "active" | "completed" | "abandoned";

export interface Session {
  id: string;
  recipeId: string;
  recipeTitle: string;
  servings: number;
  startedAt: number;
  finishedAt?: number;
  currentStep: number;      // 1-based
  totalSteps: number;
  status: CookStatus;
  timers: CookTimer[];
  notes: string[];
}

export interface Attempt {
  id: string;
  recipeId: string;
  title: string;
  servings: number;
  startedAt: number;
  finishedAt?: number;
  completed: boolean;
}

const sessionStore = durableStore<Session | null>(DATA_DIR, "cooking-session.json", "cooking");
const historyStore = durableStore<Attempt[]>(DATA_DIR, "cooking-history.json", "cooking-history");

let session: Session | null = sessionStore.load(null);
let history: Attempt[] = historyStore.load([]);

const now = () => Date.now();
const id = (p: string) => `${p}_${now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
const saveSession = () => sessionStore.save(session);
const saveHistory = () => historyStore.save(history);

/** Optional notifier fired when a timer finishes (wired to the bus / voice in index.ts). */
let timerNotifier: ((t: CookTimer, s: Session) => void) | null = null;
export function onTimerDone(cb: (t: CookTimer, s: Session) => void): void { timerNotifier = cb; }

/** Compute remaining seconds for a timer (never negative). */
const remaining = (t: CookTimer): number => Math.max(0, Math.round((t.endsAt - now()) / 1000));

/** Public view of the session with live timer remaining + current step text. */
export function view(): (Session & { step?: recipes.Step; timers: Array<CookTimer & { remainingSec: number }> }) | null {
  if (!session) return null;
  const r = recipes.getRecipe(session.recipeId);
  const step = r?.steps.find((s) => s.n === session!.currentStep);
  return {
    ...session,
    step,
    timers: session.timers.map((t) => ({ ...t, remainingSec: remaining(t) })),
  };
}

export function current(): Session | null { return session; }

/** Start a new session; any prior active session is recorded as abandoned. */
export function start(recipeIdOrTitle: string, servings?: number): { ok: boolean; error?: string; session?: ReturnType<typeof view> } {
  const r = recipes.getRecipe(recipeIdOrTitle);
  if (!r) return { ok: false, error: "recipe_not_found" };
  if (session && session.status === "active") finalize("abandoned");

  const s: Session = {
    id: id("cook"),
    recipeId: r.id,
    recipeTitle: r.title,
    servings: servings && servings > 0 ? servings : r.servings,
    startedAt: now(),
    currentStep: 1,
    totalSteps: r.steps.length,
    status: "active",
    timers: [],
    notes: [],
  };
  session = s;
  history.unshift({ id: s.id, recipeId: r.id, title: r.title, servings: s.servings, startedAt: s.startedAt, completed: false });
  history = history.slice(0, 200);
  saveSession(); saveHistory();
  return { ok: true, session: view() };
}

/** Advance a step. Reaching the end auto-completes the session. */
export function next(): { ok: boolean; done?: boolean; session?: ReturnType<typeof view> } {
  if (!session || session.status !== "active") return { ok: false };
  if (session.currentStep >= session.totalSteps) { finalize("completed"); return { ok: true, done: true, session: view() }; }
  session.currentStep += 1; saveSession();
  return { ok: true, done: false, session: view() };
}

export function prev(): { ok: boolean; session?: ReturnType<typeof view> } {
  if (!session || session.status !== "active") return { ok: false };
  session.currentStep = Math.max(1, session.currentStep - 1); saveSession();
  return { ok: true, session: view() };
}

export function goto(step: number): { ok: boolean; session?: ReturnType<typeof view> } {
  if (!session || session.status !== "active") return { ok: false };
  session.currentStep = Math.max(1, Math.min(session.totalSteps, Math.round(step))); saveSession();
  return { ok: true, session: view() };
}

/** Start a named timer. If seconds omitted, use the current step's suggested duration. */
export function addTimer(label?: string, seconds?: number): { ok: boolean; error?: string; timer?: CookTimer & { remainingSec: number } } {
  if (!session || session.status !== "active") return { ok: false, error: "no_session" };
  if (session.timers.filter((t) => !t.done).length >= 10) return { ok: false, error: "too_many_timers" };
  let secs = typeof seconds === "number" && Number.isFinite(seconds) ? seconds : undefined;
  let lbl = typeof label === "string" ? label.trim().slice(0, 60) || undefined : undefined;
  if (!secs) {
    const r = recipes.getRecipe(session.recipeId);
    const step = r?.steps.find((s) => s.n === session!.currentStep);
    secs = step?.durationSec;
    lbl = lbl || step?.timerLabel;
  }
  if (!secs || secs <= 0) return { ok: false, error: "no_duration" };
  secs = Math.min(21600, Math.max(1, Math.round(secs)));
  const t: CookTimer = { id: id("t"), label: lbl || "timer", durationSec: secs, startedAt: now(), endsAt: now() + secs * 1000, done: false };
  session.timers.push(t); saveSession();
  return { ok: true, timer: { ...t, remainingSec: Math.round(secs) } };
}

export function timers(): Array<CookTimer & { remainingSec: number }> {
  if (!session) return [];
  return session.timers.map((t) => ({ ...t, remainingSec: remaining(t) }));
}

export function complete(): { ok: boolean; session?: ReturnType<typeof view> } {
  if (!session) return { ok: false };
  finalize("completed");
  return { ok: true, session: view() };
}

export function abandon(): { ok: boolean } {
  if (!session) return { ok: false };
  finalize("abandoned");
  return { ok: true };
}

function finalize(status: CookStatus): void {
  if (!session) return;
  session.status = status;
  session.finishedAt = now();
  const h = history.find((a) => a.id === session!.id);
  if (h) { h.finishedAt = session.finishedAt; h.completed = status === "completed"; }
  saveHistory();
  // Clear the active session once it's resolved; it lives on in history.
  const resolved = session;
  session = null;
  saveSession();
  void resolved;
}

export function getHistory(limit = 50): Attempt[] { return history.slice(0, limit); }

export function stats(recipeId?: string): { started: number; finished: number; completionRate: number; byRecipe?: Record<string, { started: number; finished: number }> } {
  const rows = recipeId ? history.filter((a) => a.recipeId === recipeId) : history;
  const started = rows.length;
  const finished = rows.filter((a) => a.completed).length;
  const base = { started, finished, completionRate: started ? Math.round((finished / started) * 100) / 100 : 0 };
  if (recipeId) return base;
  const byRecipe: Record<string, { started: number; finished: number }> = {};
  for (const a of history) {
    byRecipe[a.recipeId] = byRecipe[a.recipeId] || { started: 0, finished: 0 };
    byRecipe[a.recipeId].started++;
    if (a.completed) byRecipe[a.recipeId].finished++;
  }
  return { ...base, byRecipe };
}

/** Background tick: mark finished timers and fire the notifier once each. */
setInterval(() => {
  if (!session) return;
  let changed = false;
  for (const t of session.timers) {
    if (!t.done && now() >= t.endsAt) {
      t.done = true; changed = true;
      try { timerNotifier?.(t, session); } catch { /* best effort */ }
    }
  }
  if (changed) saveSession();
}, 1000).unref?.();
