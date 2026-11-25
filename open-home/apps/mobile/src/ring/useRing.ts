/**
 * The ring, owned by the phone.
 *
 * This is the half that was missing: ble.ts can drive a ring and gestures.ts
 * can recognise one, but nothing connected them to the app or to the hub.
 *
 * WHAT TALKS TO WHAT
 *   ring --BLE--> this hook --HTTP--> hub      (gestures become actions)
 *                      |
 *                      '--> React state        (the screen shows the link)
 *
 * The hub remains the thing that decides what a double tap MEANS — the phone
 * only reports that one happened (POST /ring/gesture). That keeps the meaning
 * in one place for both transports, so the Pi and the phone cannot drift into
 * disagreeing about the same knock.
 *
 * THE NATIVE MODULE IS LOADED LAZILY, ON PURPOSE. react-native-ble-plx cannot
 * run in Expo Go, and the rest of the app still has to work there. So we
 * require() it at connect time and report "needs a dev build" as a state
 * rather than crashing the screen on import.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { PermissionsAndroid, Platform } from "react-native";

import { useCommand } from "@/api/hooks";

import { RingLink, type RingTelemetry } from "./ble";
import type { Gesture } from "./gestures";

export type LinkState =
  | "idle"
  | "unsupported"
  | "scanning"
  | "connecting"
  | "live"
  | "error";

export interface RingHook {
  state: LinkState;
  message: string | null;
  telemetry: RingTelemetry;
  lastGesture: (Gesture & { sentToHub: boolean }) | null;
  /** Newest first, capped — enough to see what the radio did without a console. */
  log: string[];
  connect: () => void;
  disconnect: () => void;
}

/** Keep the phone's telemetry posts rare; gestures are never throttled. */
const STATE_POST_MS = 20_000;

/**
 * Android needs runtime permission before a scan returns anything at all —
 * it does not error, it just silently finds nothing, which is a miserable
 * thing to debug. iOS handles this through the Info.plist strings in app.json.
 */
async function askAndroid(): Promise<string | null> {
  if (Platform.OS !== "android") return null;
  const api = Number(Platform.Version);
  const want =
    api >= 31
      ? [
          PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
          PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
        ]
      : [PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION];
  const got = await PermissionsAndroid.requestMultiple(want);
  const denied = Object.entries(got)
    .filter(([, v]) => v !== PermissionsAndroid.RESULTS.GRANTED)
    .map(([k]) => k.split(".").pop());
  return denied.length ? `Bluetooth permission denied: ${denied.join(", ")}` : null;
}

export function useRing(): RingHook {
  const run = useCommand();
  const runRef = useRef(run);
  runRef.current = run;

  const [state, setState] = useState<LinkState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<RingTelemetry>({ connected: false });
  const [lastGesture, setLastGesture] = useState<(Gesture & { sentToHub: boolean }) | null>(null);
  const [log, setLog] = useState<string[]>([]);

  const link = useRef<RingLink | null>(null);
  const manager = useRef<any>(null);
  const lastStatePost = useRef(0);
  const alive = useRef(true);

  const note = useCallback((line: string) => {
    const stamp = new Date().toLocaleTimeString([], { hour12: false });
    setLog((prev) => [`${stamp}  ${line}`, ...prev].slice(0, 40));
  }, []);

  const disconnect = useCallback(() => {
    const l = link.current;
    link.current = null;
    setState("idle");
    // Fire and forget: stop() writes `a1 02` so the LEDs cannot be left on,
    // and we do not want the UI waiting on a radio that may already be gone.
    l?.stop().catch(() => {});
  }, []);

  // A live BLE connection must not outlive the screen, or the ring stays
  // claimed by a component nobody can see any more.
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      link.current?.stop().catch(() => {});
      link.current = null;
      try {
        manager.current?.destroy();
      } catch {
        /* never constructed */
      }
      manager.current = null;
    };
  }, []);

  const connect = useCallback(() => {
    void (async () => {
      if (link.current) return;

      if (!manager.current) {
        try {
          // eslint-disable-next-line @typescript-eslint/no-require-imports
          const mod = require("react-native-ble-plx");
          manager.current = new mod.BleManager();
        } catch (e) {
          setState("unsupported");
          setMessage(
            "Bluetooth needs a dev build of this app — react-native-ble-plx is a native module and Expo Go cannot load it.",
          );
          note(`native module missing: ${(e as Error).message}`);
          return;
        }
      }

      const denied = await askAndroid();
      if (denied) {
        setState("error");
        setMessage(denied);
        return;
      }

      const l = new RingLink(manager.current, {
        onLog: (line) => alive.current && note(line),
        onTelemetry: (t) => {
          if (!alive.current) return;
          setTelemetry((prev) => ({ ...prev, ...t }));
          if (!t.connected) return;
          // Report upward so the rest of the house (and the web surface) sees
          // the same ring whichever radio is holding it.
          const now = Date.now();
          const interesting = t.battery !== undefined || t.charging !== undefined;
          if (interesting || now - lastStatePost.current > STATE_POST_MS) {
            lastStatePost.current = now;
            void runRef
              .current("/ring/state", {
                battery: t.battery,
                charging: t.charging,
                rssi: t.rssi,
              })
              .catch(() => {});
          }
        },
        onGesture: (g) => {
          if (!alive.current) return;
          // Optimistic in the UI, then corrected: a gesture the hub never
          // received should not look like one that worked.
          setLastGesture({ ...g, sentToHub: false });
          void runRef
            .current("/ring/gesture", { kind: g.kind, value: g.value })
            .then((r) => {
              if (!alive.current) return;
              const ok = !!r;
              setLastGesture({ ...g, sentToHub: ok });
              note(
                ok
                  ? `${g.kind}${g.value != null ? ` ${g.value}°` : ""} -> hub: ${
                      (r as any)?.did ?? "accepted"
                    }`
                  : `${g.kind} -> hub unreachable`,
              );
            })
            .catch(() => {
              if (alive.current) note(`${g.kind} -> hub error`);
            });
        },
      });
      link.current = l;

      try {
        setState("scanning");
        setMessage(null);
        const dev = await l.find();
        if (!alive.current) return;
        setState("connecting");
        await l.connect(dev);
        if (!alive.current) return;
        setState("live");
        // Polling is the data path and it never returns while connected.
        void l.startPolling().catch((e: Error) => {
          if (!alive.current) return;
          setState("error");
          setMessage(e.message);
        });
      } catch (e) {
        if (!alive.current) return;
        link.current = null;
        setState("error");
        setMessage((e as Error).message);
        note(`failed: ${(e as Error).message}`);
      }
    })();
  }, [note]);

  return { state, message, telemetry, lastGesture, log, connect, disconnect };
}
