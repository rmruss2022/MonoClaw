import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { SectionTitle, Loading, Empty } from "@/components/ui";
import { colors, radius, font } from "@/theme";

/**
 * The ring.
 *
 * Reads hub state rather than talking to the ring over Bluetooth, and that is
 * the architecture rather than a shortcut: at home the Pi owns the BLE
 * connection, so the phone asking the hub is both simpler and more reliable
 * than two radios fighting over one peripheral that accepts a single
 * connection.
 *
 * The away-from-home case DOES need CoreBluetooth in this app — see
 * services/ring-bridge/ARCHITECTURE.md. That is a native-module job
 * (react-native-ble-plx, the bluetooth-central background mode, and state
 * restoration so iOS can relaunch us). This screen is the half that works
 * without any of it, and it is also the screen that will show that data once
 * the native half exists.
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
  // out of range, and saying so saves a pointless debugging session.
  if (!data?.seen) {
    return (
      <SafeAreaView style={s.safe}>
        <Empty text="No ring has reported to the hub yet. Start the ring client on the Pi, or pair the ring in the app once Bluetooth support ships." />
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
  note: { color: colors.muted, fontSize: font.tiny, textAlign: "center", marginTop: 8 },
});
