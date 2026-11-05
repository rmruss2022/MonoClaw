// Real device transport: a WebSocket client to ws://<host>/ws with a reconnect
// supervisor (exponential backoff), snapshot+delta apply, and typed command
// senders. Implements the shared DeviceConnection seam.

import type { DeviceConnection } from "./connection.ts";
import {
  applyDelta,
  clearDevice,
  setError,
  setLibrary,
  setSnapshot,
  setStatus,
} from "../state.ts";
import {
  clampVolume,
  type AppToDevice,
  type CommandMsg,
  type DeviceToApp,
  type RepeatMode,
  type VapeSetPayload,
} from "../protocol.ts";

const MAX_BACKOFF_MS = 15_000;
const BASE_BACKOFF_MS = 500;

export class DeviceClient implements DeviceConnection {
  private ws: WebSocket | null = null;
  private closedByUs = false;
  private attempt = 0;
  private reconnectTimer: number | null = null;

  constructor(private readonly host: string) {}

  private url(): string {
    // Allow "host", "host:port", or a full "ws://..." string.
    if (this.host.startsWith("ws://") || this.host.startsWith("wss://")) {
      return this.host.replace(/\/$/, "") + "/ws";
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${this.host}/ws`;
  }

  connect(): void {
    this.closedByUs = false;
    setStatus(this.attempt === 0 ? "connecting" : "reconnecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url());
    } catch (err) {
      setError(String(err));
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      setError(null);
      setStatus("connected");
      // Ask for the library up front; snapshot arrives unprompted.
      this.requestLibrary();
    };

    ws.onmessage = (ev) => this.onMessage(ev.data);

    ws.onerror = () => {
      // onclose will follow; keep the error for the Device screen.
      setError("WebSocket error");
    };

    ws.onclose = () => {
      this.ws = null;
      if (this.closedByUs) {
        setStatus("offline");
        return;
      }
      this.scheduleReconnect();
    };
  }

  disconnect(): void {
    this.closedByUs = true;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.onmessage = null;
      try {
        this.ws.close();
      } catch {
        /* ignore */
      }
      this.ws = null;
    }
    clearDevice();
    setStatus("offline");
  }

  private scheduleReconnect(): void {
    setStatus("reconnecting");
    const delay = Math.min(
      MAX_BACKOFF_MS,
      BASE_BACKOFF_MS * 2 ** this.attempt,
    );
    this.attempt++;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closedByUs) this.connect();
    }, delay);
  }

  private onMessage(raw: unknown): void {
    if (typeof raw !== "string") return;
    let msg: DeviceToApp;
    try {
      msg = JSON.parse(raw) as DeviceToApp;
    } catch {
      return;
    }
    switch (msg.t) {
      case "state": {
        const { t: _t, ...snapshot } = msg;
        void _t;
        setSnapshot(snapshot);
        break;
      }
      case "delta":
        applyDelta(msg);
        break;
      case "library":
        setLibrary(msg.tracks);
        break;
    }
  }

  private send(msg: AppToDevice): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private cmd(fields: Omit<CommandMsg, "t">): void {
    this.send({ t: "cmd", ...fields });
  }

  // --- audio ---
  play(): void {
    this.cmd({ audio: "play" });
  }
  pause(): void {
    this.cmd({ audio: "pause" });
  }
  next(): void {
    this.cmd({ audio: "next" });
  }
  prev(): void {
    this.cmd({ audio: "prev" });
  }
  stop(): void {
    this.cmd({ audio: "stop" });
  }
  seek(positionS: number): void {
    this.cmd({ seekS: Math.max(0, Math.round(positionS)) });
  }
  setVolume(volume: number): void {
    this.cmd({ volume: clampVolume(volume) });
  }
  playTrack(id: string): void {
    this.cmd({ playTrack: id });
  }
  setShuffle(on: boolean): void {
    this.cmd({ shuffle: on });
  }
  setRepeat(mode: RepeatMode): void {
    this.cmd({ repeat: mode });
  }

  // --- vape ---
  vapeFire(on: boolean): void {
    this.cmd({ vape: "fire", on });
  }
  vapeSet(payload: VapeSetPayload): void {
    this.cmd({ vapeSet: payload });
  }
  vapeLock(locked: boolean): void {
    this.cmd({ vapeLock: locked });
  }

  // --- vibe ---
  led(preset: string): void {
    this.cmd({ led: { preset } });
  }
  eq(preset: string): void {
    this.cmd({ eq: { preset } });
  }

  // --- misc ---
  requestLibrary(): void {
    this.cmd({ library: true });
  }
}
