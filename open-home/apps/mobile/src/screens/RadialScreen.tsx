/**
 * The radial remote — a native port of the web control surface
 * (apps/app/control.html), which is the interaction this product is actually
 * built around.
 *
 * Press anywhere on the dial to arm it, drag toward a wedge, release to fire.
 * Drag through two directions in sequence and it becomes a *chord*: a gesture
 * shortcut straight to a scene without ever lifting a finger. Double-tap the
 * centre to talk to the house.
 *
 * The eight wedges, the five chords and their direction indices are copied
 * from control.html deliberately — muscle memory built on the web surface has
 * to keep working here, so the angles and the sequences must match exactly.
 */
import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  View, Text, StyleSheet, PanResponder, Vibration, Dimensions, Pressable, ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Path, Polyline, Circle } from "react-native-svg";
import { LinearGradient } from "expo-linear-gradient";
import Ionicons from "@expo/vector-icons/Ionicons";
import {
  useAudioRecorder, RecordingPresets,
  requestRecordingPermissionsAsync, setAudioModeAsync,
} from "expo-audio";
import { api } from "@/api/client";
import { usePoll } from "@/api/hooks";
import { colors, radius, font, space } from "@/theme";

type Icon = keyof typeof Ionicons.glyphMap;

/** Direction index 0 = right, then clockwise every 45°, matching control.html. */
const ACTIONS: { key: string; label: string; icon: Icon }[] = [
  { key: "cameras", label: "Cameras", icon: "videocam" },
  { key: "doorbell", label: "Doorbell", icon: "notifications" },
  { key: "lock", label: "Lock", icon: "lock-closed" },
  { key: "away", label: "Away", icon: "exit" },
  { key: "music", label: "Music", icon: "musical-notes" },
  { key: "goodnight", label: "Goodnight", icon: "moon" },
  { key: "lights", label: "Lights", icon: "bulb" },
  { key: "movie", label: "Movie", icon: "film" },
];

/** Two-direction gesture shortcuts. Sequences copied from control.html. */
const CHORDS: { seq: number[]; key: string; label: string; icon: Icon }[] = [
  { seq: [6, 7], key: "nighttime", label: "Nighttime", icon: "moon" },
  { seq: [6, 2], key: "morning", label: "Good morning", icon: "sunny" },
  { seq: [2, 6], key: "matthews_room", label: "Matthew's Room", icon: "bed" },
  { seq: [7, 1], key: "party", label: "Party", icon: "sparkles" },
  { seq: [4, 0], key: "reading", label: "Reading", icon: "book" },
];

const SCENE_SUB: Record<string, string> = {
  nighttime: "Lights off · doors locked · quiet",
  goodnight: "Lights off · doors locked · quiet",
  morning: "Lights up · jazz on · report read",
  movie: "Dimmed · TV on · shades down",
  away: "Locked up · lights off · cameras on",
  party: "Every light up · music on",
  reading: "Soft light · everything else calm",
  matthews_room: "Bedroom light · music · shades",
};

const ARROW = ["→", "↘", "↓", "↙", "←", "↖", "↑", "↗"];

const N = ACTIONS.length;
const STEP = 360 / N;
const DEAD = 50;           // centre dead zone, px — below this no wedge is hot
const VIEW = 400;
const CX = 200, CY = 200, R = 190, INNER = 64;
const MID = (R + INNER) / 2 + 18;

const polar = (cx: number, cy: number, r: number, deg: number) => {
  const a = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)] as const;
};

function wedgePath(i: number): string {
  const s = i * STEP - STEP / 2, e = i * STEP + STEP / 2;
  const [x1, y1] = polar(CX, CY, R, s);
  const [x2, y2] = polar(CX, CY, R, e);
  const [ix1, iy1] = polar(CX, CY, INNER, s);
  const [ix2, iy2] = polar(CX, CY, INNER, e);
  return `M ${ix1} ${iy1} L ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2} L ${ix2} ${iy2} A ${INNER} ${INNER} 0 0 0 ${ix1} ${iy1} Z`;
}

const matchChord = (p: number[]) =>
  CHORDS.find((c) => c.seq.length === p.length && c.seq.every((v, k) => v === p[k]));

interface Summary {
  lightsOn: number; lightsTotal: number; allLocked: boolean;
  anyPlaying: boolean; temp: number | null; target: number | null;
}

/**
 * The openhome mark: a house outline around a keyhole — you hold the key to
 * your home and your data. Traced from apps/app/assets/brand/mark.svg so the
 * dial's centre reads the same here as on the web surface.
 */
