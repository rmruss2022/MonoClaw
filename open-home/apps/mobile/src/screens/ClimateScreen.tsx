import React from "react";
import { View, Text, ScrollView, StyleSheet, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll, useCommand } from "@/api/hooks";
import { SectionTitle, Loading, Empty } from "@/components/ui";
import { colors, radius, font } from "@/theme";

interface ThermostatView {
  id: string; name: string; room: string;
  mode: string; action: string;
  currentF: number; targetF: number; humidity?: number; minF: number; maxF: number;
  real: boolean; online: boolean;
}
interface State {
  thermostats: ThermostatView[];
  rooms: { room: string; thermostats: ThermostatView[] }[];
  counts: { total: number; real: number; active: number };
}

const MODES = ["off", "heat", "cool", "auto"];
const actionColor: Record<string, string> = { heating: "#f5894f", cooling: "#4fa8f5", idle: colors.muted };

export default function ClimateScreen() {
  const { data, loading, refresh } = usePoll<State>("/climate/state", 5000);
  const run = useCommand();

  const setTemp = async (t: ThermostatView, targetF: number) => {
    const clamped = Math.max(t.minF, Math.min(t.maxF, targetF));
    await run("/climate/command", { cmd: "set-temp", id: t.id, targetF: clamped });
    refresh();
  };
  const setMode = async (t: ThermostatView, mode: string) => {
    await run("/climate/command", { cmd: "set-mode", id: t.id, mode });
    refresh();
  };

  if (loading && !data) return <Loading />;
  const list = data?.thermostats ?? [];

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Climate</Text>
        {data && (
          <Text style={styles.subtitle}>
            {data.counts.active} active · {data.counts.total} total
            {data.counts.real === 0 ? " · none paired yet" : ""}
          </Text>
        )}

        {list.length === 0 && (
          <Empty text="No thermostats yet. Pair an ESPHome or Matter thermostat from the hub on your LAN." />
        )}

        {list.map((t) => (
          <View key={t.id} style={styles.card}>
            <View style={styles.head}>
              <View>
                <Text style={styles.name}>{t.name}</Text>
                <Text style={styles.room}>
                  {t.room}
                  {!t.online ? " · offline" : ""}
                  {!t.real ? " · demo" : ""}
                </Text>
              </View>
              <Text style={[styles.action, { color: actionColor[t.action] ?? colors.muted }]}>
                {t.action === "idle" ? "Idle" : t.action}
              </Text>
            </View>

            <View style={styles.dial}>
              <Pressable onPress={() => setTemp(t, t.targetF - 1)} style={styles.step}>
                <Text style={styles.stepText}>−</Text>
              </Pressable>
              <View style={styles.readout}>
                <Text style={styles.target}>{Math.round(t.targetF)}°</Text>
                <Text style={styles.current}>now {Math.round(t.currentF)}°{t.humidity ? ` · ${t.humidity}%` : ""}</Text>
              </View>
              <Pressable onPress={() => setTemp(t, t.targetF + 1)} style={styles.step}>
                <Text style={styles.stepText}>+</Text>
              </Pressable>
            </View>

            <View style={styles.modes}>
              {MODES.map((m) => (
                <Pressable
                  key={m}
                  onPress={() => setMode(t, m)}
                  style={[styles.mode, t.mode === m && styles.modeOn]}
                >
                  <Text style={[styles.modeText, t.mode === m && { color: colors.accent }]}>
                    {m[0].toUpperCase() + m.slice(1)}
                  </Text>
                </Pressable>
              ))}
            </View>
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
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: 2, marginBottom: 6 },
  card: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 18,
    marginTop: 12,
  },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  name: { color: colors.text, fontSize: font.h2, fontWeight: "700" },
  room: { color: colors.muted, fontSize: font.tiny, marginTop: 2 },
  action: { fontSize: font.small, fontWeight: "700", textTransform: "capitalize" },
  dial: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginVertical: 18 },
  step: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { color: colors.accent, fontSize: 28, fontWeight: "700", lineHeight: 30 },
  readout: { alignItems: "center" },
  target: { color: colors.text, fontSize: 52, fontWeight: "800", letterSpacing: -2 },
  current: { color: colors.muted, fontSize: font.small, marginTop: -4 },
  modes: { flexDirection: "row", gap: 8 },
  mode: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
  },
  modeOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  modeText: { color: colors.muted, fontSize: font.small, fontWeight: "700" },
});
