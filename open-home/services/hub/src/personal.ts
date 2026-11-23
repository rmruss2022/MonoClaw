/**
 * What's going on in MATTHEW's life — as opposed to the house's.
 *
 * The agent used to answer "what's going on?" with a thermostat reading and
 * whether music was playing, because device state was the only context it was
 * ever given. This is the other half: the todo list, the morning digest, the
 * time of day. The assistant is his, not the thermostat's.
 *
 * Everything here is best effort and cached. A slow dashboard must never make
 * the house slow to answer, and stale todos are far better than a pause.
 */
const DASH = (process.env.DASH_URL || "https://dash.bedrock.casa").replace(/\/$/, "");
const TTL_MS = Number(process.env.OPEN_HOME_PERSONAL_TTL_MS ?? 120_000);

interface Todo { text: string; done?: boolean }
interface Cached<T> { at: number; value: T }

let todoCache: Cached<Todo[]> | null = null;
let reportCache: Cached<string> | null = null;

async function getJson(path: string, timeoutMs = 4000): Promise<any | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(`${DASH}${path}`, { signal: ctrl.signal });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export async function todos(): Promise<Todo[]> {
  if (todoCache && Date.now() - todoCache.at < TTL_MS) return todoCache.value;
  const j = await getJson("/api/todo");
  const list: Todo[] = Array.isArray(j?.todos) ? j.todos : [];
  // Keep a stale list on failure rather than pretending he has nothing to do.
  if (!j && todoCache) return todoCache.value;
  todoCache = { at: Date.now(), value: list };
  return list;
}

export async function digest(): Promise<string> {
  if (reportCache && Date.now() - reportCache.at < TTL_MS) return reportCache.value;
  const j = await getJson("/api/report-latest");
  const text = String(j?.report?.spoken ?? j?.report?.text ?? "").trim();
  if (!j && reportCache) return reportCache.value;
  reportCache = { at: Date.now(), value: text };
  return text;
}

function partOfDay(d: Date): string {
  const h = d.getHours();
  if (h < 5) return "the middle of the night";
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  if (h < 21) return "evening";
  return "night";
}

/**
 * A compact brief about Matthew for the system prompt.
 *
 * Deliberately short: this rides on every single request, including "turn off
 * the lights", so it has to be cheap in tokens as well as in latency.
 */
export async function brief(): Promise<string> {
  const now = new Date();
  const [list, rep] = await Promise.all([todos(), digest()]);
  const open = list.filter((t) => !t.done).map((t) => t.text).filter(Boolean);

  const lines = [
    `Right now it is ${now.toLocaleString("en-US", { weekday: "long", hour: "numeric", minute: "2-digit" })} — ${partOfDay(now)}.`,
  ];
  lines.push(open.length
    ? `On Matthew's list: ${open.slice(0, 8).join("; ")}.`
    : `Matthew's todo list is empty.`);
  if (rep) {
    // The digest is the day's news/weather; one line of it is enough for the
    // model to pick up on without reciting the whole thing.
    lines.push(`Today's briefing (only mention if relevant): ${rep.slice(0, 400)}`);
  }
  return lines.join("\n");
}