function Mark({ size }: { size: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64">
      <Path
        d="M32 6 L56.5 25.5 L56.5 55 L7.5 55 L7.5 25.5 Z"
        fill="none" stroke={colors.accent} strokeWidth={5}
        strokeLinejoin="round" strokeLinecap="round"
      />
      <Circle cx={32} cy={33} r={6.2} fill={colors.accent} />
      <Path d="M28.8 37 L26.2 49.5 L37.8 49.5 L35.2 37 Z" fill={colors.accent} />
    </Svg>
  );
}

/** First sentence only — the snackbar is a confirmation, not a transcript. */
function firstSentence(s: string): string {
  const t = s.replace(/\s+/g, " ").trim();
  const m = t.match(/^(.{0,90}?[.!?])(\s|$)/);
  return (m ? m[1] : t.slice(0, 90)).trim();
}

export default function RadialScreen() {
  const { data: state, refresh } = usePoll<{ summary?: Summary }>("/devices", 8000);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  const [armed, setArmed] = useState(false);
  const [hot, setHot] = useState(-1);
  const [path, setPath] = useState<number[]>([]);
  const [burst, setBurst] = useState<{ label: string; sub: string; icon: Icon } | null>(null);
  const [voice, setVoice] = useState<"idle" | "recording" | "thinking">("idle");

  // Refs mirror state for the gesture callbacks: PanResponder closes over the
  // handlers once, so reading React state inside them would see stale values.
  const pathRef = useRef<number[]>([]);
  const hotRef = useRef(-1);
  const centreRef = useRef({ x: 0, y: 0 });
  const dialRef = useRef<React.ComponentRef<typeof View>>(null);
  const lastTap = useRef(0);
  const burstTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const voiceRef = useRef<"idle" | "recording" | "thinking">("idle");

  const size = Math.min(Dimensions.get("window").width - space(10), 360);

  const showBurst = useCallback((label: string, sub: string, icon: Icon) => {
    setBurst({ label, sub, icon });
    if (burstTimer.current) clearTimeout(burstTimer.current);
    burstTimer.current = setTimeout(() => setBurst(null), 4200);
  }, []);

  const fire = useCallback(async (key: string, label: string, icon: Icon) => {
    Vibration.vibrate(18);
    showBurst(label, SCENE_SUB[key] ?? "", icon);
    try {
      const r: any = await api("/control", { method: "POST", body: { action: key }, timeoutMs: 25000 });
      if (r?.label) showBurst(label, String(r.label), icon);
      refresh();
    } catch (e) {
      showBurst(label, (e as Error).message || "Couldn't reach the hub", icon);
    }
  }, [refresh, showBurst]);

  // ---- voice (double-tap the centre) ----
  const startVoice = useCallback(async () => {
    try {
      const perm = await requestRecordingPermissionsAsync();
      if (!perm.granted) { showBurst("Microphone is off", "Enable it for openhome in iOS Settings", "mic-off"); return; }
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      voiceRef.current = "recording";
      setVoice("recording");
      // Starting to listen is a state change worth feeling, unlike sweeping
      // past a wedge you did not choose.
      Vibration.vibrate(12);
    } catch (e) {
      showBurst("Couldn't listen", (e as Error).message || "", "mic-off");
    }
  }, [recorder, showBurst]);

  const stopVoice = useCallback(async () => {
    if (voiceRef.current !== "recording") return;
    voiceRef.current = "thinking";
    setVoice("thinking");
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error("no recording produced");
      const blob = await (await fetch(uri)).blob();
      const b64 = await new Promise<string>((resolve, reject) => {
        const fr = new FileReader();
        fr.onerror = () => reject(new Error("couldn't read the recording"));
        fr.onload = () => resolve(String(fr.result).split(",")[1] ?? "");
        fr.readAsDataURL(blob);
      });
      const r: any = await api("/agent/audio", {
        method: "POST", body: { audio: b64, mime: "audio/m4a" }, timeoutMs: 60000,
      });
      // The house answers out loud. The snackbar only confirms it was heard and
      // what changed — a wall of text to read defeats the point of talking.
      const acts: string[] = (r?.actions ?? []).filter(Boolean);
      const sub = acts.length ? acts.join(" · ")
        : r?.ok === false ? "Couldn't process that"
        : firstSentence(r?.reply ?? "");
      showBurst(r?.transcript ? `“${r.transcript}”` : "Heard you", sub, "mic");
      refresh();
    } catch (e) {
      showBurst("Voice failed", (e as Error).message || "", "alert-circle");
    } finally {
      voiceRef.current = "idle";
      setVoice("idle");
    }
  }, [recorder, refresh]);

  const responder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,

    onPanResponderGrant: () => {
      // A press while recording ends the utterance — same as the web surface,
      // where tapping again is how you stop talking.
      if (voiceRef.current === "recording") { stopVoice(); return; }
      pathRef.current = [];
      hotRef.current = -1;
      setPath([]); setHot(-1); setArmed(true);
      // No haptic here, and none per wedge: buzzing on every direction you
      // sweep past turns a deliberate confirmation into noise. The phone only
      // taps back once something is actually chosen.
    },

    onPanResponderMove: (_e, g) => {
      if (voiceRef.current !== "idle") return;
      const dx = g.moveX - centreRef.current.x;
      const dy = g.moveY - centreRef.current.y;
      const dist = Math.hypot(dx, dy);
      if (dist < DEAD) { if (hotRef.current !== -1) { hotRef.current = -1; setHot(-1); } return; }
      let deg = (Math.atan2(dy, dx) * 180) / Math.PI;
      if (deg < 0) deg += 360;
      const i = Math.round(deg / STEP) % N;
      if (i !== hotRef.current) {
        hotRef.current = i;
        setHot(i);
        if (pathRef.current[pathRef.current.length - 1] !== i) {
          pathRef.current = [...pathRef.current, i];
          setPath(pathRef.current);
        }
      }
    },

    onPanResponderRelease: () => {
      if (voiceRef.current !== "idle") return;
      const seq = pathRef.current.slice();
      setArmed(false); setHot(-1); setPath([]);
      hotRef.current = -1; pathRef.current = [];

      if (seq.length === 0) {
        // Centre tap with no direction: double-tap wakes the agent.
        const now = Date.now();
        if (now - lastTap.current < 350) { lastTap.current = 0; startVoice(); }
        else lastTap.current = now;
        return;
      }
      const chord = matchChord(seq);
      if (chord) fire(chord.key, chord.label, chord.icon);
      else {
        const act = ACTIONS[seq[seq.length - 1]];
        if (act) fire(act.key, act.label, act.icon);
      }
    },

    onPanResponderTerminate: () => {
      setArmed(false); setHot(-1); setPath([]);
      hotRef.current = -1; pathRef.current = [];
    },
  }), [fire, startVoice, stopVoice]);

  const pending = matchChord(path);
  const sum = state?.summary;
  const scale = size / VIEW;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.title}>openhome</Text>
        <Text style={styles.subtitle}>
          {sum
            ? `${sum.lightsOn}/${sum.lightsTotal} lights · ${sum.allLocked ? "locked" : "unlocked"}${sum.anyPlaying ? " · playing" : ""}`
            : "connecting…"}
        </Text>
      </View>

      {/* Breadcrumb: the gesture so far, and the chord it would fire. */}
      <View style={styles.crumbRow}>
        {path.length > 0 && (
          <View style={styles.crumb}>
            <Text style={styles.crumbArrows}>{path.map((i) => ARROW[i]).join(" ")}</Text>
            {pending && <Text style={styles.crumbName}>{pending.label}</Text>}
          </View>
        )}
      </View>

      <View
        ref={dialRef}
        collapsable={false}
        style={[styles.dial, { width: size, height: size }]}
        // PanResponder reports PAGE coordinates, so the centre has to be measured
        // in window space — layout x/y are relative to the parent and would put
        // the origin in the wrong place, skewing every angle.
        onLayout={() => {
          dialRef.current?.measureInWindow((px, py, w, h) => {
            if (w && h) centreRef.current = { x: px + w / 2, y: py + h / 2 };
          });
        }}
        {...responder.panHandlers}
      >
        <Svg width={size} height={size} viewBox={`0 0 ${VIEW} ${VIEW}`}>
          {ACTIONS.map((_, i) => {
            const near = hot >= 0 && (i === (hot + 1) % N || i === (hot - 1 + N) % N);
            return (
              <Path
                key={i}
                d={wedgePath(i)}
                fill={i === hot ? colors.accentWash : "transparent"}
                stroke={i === hot ? colors.accent : near ? colors.accentDim : colors.line}
                strokeWidth={i === hot ? 2 : 1}
                opacity={armed ? 1 : 0.35}
              />
            );
          })}
          {path.length > 1 && (
            <Polyline
              points={path.map((i) => polar(CX, CY, MID, i * STEP).join(",")).join(" ")}
              fill="none"
              stroke={colors.accent}
              strokeWidth={4}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={0.85}
            />
          )}
          <Circle cx={CX} cy={CY} r={INNER - 6} fill={colors.panel} stroke={colors.line} strokeWidth={1} />
        </Svg>

        {/* Wedge labels, positioned on the same 38% radius as the web surface. */}
        {ACTIONS.map((a, i) => {
          const [lx, ly] = polar(50, 50, 38, i * STEP);
          return (
            <View
              key={a.key}
              pointerEvents="none"
              style={[styles.label, { left: `${lx}%`, top: `${ly}%`, opacity: armed ? (i === hot ? 1 : 0.5) : 0.75 }]}
            >
              <Ionicons name={a.icon} size={20} color={i === hot ? colors.accent : colors.muted} />
              <Text style={[styles.labelText, i === hot && { color: colors.accent }]} numberOfLines={1}>{a.label}</Text>
            </View>
          );
        })}

        {/* Core — the openhome mark, as on the web dial. */}
        <View
          pointerEvents="none"
          style={[
            styles.core,
            { left: size / 2 - 52, top: size / 2 - 52 },
            armed && { borderColor: colors.accent },
          ]}
        >
          <LinearGradient colors={["#1b1730", "#15111f"]} style={styles.coreFill} />
          {voice === "thinking"
            ? <ActivityIndicator color={colors.accent} />
            : voice === "recording"
              ? <Ionicons name="radio-button-on" size={34} color={colors.accent} />
              : <Mark size={46} />}
        </View>
      </View>

      <Text style={styles.hint}>
        {voice === "recording" ? "Listening — tap to send"
          : voice === "thinking" ? "Thinking…"
          : armed ? "Release to run" : "Drag out to pick · double-tap to talk"}
      </Text>

      {/* Scene burst */}
      {burst && (
        <View style={styles.burst}>
          <Ionicons name={burst.icon} size={22} color={colors.accent} />
          <View style={{ flex: 1 }}>
            <Text style={styles.burstName}>{burst.label}</Text>
            {!!burst.sub && <Text style={styles.burstSub} numberOfLines={2}>{burst.sub}</Text>}
          </View>
        </View>
      )}

    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg, alignItems: "center" },
  header: { alignItems: "center", paddingTop: space(3) },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700" },
  subtitle: { color: colors.muted, fontSize: font.small, marginTop: space(1) },

  crumbRow: { height: 34, justifyContent: "center", marginTop: space(2) },
  crumb: {
    flexDirection: "row", alignItems: "center", gap: space(2),
    paddingHorizontal: space(4), paddingVertical: space(1),
    borderRadius: radius.pill, backgroundColor: colors.panelAlt,
    borderWidth: 1, borderColor: colors.accentDim,
  },
  crumbArrows: { color: colors.text, fontSize: font.body, fontWeight: "700", letterSpacing: 2 },
  crumbName: { color: colors.accent, fontSize: font.small, fontWeight: "700" },

  dial: { marginTop: space(2), alignItems: "center", justifyContent: "center" },
  label: {
    position: "absolute", width: 74, marginLeft: -37, marginTop: -22,
    alignItems: "center", gap: 2,
  },
  labelText: { color: colors.muted, fontSize: font.tiny, fontWeight: "700" },
  core: {
    position: "absolute", width: 104, height: 104, borderRadius: 52,
    alignItems: "center", justifyContent: "center", overflow: "hidden",
    borderWidth: 1, borderColor: colors.line,
    // Matches the web dial's drop shadow, which is what makes the core read as
    // sitting above the wedges rather than punched out of them.
    shadowColor: "#000", shadowOpacity: 0.5, shadowRadius: 20,
    shadowOffset: { width: 0, height: 10 }, elevation: 8,
  },
  coreFill: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 },

  hint: { color: colors.muted, fontSize: font.small, marginTop: space(4), fontWeight: "600" },

  burst: {
    flexDirection: "row", alignItems: "center", gap: space(3),
    marginTop: space(4), marginHorizontal: space(5),
    paddingHorizontal: space(5), paddingVertical: space(4),
    borderRadius: radius.lg, backgroundColor: colors.panel,
    borderWidth: 1, borderColor: colors.accentDim, alignSelf: "stretch",
  },
  burstName: { color: colors.text, fontSize: font.body, fontWeight: "700" },
  burstSub: { color: colors.muted, fontSize: font.tiny, marginTop: 2 },

});
