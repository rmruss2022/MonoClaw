import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { SectionTitle, Loading, Empty } from "@/components/ui";
import { colors, radius, font } from "@/theme";

interface NowPlaying {
  source?: string; title?: string; artist?: string; album?: string;
  playing?: boolean; positionMs?: number; durationMs?: number; device?: string;
}
interface Room { id: string; name: string; speakers: string[]; online: boolean }
interface State {
  nowPlaying: NowPlaying;
  rooms: Room[];
  counts: { speakers: number; online: number; zones: number };
  spotify?: { connected?: boolean };
}

const fmt = (ms = 0) => {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export default function SpeakersScreen() {
  const { data, loading, refresh } = usePoll<State>("/audio/state", 4000);
  const run = useCommand();

  const transport = async (action: string) => {
    await run("/audio/command", { cmd: "transport", action });
    refresh();
  };
  const playRoom = async (room: string) => {
    await run("/audio/command", { cmd: "play-room", room });
    refresh();
  };

  if (loading && !data) return <Loading />;
  const np = data?.nowPlaying;
  const rooms = data?.rooms ?? [];
  const pct = np?.durationMs ? Math.min(100, ((np.positionMs ?? 0) / np.durationMs) * 100) : 0;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Speakers</Text>
        {data && (
          <Text style={styles.subtitle}>
            {data.counts.online}/{data.counts.speakers} online · {rooms.length} rooms
          </Text>
        )}

        <View style={styles.np}>
          <Text style={styles.npTitle} numberOfLines={1}>{np?.title || "Nothing playing"}</Text>
          <Text style={styles.npArtist} numberOfLines={1}>
            {np?.artist || "Pick a room and hit play"}
            {np?.device ? ` · ${np.device}` : ""}
          </Text>
          <View style={styles.bar}>
            <View style={[styles.barFill, { width: `${pct}%` }]} />
          </View>
          <View style={styles.times}>
            <Text style={styles.time}>{fmt(np?.positionMs)}</Text>
            <Text style={styles.time}>{fmt(np?.durationMs)}</Text>
          </View>
          <View style={styles.transport}>
            <Pressable onPress={() => transport("prev")} style={styles.tbtn}>
              <Text style={styles.tico}>⏮</Text>
            </Pressable>
            <Pressable onPress={() => transport(np?.playing ? "pause" : "play")} style={[styles.tbtn, styles.tmain]}>
              <Text style={styles.ticoMain}>{np?.playing ? "⏸" : "▶"}</Text>
            </Pressable>
            <Pressable onPress={() => transport("next")} style={styles.tbtn}>
              <Text style={styles.tico}>⏭</Text>
            </Pressable>
          </View>
        </View>

        <SectionTitle>Rooms</SectionTitle>
        {rooms.length === 0 && <Empty text="No speakers yet. Add Wi-Fi/Bluetooth speakers or a Snapcast server from the hub." />}
        {rooms.map((r) => (
          <View key={r.id} style={styles.room}>
            <View style={{ flex: 1 }}>
              <Text style={styles.roomName}>{r.name}</Text>
              <Text style={styles.roomMeta} numberOfLines={1}>
                {r.speakers.join(", ")}
                {r.online ? "" : " · offline"}
              </Text>
            </View>
            <Pressable onPress={() => playRoom(r.name)} style={styles.playBtn} disabled={!r.online}>
              <Text style={[styles.playText, !r.online && { color: colors.muted }]}>Play</Text>
            </Pressable>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 20, paddingBottom: 40 },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700" },
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: 2, marginBottom: 14 },
  np: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 20,
    marginBottom: 20,
  },
  npTitle: { color: colors.text, fontSize: font.h2, fontWeight: "700" },
  npArtist: { color: colors.muted, fontSize: font.small, marginTop: 2 },
  bar: { height: 4, borderRadius: 2, backgroundColor: colors.line, marginTop: 16, overflow: "hidden" },
  barFill: { height: 4, borderRadius: 2, backgroundColor: colors.accent },
  times: { flexDirection: "row", justifyContent: "space-between", marginTop: 6 },
  time: { color: colors.muted, fontSize: font.tiny, fontVariant: ["tabular-nums"] },
  transport: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 24, marginTop: 14 },
  tbtn: { width: 54, height: 54, alignItems: "center", justifyContent: "center" },
  tmain: {
    backgroundColor: colors.accent,
    borderRadius: 27,
  },
  tico: { color: colors.text, fontSize: 24 },
  ticoMain: { color: "#05251a", fontSize: 22 },
  room: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 14,
    marginBottom: 8,
  },
  roomName: { color: colors.text, fontSize: font.body, fontWeight: "600" },
  roomMeta: { color: colors.muted, fontSize: font.tiny, marginTop: 2 },
  playBtn: {
    paddingVertical: 8,
    paddingHorizontal: 18,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.accentDim,
    backgroundColor: colors.accentWash,
  },
  playText: { color: colors.accent, fontWeight: "700", fontSize: font.small },
});
