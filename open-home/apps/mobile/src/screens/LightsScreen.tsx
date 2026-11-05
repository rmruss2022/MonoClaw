import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { Card, SectionTitle, StatusDot, Toggle, Loading, Empty } from "@/components/ui";
import { colors, radius, font, space } from "@/theme";

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
          const onCount = group.lights.filter((l) => l.on).length;
          return (
            <View key={group.room} style={styles.group}>
              <View style={styles.roomHead}>
                <View>
                  <SectionTitle>{group.room}</SectionTitle>
                  <Text style={styles.roomCount}>{onCount}/{group.lights.length} on</Text>
                </View>
                <Pressable
                  onPress={() => roomPower(group.room, !anyOn)}
                  accessibilityRole="button"
                  accessibilityLabel={anyOn ? `Turn all ${group.room} lights off` : `Turn all ${group.room} lights on`}
                  style={({ pressed }) => [styles.roomBtn, anyOn && styles.roomBtnOn, pressed && { opacity: 0.7 }]}
                >
                  <Text style={[styles.roomBtnText, anyOn && { color: colors.accent }]}>
                    {anyOn ? "All off" : "All on"}
                  </Text>
                </Pressable>
              </View>

              {group.lights.map((l) => {
                const activeLevel = Math.round(l.brightness / 25) * 25;
                return (
                  <Card key={l.id} active={l.on} style={styles.lightCard}>
                    <Pressable
                      onPress={() => toggle(l)}
                      accessibilityRole="switch"
                      accessibilityLabel={l.name}
                      accessibilityState={{ checked: l.on, disabled: !l.online }}
                      style={({ pressed }) => [styles.lightHead, pressed && { opacity: 0.8 }]}
                    >
                      <StatusDot color={l.on ? colors.accent : colors.muted} glow={l.on} />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.lightName}>{l.name}</Text>
                        <Text style={styles.lightMeta}>
                          {l.on ? `On · ${l.brightness}%` : "Off"}
                          {!l.online ? " · offline" : ""}
                          {!l.real ? " · demo" : ""}
                        </Text>
                      </View>
                      <Toggle on={l.on} />
                    </Pressable>

                    {l.on && l.dimmable && (
                      <View style={styles.levels}>
                        {LEVELS.map((lv) => {
                          const sel = activeLevel === lv;
                          return (
                            <Pressable
                              key={lv}
                              onPress={() => setBrightness(l, lv)}
                              accessibilityRole="button"
                              accessibilityLabel={`Set ${l.name} to ${lv} percent`}
                              accessibilityState={{ selected: sel }}
                              style={({ pressed }) => [styles.level, sel && styles.levelOn, pressed && { opacity: 0.7 }]}
                            >
                              <Text style={[styles.levelText, sel && { color: colors.accent }]}>{lv}%</Text>
                            </Pressable>
                          );
                        })}
                      </View>
                    )}
                  </Card>
                );
              })}
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), paddingBottom: space(10) },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700" },
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: space(1) },

  group: { marginTop: space(5) },
  roomHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: space(3),
  },
  roomCount: { color: colors.muted, fontSize: font.tiny, marginTop: space(1) },
  roomBtn: {
    minHeight: 44,
    paddingHorizontal: space(4),
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  roomBtnOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  roomBtnText: { color: colors.muted, fontSize: font.small, fontWeight: "700" },

  lightCard: { padding: space(4), borderRadius: radius.md, marginTop: space(2) },
  lightHead: { flexDirection: "row", alignItems: "center", gap: space(3), minHeight: 44 },
  lightName: { color: colors.text, fontSize: font.body, fontWeight: "600" },
  lightMeta: { color: colors.muted, fontSize: font.tiny, marginTop: space(1) },

  levels: { flexDirection: "row", gap: space(2), marginTop: space(3) },
  level: {
    flex: 1,
    minHeight: 44,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center",
  },
  levelOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  levelText: { color: colors.muted, fontSize: font.small, fontWeight: "700" },
});
