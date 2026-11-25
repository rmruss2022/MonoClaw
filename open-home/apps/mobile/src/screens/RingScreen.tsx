import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { SectionTitle, Loading, Empty } from "@/components/ui";
import { colors, radius, font } from "@/theme";
import { useRing } from "@/ring/useRing";

/**
 * The ring.
 *
 * Two halves, and they are deliberately separate:
 *
 *   "Status"     — whatever the hub last heard, from whichever client owned
 *                  the connection. Needs no Bluetooth in this app at all.
 *   "This phone" — this phone holding the BLE link itself (useRing + ble.ts).
 *
 * THE PHONE IS NOW THE PRIMARY TRANSPORT, on measurement rather than taste.
 * The Pi can see the ring but only at -71 to -75 dBm, and at that signal its
 * GATT handshake does not survive: each ATT round trip took 100-300 ms and the
 * link supervision timeout fired before discovery finished. A USB dongle made
 * it worse. The phone is inches from your hand instead of metres.
 *
 * Only one device can hold the ring at a time, so connecting here means the
 * Pi's ring client cannot have it. That is a real trade, and this screen says
 * so rather than hiding it.
 */
interface Gesture { kind: string; at: number; value?: number }
interface RingState {
  seen: boolean;
  at: number;
  rssi?: number;
  battery?: number;
  charging?: boolean;
  worn?: boolean;
  steps?: number;
  heartRate?: number;
  firmware?: string;
  lastGesture?: Gesture;
  gestures: Record<string, number>;
  musicMode: boolean;
}

const GESTURE_LABEL: Record<string, string> = {
  tap: "Tap", double_tap: "Double tap", triple_tap: "Triple tap", hold: "Hold",
  music_enter: "Music mode on", music_volume: "Volume", music_exit: "Music mode off",
};

const BINDINGS: { gesture: string; does: string }[] = [
  { gesture: "Double tap", does: "Wake Jarvis" },
  { gesture: "Triple tap", does: "Stop talking" },
  { gesture: "Hold", does: "Run a scene" },
  { gesture: "Roll (in music mode)", does: "Volume" },
];

