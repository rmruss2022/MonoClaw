/**
 * Snapcast control-plane integration — synchronized multi-room playback.
 *
 * snapserver runs on the hub and streams sample-synced PCM to one snapclient per
 * speaker; this module drives snapserver's JSON-RPC control API (TCP :1705,
 * newline-delimited JSON-RPC 2.0) to:
 *   - read groups/clients/streams (Server.GetStatus)
 *   - push calibration to each client: delay → Client.SetLatency, trim → volume
 *   - group a room's speakers so they play one stream in perfect sync
 *     (Group.SetClients)
 *
 * Capability-aware: if snapserver isn't reachable (e.g. a cloud host with no
 * audio pipeline) every call degrades to "unavailable" — the audible layer needs
 * snapserver + clients running on the hub (see /docs/run-hub).
 */
import net from "node:net";

const HOST = process.env.SNAPCAST_HOST || "127.0.0.1";
const PORT = Number(process.env.SNAPCAST_PORT || 1705);

let idc = 0;
function request<T = any>(method: string, params: any = {}, timeoutMs = 2500): Promise<T> {
  return new Promise((resolve, reject) => {
    const id = ++idc;
    let buf = "";
    const sock = net.createConnection({ host: HOST, port: PORT });
    const to = setTimeout(() => { sock.destroy(); reject(new Error("snapcast_timeout")); }, timeoutMs);
    sock.on("connect", () => sock.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\r\n"));
    sock.on("data", (d) => {
      buf += d.toString();
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
        if (!line) continue;
        try { const msg = JSON.parse(line); if (msg.id === id) { clearTimeout(to); sock.end();
          if (msg.error) reject(new Error(msg.error.message || "snapcast_error")); else resolve(msg.result); return; } } catch {}
      }
    });
    sock.on("error", (e) => { clearTimeout(to); reject(e); });
  });
}

export interface SnapClient { id: string; name: string; ip: string; connected: boolean; latency: number; volume: number; muted: boolean; groupId: string; }
export interface SnapGroup { id: string; name: string; stream: string; clientIds: string[]; }
export interface SnapStatus { groups: SnapGroup[]; clients: SnapClient[]; streams: string[]; }

function normalize(res: any): SnapStatus {
  const groups: SnapGroup[] = [], clients: SnapClient[] = [];
  const srv = res?.server ?? res;
  for (const g of srv?.groups ?? []) {
    const clientIds: string[] = [];
    for (const c of g.clients ?? []) {
      clientIds.push(c.id);
      clients.push({
        id: c.id, name: c.config?.name || c.host?.name || c.id, ip: c.host?.ip || "",
        connected: !!c.connected, latency: c.config?.latency ?? 0,
        volume: c.config?.volume?.percent ?? 100, muted: !!c.config?.volume?.muted, groupId: g.id,
      });
    }
    groups.push({ id: g.id, name: g.name || "", stream: g.stream_id || "", clientIds });
  }
  const streams = (srv?.streams ?? []).map((s: any) => s.id);
  return { groups, clients, streams };
}

let lastAvailable = false;
let cachedStatus: SnapStatus | null = null;
export function availableCached(): boolean { return lastAvailable; }
export function cached(): { available: boolean; groups: SnapGroup[]; clients: number } {
  return { available: lastAvailable, groups: cachedStatus?.groups ?? [], clients: cachedStatus?.clients.length ?? 0 };
}
export async function refresh(): Promise<void> { cachedStatus = await getStatus(); }
export async function available(): Promise<boolean> {
  try { await request("Server.GetStatus", {}, 1200); lastAvailable = true; } catch { lastAvailable = false; }
  return lastAvailable;
}
export async function getStatus(): Promise<SnapStatus | null> {
  try { const r = await request("Server.GetStatus"); lastAvailable = true; return normalize(r); }
  catch { lastAvailable = false; return null; }
}

export async function setLatency(clientId: string, ms: number) { return request("Client.SetLatency", { id: clientId, latency: Math.max(0, Math.round(ms)) }); }
export async function setVolume(clientId: string, percent: number, muted = false) { return request("Client.SetVolume", { id: clientId, volume: { muted, percent: Math.max(0, Math.min(100, Math.round(percent))) } }); }
export async function setName(clientId: string, name: string) { return request("Client.SetName", { id: clientId, name }); }
/** Put exactly these clients into one group so they play a stream in sync. */
export async function setGroupClients(groupId: string, clientIds: string[]) { return request("Group.SetClients", { id: groupId, clients: clientIds }); }

const dbToPercent = (db: number) => Math.max(15, Math.min(100, Math.round(100 * Math.pow(10, db / 20))));

/** Find the snapclient whose name/host matches a speaker name (best-effort). */
function matchClient(status: SnapStatus, speakerName: string): SnapClient | undefined {
  const n = (speakerName || "").toLowerCase();
  return status.clients.find((c) => c.name.toLowerCase() === n)
    || status.clients.find((c) => c.name.toLowerCase().includes(n) || n.includes(c.name.toLowerCase()));
}

/** Push a calibration profile onto matching snapclients (delay + level trim). */
export async function applyCalibration(profile: { speakers: Array<{ name?: string; id: string; delayMs: number; trimDb: number }> }): Promise<{ applied: number; total: number }> {
  const status = await getStatus();
  if (!status) return { applied: 0, total: profile.speakers.length };
  let applied = 0;
  for (const sp of profile.speakers) {
    const c = matchClient(status, sp.name || sp.id);
    if (!c) continue;
    try { await setLatency(c.id, sp.delayMs); await setVolume(c.id, dbToPercent(sp.trimDb || 0)); applied++; } catch {}
  }
  return { applied, total: profile.speakers.length };
}

/** Group a room's speakers (by name) into one Snapcast group → synced playback. */
export async function syncRoom(speakerNames: string[]): Promise<{ ok: boolean; grouped: number; reason?: string }> {
  const status = await getStatus();
  if (!status) return { ok: false, grouped: 0, reason: "Snapcast not reachable" };
  const ids = speakerNames.map((n) => matchClient(status, n)?.id).filter(Boolean) as string[];
  if (!ids.length) return { ok: false, grouped: 0, reason: "No matching Snapcast clients (start a snapclient per speaker)" };
  const groupId = status.clients.find((c) => c.id === ids[0])?.groupId || status.groups[0]?.id;
  if (!groupId) return { ok: false, grouped: 0, reason: "No group available" };
  try { await setGroupClients(groupId, ids); return { ok: true, grouped: ids.length }; }
  catch (e) { return { ok: false, grouped: 0, reason: (e as Error).message }; }
}
