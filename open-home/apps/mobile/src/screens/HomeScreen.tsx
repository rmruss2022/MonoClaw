import React, { useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { Card, SectionTitle, Loading } from "@/components/ui";
import { colors, radius, font } from "@/theme";

interface Scene { id: string; name: string; icon: string; description: string }
interface Summary {
  devices: number; rooms: number; lightsOn: number; lightsTotal: number;
  allLocked: boolean; anyPlaying: boolean; temp: number; target: number; scene: string | null;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Still up?";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 22) return "Good evening";
  return "Good night";
}

export default function HomeScreen() {
  const status = usePoll<{ homeName?: string; hubName?: string }>("/hub/status", 15000);
  const dev = usePoll<{ summary: Summary }>("/devices", 6000);
  const scenes = usePoll<{ scenes: Scene[] }>("/scenes", 0);
  const run = useCommand();
  const [activating, setActivating] = useState<string | null>(null);

  const summary = dev.data?.summary;
  const homeName = status.data?.homeName || "Home";

  const activate = async (id: string) => {
    setActivating(id);
    await run("/scenes", { id });
    setActivating(null);
    dev.refresh();
  };

  if (dev.loading && !summary) return <Loading />;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.greeting}>{greeting()}</Text>
        <Text style={styles.home}>{homeName}</Text>

        {summary && (
          <View style={styles.chips}>
            <Chip on={summary.lightsOn > 0} label={`${summary.lightsOn}/${summary.lightsTotal} lights`} />
            <Chip on label={`${Math.round(summary.temp)}°→${Math.round(summary.target)}°`} />
            <Chip on={summary.allLocked} label={summary.allLocked ? "Locked" : "Unlocked"} />
            {summary.anyPlaying && <Chip on label="Playing" />}
          </View>
        )}

        <SectionTitle>Scenes</SectionTitle>
        <View style={styles.sceneGrid}>
          {(scenes.data?.scenes ?? []).map((s) => {
            const active = summary?.scene === s.id;
            return (
              <Pressable
                key={s.id}
                onPress={() => activate(s.id)}
                style={[styles.scene, active && styles.sceneOn, activating === s.id && { opacity: 0.6 }]}
              >
                <Text style={styles.sceneIcon}>{s.icon}</Text>
                <Text style={[styles.sceneName, active && { color: colors.accent }]}>{s.name}</Text>
              </Pressable>
            );
          })}
        </View>

        <SectionTitle>Overview</SectionTitle>
        <Card>
          <Row label="Devices" value={String(summary?.devices ?? "—")} />
          <Row label="Rooms" value={String(summary?.rooms ?? "—")} />
          <Row label="Active scene" value={summary?.scene ? titleCase(summary.scene) : "None"} last />
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

function Chip({ label, on }: { label: string; on?: boolean }) {
  return (
    <View style={[styles.chip, on && styles.chipOn]}>
      <Text style={[styles.chipText, on && { color: colors.accent }]}>{label}</Text>
    </View>
  );
}

function Row({ label, value, last }: { label: string; value: string; last?: boolean }) {
  return (
    <View style={[styles.row, !last && styles.rowBorder]}>
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={styles.rowValue}>{value}</Text>
    </View>
  );
}

const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 20, paddingBottom: 40 },
  greeting: { color: colors.text, fontSize: font.h1, fontWeight: "700", letterSpacing: -0.5 },
  home: { color: colors.muted, fontSize: font.body, marginTop: 2, marginBottom: 16 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
  },
  chipOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  chipText: { color: colors.muted, fontWeight: "700", fontSize: font.small },
  sceneGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  scene: {
    width: "31%",
    aspectRatio: 1,
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  sceneOn: { borderColor: colors.accent, backgroundColor: colors.accentWash },
  sceneIcon: { fontSize: 28 },
  sceneName: { color: colors.muted, fontSize: font.tiny, fontWeight: "700", textAlign: "center" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 12 },
  rowBorder: { borderBottomWidth: 1, borderBottomColor: colors.line },
  rowLabel: { color: colors.muted, fontSize: font.body },
  rowValue: { color: colors.text, fontSize: font.body, fontWeight: "600" },
});