function ago(ts?: number): string {
  if (!ts) return "never";
  const s = Math.round((Date.now() - ts) / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

export default function RingScreen() {
  const { data, loading, refresh } = usePoll<RingState>("/ring", 3000);
  const run = useCommand();

  if (loading && !data) return <Loading />;

  // A ring that has never reported is a different thing from a ring that is
  // out of range, and saying so saves a pointless debugging session. It is NOT
  // a reason to hide the phone section — connecting here is how it stops being
  // true.
  if (!data?.seen) {
    return (
      <SafeAreaView style={s.safe}>
        <ScrollView contentContainerStyle={s.body}>
          <Empty text="No ring has reported to the hub yet. Connect it to this phone below, or start the ring client on the Pi." />
          <Phone />
        </ScrollView>
      </SafeAreaView>
    );
  }

  const stale = Date.now() - data.at > 10 * 60_000;

  return (
    <SafeAreaView style={s.safe}>
      <ScrollView contentContainerStyle={s.body}>
        <SectionTitle>Status</SectionTitle>
        <View style={s.card}>
          <Row label="Last heard" value={ago(data.at)} warn={stale} />
          {data.worn !== undefined && (
            <Row label="On your hand" value={data.worn ? "yes" : "no — in the charger?"} warn={!data.worn} />
          )}
          {data.battery !== undefined && (
            <Row
              label="Battery"
              value={`${data.battery}%${data.charging ? " (charging)" : ""}`}
              warn={data.battery < 20 && !data.charging}
            />
          )}
          {data.rssi !== undefined && <Row label="Signal" value={`${data.rssi} dBm`} />}
          {data.heartRate !== undefined && <Row label="Heart rate" value={`${data.heartRate} bpm`} />}
          {data.steps !== undefined && <Row label="Steps today" value={String(data.steps)} />}
          {data.firmware && <Row label="Firmware" value={data.firmware} />}
        </View>

        {data.musicMode && (
          <View style={[s.card, s.music]}>
            <Text style={s.musicText}>Music mode — roll your hand to change the volume</Text>
          </View>
        )}

        <SectionTitle>Last gesture</SectionTitle>
        <View style={s.card}>
          {data.lastGesture ? (
            <Row
              label={GESTURE_LABEL[data.lastGesture.kind] ?? data.lastGesture.kind}
              value={ago(data.lastGesture.at)}
            />
          ) : (
            <Text style={s.dim}>Nothing yet.</Text>
          )}
          {Object.entries(data.gestures ?? {}).length > 0 && (
            <View style={s.counts}>
              {Object.entries(data.gestures).map(([k, n]) => (
                <Text key={k} style={s.count}>
                  {GESTURE_LABEL[k] ?? k} ×{n}
                </Text>
              ))}
            </View>
          )}
        </View>

        <Phone />

        <SectionTitle>What the gestures do</SectionTitle>
        <View style={s.card}>
          {BINDINGS.map((b) => (
            <Row key={b.gesture} label={b.gesture} value={b.does} />
          ))}
        </View>

        {/* The same endpoint the ring's double tap uses, so this is a genuine
            test of that path and a useful push-to-talk button in its own right. */}
        <Pressable
          style={s.wake}
          onPress={async () => { await run("/agent/wake", { source: "app button" }); refresh(); }}
        >
          <Text style={s.wakeText}>Wake Jarvis</Text>
        </Pressable>
        <Text style={s.note}>
          Uses the same path as a double tap — if this works and the ring doesn't,
          the problem is the ring, not the hub.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

/**
 * This phone's own BLE link.
 *
 * The achieved sample rate is shown prominently because it is the one number
 * the gesture feature actually depends on, and it was never measurable over
 * the Pi's weak link. Our own harness caught a natural double tap 10% of the
 * time at 12 Hz and every time at 50 Hz, so this read decides whether taps
 * work at all — hence the plain-language verdict next to it rather than a bare
 * figure the reader has to interpret.
 */
function Phone() {
  const ring = useRing();
  const { state, telemetry: t } = ring;
  const busy = state === "scanning" || state === "connecting";

  const verdict =
    t.hz === undefined
      ? null
      : t.hz >= 45
        ? { text: "fast enough for a natural double tap", warn: false }
        : t.hz >= 25
          ? { text: "marginal — a deliberate double tap may work", warn: true }
          : { text: "too slow for a natural double tap", warn: true };

  return (
    <>
      <SectionTitle>This phone</SectionTitle>
      <View style={s.card}>
        <Row
          label="Link"
          value={
            {
              idle: "not connected",
              unsupported: "needs a dev build",
              scanning: "scanning…",
              connecting: "connecting…",
              live: "connected",
              error: "failed",
            }[state]
          }
          warn={state === "error" || state === "unsupported"}
        />
        {t.hz !== undefined && <Row label="Sample rate" value={`${t.hz} Hz`} />}
        {verdict && <Row label="" value={verdict.text} warn={verdict.warn} />}
        {t.battery !== undefined && (
          <Row label="Battery" value={`${t.battery}%${t.charging ? " (charging)" : ""}`} />
        )}
        {t.rssi !== undefined && <Row label="Signal" value={`${t.rssi} dBm`} />}
        {ring.lastGesture && (
          <Row
            label={GESTURE_LABEL[ring.lastGesture.kind] ?? ring.lastGesture.kind}
            value={ring.lastGesture.sentToHub ? "sent to the hub" : "not reaching the hub"}
            warn={!ring.lastGesture.sentToHub}
          />
        )}
        {ring.message && <Text style={s.dim}>{ring.message}</Text>}

        <Pressable
          style={[s.secondary, busy && s.busy]}
          disabled={busy}
          onPress={() => (state === "live" ? ring.disconnect() : ring.connect())}
        >
          <Text style={s.secondaryText}>
            {state === "live" ? "Disconnect" : busy ? "Working…" : "Connect ring to this phone"}
          </Text>
        </Pressable>
        <Text style={s.note}>
          Only one device can hold the ring at a time — connecting here takes it
          from the Pi.
        </Text>

        {ring.log.length > 0 && (
          <View style={s.logBox}>
            {ring.log.slice(0, 8).map((line, i) => (
              <Text key={i} style={s.logLine}>
                {line}
              </Text>
            ))}
          </View>
        )}
      </View>
    </>
  );
}

function Row({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <View style={s.row}>
      <Text style={s.label}>{label}</Text>
      <Text style={[s.value, warn && s.warn]}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  body: { padding: 16, paddingBottom: 48, gap: 8 },
  card: { backgroundColor: colors.panel, borderRadius: radius.lg, padding: 14, gap: 10 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  label: { color: colors.muted, fontSize: font.small },
  value: { color: colors.text, fontSize: font.small, fontWeight: "600" },
  warn: { color: colors.warn },
  dim: { color: colors.muted, fontSize: font.small },
  counts: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 4 },
  count: { color: colors.muted, fontSize: font.tiny },
  music: { borderWidth: 1, borderColor: colors.purple },
  musicText: { color: colors.purple, fontSize: font.small, fontWeight: "600", textAlign: "center" },
  wake: {
    marginTop: 18, backgroundColor: colors.accent,
    borderRadius: radius.lg, paddingVertical: 15, alignItems: "center",
  },
  wakeText: { color: colors.onAccent, fontSize: font.body, fontWeight: "700" },
  secondary: {
    marginTop: 6, borderWidth: 1, borderColor: colors.line,
    borderRadius: radius.md, paddingVertical: 12, alignItems: "center",
  },
  busy: { opacity: 0.5 },
  secondaryText: { color: colors.text, fontSize: font.small, fontWeight: "600" },
  logBox: { marginTop: 4, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 8, gap: 2 },
  logLine: { color: colors.muted, fontSize: font.tiny, fontVariant: ["tabular-nums"] },
  note: { color: colors.muted, fontSize: font.tiny, textAlign: "center", marginTop: 8 },
});
