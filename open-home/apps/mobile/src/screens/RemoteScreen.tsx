/**
 * Remote — talk to the house, and the quick controls that used to live on the
 * web control surface (apps/app/control.html): voice capture, scenes, and the
 * at-a-glance house state.
 *
 * Voice path: record on the phone -> POST base64 to the hub's /agent/audio ->
 * the hub transcribes (ElevenLabs Scribe) and Claude decides what to do -> we
 * show the transcript, the reply, and what actually changed.
 *
 * The transcript matters as much as the reply. When a voice command does the
 * wrong thing it is nearly always a misheard word, and without showing what
 * the hub heard the user is left guessing whether the mic or the brain failed.
 */
import React, { useCallback, useRef, useState } from "react";
import { View, Text, ScrollView, StyleSheet, Pressable, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Ionicons from "@expo/vector-icons/Ionicons";
import {
  useAudioRecorder, RecordingPresets,
  requestRecordingPermissionsAsync, setAudioModeAsync,
} from "expo-audio";
import { api } from "@/api/client";
import { usePoll, useCommand } from "@/api/hooks";
import { Card, SectionTitle, Empty, StatusDot } from "@/components/ui";
import { colors, radius, font, space } from "@/theme";

interface Scene { id: string; name: string; icon?: string }
interface Summary {
  lightsOn: number; lightsTotal: number; allLocked: boolean;
  anyPlaying: boolean; temp: number | null; target: number | null; scene?: string;
}
interface Turn { id: number; heard: string; reply: string; actions: string[]; error?: boolean }

type Phase = "idle" | "recording" | "thinking";

export default function RemoteScreen() {
  const { data: scenes } = usePoll<{ scenes: Scene[] }>("/scenes", 0);
  const { data: state, refresh: refreshState } = usePoll<{ summary?: Summary }>("/devices", 6000);
  const run = useCommand();

  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [phase, setPhase] = useState<Phase>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const nextId = useRef(1);

  const say = (t: Omit<Turn, "id">) => setTurns((prev) => [{ ...t, id: nextId.current++ }, ...prev].slice(0, 8));

  const start = useCallback(async () => {
    setProblem(null);
    try {
      const perm = await requestRecordingPermissionsAsync();
      if (!perm.granted) { setProblem("Microphone access is off. Enable it for openhome in iOS Settings."); return; }
      // Without this the recording is silent on iOS when the ringer switch is
      // on silent — a failure that looks exactly like "the hub didn't hear me".
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setPhase("recording");
    } catch (e) {
      setProblem((e as Error).message || "Couldn't start recording");
      setPhase("idle");
    }
  }, [recorder]);

  const stopAndSend = useCallback(async () => {
    if (phase !== "recording") return;
    setPhase("thinking");
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error("no recording produced");

      // RN can fetch a file:// URI, and its Blob supports readAsDataURL — so
      // base64 needs no extra native module.
      const blob = await (await fetch(uri)).blob();
      const b64 = await new Promise<string>((resolve, reject) => {
        const r = new FileReader();
        r.onerror = () => reject(new Error("couldn't read the recording"));
        r.onload = () => resolve(String(r.result).split(",")[1] ?? "");
        r.readAsDataURL(blob);
      });
      if (!b64) throw new Error("the recording was empty");

      const r: any = await api("/agent/audio", {
        method: "POST",
        body: { audio: b64, mime: "audio/m4a" },
      });

      if (r?.ok === false) {
        say({
          heard: r.transcript ?? "",
          reply: r.reply ?? (r.error === "no_speech_to_text"
            ? "This hub has no speech-to-text provider configured."
            : "The hub couldn't process that."),
          actions: [],
          error: true,
        });
      } else {
        say({
          heard: r?.transcript ?? "",
          reply: r?.reply ?? "",
          actions: (r?.actions ?? []).map((a: any) => a?.label).filter(Boolean),
        });
        refreshState();
      }
    } catch (e) {
      setProblem((e as Error).message || "Voice request failed");
    } finally {
      setPhase("idle");
    }
  }, [phase, recorder, refreshState]);

  const scene = useCallback(async (s: Scene) => {
    // Scenes have their own endpoint; POST /scenes {id} returns the new summary.
    const r: any = await run("/scenes", { id: s.id });
    if (!r) { setProblem("Couldn't activate that scene"); return; }
    say({ heard: "", reply: `${s.name} scene`, actions: [s.name] });
    refreshState();
  }, [run, refreshState]);

  const sum = state?.summary;
  const recording = phase === "recording";
  const thinking = phase === "thinking";

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Remote</Text>
        <Text style={styles.subtitle}>Hold the button and tell the house what to do</Text>

        {/* Talk */}
        <View style={styles.micWrap}>
          <Pressable
            onPressIn={start}
            onPressOut={stopAndSend}
            disabled={thinking}
            accessibilityRole="button"
            accessibilityLabel="Hold to speak"
            style={({ pressed }) => [
              styles.mic,
              recording && styles.micLive,
              thinking && styles.micBusy,
              pressed && !recording && { opacity: 0.85 },
            ]}
          >
            {thinking
              ? <ActivityIndicator color={colors.accent} size="large" />
              : <Ionicons name={recording ? "radio-button-on" : "mic"} size={44} color={recording ? colors.onAccent : colors.accent} />}
          </Pressable>
          <Text style={styles.micHint}>
            {recording ? "Listening — release to send" : thinking ? "Thinking…" : "Hold to talk"}
          </Text>
        </View>

        {problem && (
          <Card style={styles.problem}>
            <Text style={styles.problemText}>{problem}</Text>
          </Card>
        )}

        {/* Conversation */}
        {turns.length > 0 && (
          <>
            <SectionTitle>Conversation</SectionTitle>
            {turns.map((t) => (
              <Card key={t.id} style={styles.turn}>
                {!!t.heard && <Text style={styles.heard}>“{t.heard}”</Text>}
                <Text style={[styles.reply, t.error && { color: colors.danger }]}>{t.reply}</Text>
                {t.actions.length > 0 && (
                  <View style={styles.actionRow}>
                    {t.actions.map((a, i) => (
                      <View key={a + i} style={styles.actionTag}>
                        <Ionicons name="checkmark" size={11} color={colors.success} />
                        <Text style={styles.actionText}>{a}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </Card>
            ))}
          </>
        )}

        {/* Scenes */}
        <SectionTitle>Scenes</SectionTitle>
        {!scenes?.scenes?.length && <Empty text="No scenes defined on this hub yet." />}
        <View style={styles.sceneGrid}>
          {(scenes?.scenes ?? []).map((s) => (
            <Pressable
              key={s.id}
              onPress={() => scene(s)}
              accessibilityRole="button"
              accessibilityLabel={`Activate ${s.name}`}
              style={({ pressed }) => [
                styles.scene,
                sum?.scene === s.id && styles.sceneOn,
                pressed && { opacity: 0.75 },
              ]}
            >
              <Text style={[styles.sceneText, sum?.scene === s.id && { color: colors.accent }]}>{s.name}</Text>
            </Pressable>
          ))}
        </View>

        {/* House at a glance */}
        {sum && (
          <>
            <SectionTitle>House</SectionTitle>
            <Card style={styles.glance}>
              <Glance icon="bulb" label="Lights" value={`${sum.lightsOn} of ${sum.lightsTotal} on`} on={sum.lightsOn > 0} />
              <Glance icon="lock-closed" label="Locks" value={sum.allLocked ? "All locked" : "Something open"} on={sum.allLocked} />
              <Glance icon="musical-notes" label="Music" value={sum.anyPlaying ? "Playing" : "Quiet"} on={sum.anyPlaying} />
              {sum.temp != null && (
                <Glance icon="thermometer" label="Climate" value={`${Math.round(sum.temp)}° → ${Math.round(sum.target ?? sum.temp)}°`} on />
              )}
            </Card>
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Glance({ icon, label, value, on }: { icon: any; label: string; value: string; on: boolean }) {
  return (
    <View style={styles.glanceRow}>
      <Ionicons name={icon} size={18} color={on ? colors.accent : colors.muted} />
      <Text style={styles.glanceLabel}>{label}</Text>
      <StatusDot color={on ? colors.success : colors.muted} glow={on} />
      <Text style={styles.glanceValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), paddingBottom: space(10) },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700" },
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: space(1), marginBottom: space(6) },

  micWrap: { alignItems: "center", marginBottom: space(6) },
  mic: {
    width: 128, height: 128, borderRadius: 64,
    alignItems: "center", justifyContent: "center",
    backgroundColor: colors.accentWash,
    borderWidth: 2, borderColor: colors.accentDim,
  },
  micLive: { backgroundColor: colors.accent, borderColor: colors.accent },
  micBusy: { opacity: 0.8 },
  micHint: { color: colors.muted, fontSize: font.small, marginTop: space(3), fontWeight: "600" },

  problem: { padding: space(4), marginBottom: space(4) },
  problemText: { color: colors.danger, fontSize: font.small },

  turn: { padding: space(4), marginBottom: space(2) },
  heard: { color: colors.muted, fontSize: font.small, fontStyle: "italic", marginBottom: space(2) },
  reply: { color: colors.text, fontSize: font.body, lineHeight: 21 },
  actionRow: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginTop: space(3) },
  actionTag: {
    flexDirection: "row", alignItems: "center", gap: space(1),
    paddingHorizontal: space(2), paddingVertical: space(1),
    borderRadius: radius.pill, backgroundColor: colors.panelAlt,
    borderWidth: 1, borderColor: colors.line,
  },
  actionText: { color: colors.muted, fontSize: font.tiny, fontWeight: "700" },

  sceneGrid: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginBottom: space(5) },
  scene: {
    minHeight: 44, paddingHorizontal: space(5), justifyContent: "center",
    borderRadius: radius.pill, borderWidth: 1, borderColor: colors.line,
  },
  sceneOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  sceneText: { color: colors.text, fontSize: font.small, fontWeight: "700" },

  glance: { padding: space(4), gap: space(3) },
  glanceRow: { flexDirection: "row", alignItems: "center", gap: space(3) },
  glanceLabel: { color: colors.text, fontSize: font.small, fontWeight: "600", width: 68 },
  glanceValue: { color: colors.muted, fontSize: font.small, flex: 1, textAlign: "right" },
});
