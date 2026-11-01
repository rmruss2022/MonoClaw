import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { SectionTitle, Loading, Empty } from "@/components/ui";
import { colors, radius, font } from "@/theme";

interface LightView {
  id: string; name: string; room: string; on: boolean; brightness: number;
  real: boolean; dimmable: boolean; online: boolean;
}
interface RoomGroup { room: string; lights: LightView[] }
interface State { lights: LightView[]; rooms: RoomGroup[]; counts: { total: number; on: number; real: number } }

const LEVELS = [25, 50, 75, 100];

export default function LightsScreen() {
  const { data, loading, refresh } = usePoll<State>("/lights/state", 5000);
  const run = useCommand();

  const toggle = async (l: LightView) => {
    await run("/lights/command", { cmd: "toggle", id: l.id, on: !l.on });
    refresh();
  };
  const setBrightness = async (l: LightView, brightness: number) => {
    await run("/lights/command", { cmd: "brightness", id: l.id, brightness });
    refresh();
  };
  const roomPower = async (room: string, on: boolean) => {
    await run("/lights/command", { cmd: "room-power", room, on });
    refresh();
  };

  if (loading && !data) return <Loading />;

  const rooms = data?.rooms ?? [];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Lights</Text>
        {data && (
          <Text style={styles.subtitle}>
            {data.counts.on} on · {data.counts.total} total
            {data.counts.real === 0 ? " · none paired yet" : ` · ${data.counts.real} real`}
          </Text>
        )}

        {rooms.length === 0 && (
          <Empty text="No lights yet. Pair ESPHome or Matter bulbs from the hub on your LAN to see them here." />
        )}

        {rooms.map((group) => {
          const anyOn = group.lights.some((l) => l.on);
          return (
            <View key={group.room} style={{ marginTop: 18 }}>
              <View style={styles.roomHead}>
                <SectionTitle>{group.room}</SectionTitle>
                <Pressable onPress={() => roomPower(group.room, !anyOn)} style={styles.roomBtn}>
                  <Text style={styles.roomBtnText}>{anyOn ? "All off" : "All on"}</Text>
                </Pressable>
              </View>
              {group.lights.map((l) => (
                <View key={l.id} style={styles.lightCard}>
                  <Pressable onPress={() => toggle(l)} style={styles.lightHead}>
                    <View style={[styles.bulb, l.on && styles.bulbOn]} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.lightName}>{l.name}</Text>
                      <Text style={styles.lightMeta}>
                        {l.on ? `On · ${l.brightness}%` : "Off"}
                        {!l.online ? " · offline" : ""}
                        {!l.real ? " · demo" : ""}
                      </Text>
                    </View>
                    <View style={[styles.toggle, l.on && styles.toggleOn]}>
                      <View style={[styles.knob, l.on && styles.knobOn]} />
                    </View>
                  </Pressable>
                  {l.on && l.dimmable && (
                    <View style={styles.levels}>
                      {LEVELS.map((lv) => (
                        <Pressable
                          key={lv}
                          onPress={() => setBrightness(l, lv)}
                          style={[styles.level, Math.round(l.brightness / 25) * 25 === lv && styles.levelOn]}
                        >
                          <Text
                            style={[
                              styles.levelText,
                              Math.round(l.brightness / 25) * 25 === lv && { color: colors.accent },
                            ]}
                          >
                            {lv}%
                          </Text>
                        </Pressable>
                      ))}
                    </View>
                  )}
                </View>
              ))}
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 20, paddingBottom: 40 },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700" },
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: 2 },
  roomHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  roomBtn: {
    paddingVertical: 5,
    paddingHorizontal: 12,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
  },
  roomBtnText: { color: colors.muted, fontSize: font.tiny, fontWeight: "700" },
  lightCard: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: 14,
    marginTop: 8,
  },
  lightHead: { flexDirection: "row", alignItems: "center", gap: 12 },
  bulb: { width: 14, height: 14, borderRadius: 7, backgroundColor: colors.line },
  bulbOn: {
    backgroundColor: colors.accent,
    shadowColor: colors.accent,
    shadowOpacity: 0.8,
    shadowRadius: 6,
  },
  lightName: { color: colors.text, fontSize: font.body, fontWeight: "600" },
  lightMeta: { color: colors.muted, fontSize: font.tiny, marginTop: 2 },
  toggle: {
    width: 46,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 3,
    justifyContent: "center",
  },
  toggleOn: { backgroundColor: colors.accentWash, borderColor: colors.accentDim },
  knob: { width: 20, height: 20, borderRadius: 10, backgroundColor: colors.muted },
  knobOn: { backgroundColor: colors.accent, alignSelf: "flex-end" },
  levels: { flexDirection: "row", gap: 8, marginTop: 12 },
  level: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
  },
  levelOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  levelText: { color: colors.muted, fontSize: font.tiny, fontWeight: "700" },
});
