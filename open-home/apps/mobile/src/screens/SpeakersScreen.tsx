import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { Card, SectionTitle, StatusDot, Loading, Empty } from "@/components/ui";
import { colors, radius, font, space } from "@/theme";

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
  const playing = !!np?.playing;
  const hasTrack = !!np?.title;
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

        {/* Now playing */}
        <Card active={playing} style={styles.np}>
          <View style={styles.npTop}>
            <View style={[styles.art, playing && styles.artOn]}>
              <Text style={[styles.artGlyph, playing && { color: colors.accent }]}>♪</Text>
            </View>
            <View style={{ flex: 1 }}>
              <View style={styles.statusRow}>
                <StatusDot color={playing ? colors.success : colors.muted} glow={playing} />
                <Text style={styles.statusText}>{playing ? "Playing" : hasTrack ? "Paused" : "Idle"}</Text>
              </View>
              <Text style={styles.npTitle} numberOfLines={1}>{np?.title || "Nothing playing"}</Text>
              <Text style={styles.npArtist} numberOfLines={1}>
                {np?.artist || "Pick a room and hit play"}
                {np?.device ? ` · ${np.device}` : ""}
              </Text>
            </View>
          </View>

          <View style={styles.bar}>
            <View style={[styles.barFill, { width: `${pct}%` }]} />
          </View>
          <View style={styles.times}>
            <Text style={styles.time}>{fmt(np?.positionMs)}</Text>
            <Text style={styles.time}>{fmt(np?.durationMs)}</Text>
          </View>

          <View style={styles.transport}>
            <Pressable
              onPress={() => transport("prev")}
              accessibilityRole="button"
              accessibilityLabel="Previous track"
              style={({ pressed }) => [styles.tbtn, pressed && styles.tbtnPressed]}
            >
              <Text style={styles.tico}>⏮</Text>
            </Pressable>
            <Pressable
              onPress={() => transport(playing ? "pause" : "play")}
              accessibilityRole="button"
              accessibilityLabel={playing ? "Pause" : "Play"}
              style={({ pressed }) => [styles.tbtn, styles.tmain, pressed && { opacity: 0.85 }]}
            >
              <Text style={styles.ticoMain}>{playing ? "⏸" : "▶"}</Text>
            </Pressable>
            <Pressable
              onPress={() => transport("next")}
              accessibilityRole="button"
              accessibilityLabel="Next track"
              style={({ pressed }) => [styles.tbtn, pressed && styles.tbtnPressed]}
            >
              <Text style={styles.tico}>⏭</Text>
            </Pressable>
          </View>
        </Card>

        <View style={styles.sectionHead}>
          <SectionTitle>Rooms</SectionTitle>
        </View>
        {rooms.length === 0 && <Empty text="No speakers yet. Add Wi-Fi/Bluetooth speakers or a Snapcast server from the hub." />}
        {rooms.map((r) => (
          <Card key={r.id} style={styles.room}>
            <StatusDot color={r.online ? colors.success : colors.muted} glow={r.online} />
            <View style={{ flex: 1 }}>
              <Text style={styles.roomName}>{r.name}</Text>
              <Text style={styles.roomMeta} numberOfLines={1}>
                {r.speakers.join(", ")}
                {r.online ? "" : " · offline"}
              </Text>
            </View>
            <Pressable
              onPress={() => playRoom(r.name)}
              disabled={!r.online}
              accessibilityRole="button"
              accessibilityLabel={`Play in ${r.name}`}
              accessibilityState={{ disabled: !r.online }}
              style={({ pressed }) => [
                styles.playBtn,
                !r.online && styles.playBtnOff,
                pressed && r.online && { opacity: 0.75 },
              ]}
            >
              <Text style={[styles.playText, !r.online && { color: colors.muted }]}>Play</Text>
            </Pressable>
          </Card>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), paddingBottom: space(10) },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700" },
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: space(1), marginBottom: space(4) },

  np: { padding: space(5), marginBottom: space(5) },
  npTop: { flexDirection: "row", gap: space(4), alignItems: "center" },
  art: {
    width: 64,
    height: 64,
    borderRadius: radius.md,
    backgroundColor: colors.panelAlt,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  artOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  artGlyph: { color: colors.muted, fontSize: 28 },
  statusRow: { flexDirection: "row", alignItems: "center", gap: space(2) },
  statusText: {
    color: colors.muted,
    fontSize: font.tiny,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  npTitle: { color: colors.text, fontSize: font.h2, fontWeight: "700", marginTop: space(1) },
  npArtist: { color: colors.muted, fontSize: font.small, marginTop: space(1) },

  bar: { height: 5, borderRadius: 3, backgroundColor: colors.line, marginTop: space(4), overflow: "hidden" },
  barFill: { height: 5, borderRadius: 3, backgroundColor: colors.accent },
  times: { flexDirection: "row", justifyContent: "space-between", marginTop: space(2) },
  time: { color: colors.muted, fontSize: font.tiny, fontVariant: ["tabular-nums"] },

  transport: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space(6), marginTop: space(4) },
  tbtn: { width: 56, height: 56, borderRadius: 28, alignItems: "center", justifyContent: "center" },
  tbtnPressed: { backgroundColor: colors.press },
  tmain: { backgroundColor: colors.accent },
  tico: { color: colors.text, fontSize: 24 },
  ticoMain: { color: colors.onAccent, fontSize: 22 },

  sectionHead: { marginBottom: space(3) },
  room: {
    flexDirection: "row",
    alignItems: "center",
    gap: space(3),
    padding: space(4),
    borderRadius: radius.md,
    marginBottom: space(2),
  },
  roomName: { color: colors.text, fontSize: font.body, fontWeight: "600" },
  roomMeta: { color: colors.muted, fontSize: font.tiny, marginTop: space(1) },
  playBtn: {
    minHeight: 44,
    paddingHorizontal: space(5),
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.accentDim,
    backgroundColor: colors.accentWash,
    alignItems: "center",
    justifyContent: "center",
  },
  playBtnOff: { borderColor: colors.line, backgroundColor: "transparent" },
  playText: { color: colors.accent, fontWeight: "700", fontSize: font.small },
});
