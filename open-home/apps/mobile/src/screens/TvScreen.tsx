import React, { useCallback, useEffect, useState } from "react";
import { View, Text, TextInput, ScrollView, StyleSheet, Pressable, Image, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { tv, type TvTitle, type TvStick } from "@/api/tvClient";
import { SectionTitle, Empty, PrimaryButton } from "@/components/ui";
import { colors, radius, font } from "@/theme";

export default function TvScreen() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<TvTitle[]>([]);
  const [sticks, setSticks] = useState<TvStick[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pairCode, setPairCode] = useState("");

  const refreshSticks = useCallback(async () => {
    try {
      const s = await tv.sticks();
      setSticks(s);
      setActive((a) => a ?? s.find((x) => x.online)?.id ?? s[0]?.id ?? null);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    (async () => {
      await refreshSticks();
      try { setResults(await tv.trending()); } catch {}
      setLoading(false);
    })();
  }, [refreshSticks]);

  const runSearch = useCallback(async () => {
    setLoading(true);
    try { setResults(q.trim() ? await tv.search(q.trim()) : await tv.trending()); } catch {}
    setLoading(false);
  }, [q]);

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2200); };

  const cast = useCallback(async (t: TvTitle) => {
    if (!active) { flash("Pair a stick first"); return; }
    const r = await tv.cast(t.id, active);
    flash(r.ok ? `▶ ${t.name} → ${r.castTo}` : r.reason || "Couldn't cast");
  }, [active]);

  const claim = useCallback(async () => {
    const r = await tv.pair(pairCode.trim());
    if (r.ok) { setPairCode(""); flash(`Paired ${r.stick?.name}`); refreshSticks(); }
    else flash(r.error === "bad_or_expired_code" ? "Bad or expired code" : "Pairing failed");
  }, [pairCode, refreshSticks]);

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>TV</Text>

        {/* Stick picker / pairing */}
        {sticks.length > 0 ? (
          <View style={styles.sticks}>
            {sticks.map((s) => (
              <Pressable key={s.id} onPress={() => setActive(s.id)} style={[styles.stick, active === s.id && styles.stickOn]}>
                <View style={[styles.dot, { backgroundColor: s.online ? colors.accent : colors.muted }]} />
                <Text style={[styles.stickName, active === s.id && { color: colors.accent }]}>{s.name}</Text>
              </Pressable>
            ))}
          </View>
        ) : (
          <View style={styles.pair}>
            <Text style={styles.pairText}>Pair your openhome TV stick — enter the code shown on your TV:</Text>
            <View style={{ flexDirection: "row", gap: 8, marginTop: 10 }}>
              <TextInput
                style={[styles.input, { flex: 1 }]} value={pairCode} onChangeText={setPairCode}
                keyboardType="number-pad" placeholder="123456" placeholderTextColor={colors.muted} maxLength={6}
              />
              <View style={{ width: 110 }}><PrimaryButton label="Pair" onPress={claim} /></View>
            </View>
          </View>
        )}

        {/* Search */}
        <TextInput
          style={styles.input} value={q} onChangeText={setQ} onSubmitEditing={runSearch}
          returnKeyType="search" autoCapitalize="none" placeholder="Search movies, shows, music…"
          placeholderTextColor={colors.muted}
        />

        <SectionTitle>{q.trim() ? "Results" : "Trending"}</SectionTitle>
        {loading && <ActivityIndicator color={colors.accent} style={{ marginTop: 20 }} />}
        {!loading && results.length === 0 && <Empty text="Nothing found. Try another title." />}

        {results.map((t) => (
          <Pressable key={t.id} style={styles.row} onPress={() => cast(t)}>
            {t.poster ? <Image source={{ uri: t.poster }} style={styles.poster} /> : <View style={styles.poster} />}
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{t.name}{t.year ? ` (${t.year})` : ""}</Text>
              <Text style={styles.meta} numberOfLines={1}>
                {t.type}{t.rating ? ` · ★ ${t.rating}` : ""}{t.sources.length ? ` · ${t.sources.map((s) => s.serviceName).join(", ")}` : " · not available"}
              </Text>
            </View>
            <View style={styles.castBtn}><Text style={styles.castText}>Cast</Text></View>
          </Pressable>
        ))}
      </ScrollView>

      {toast && <View style={styles.toast}><Text style={styles.toastText}>{toast}</Text></View>}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 20, paddingBottom: 60 },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700", marginBottom: 12 },
  sticks: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 14 },
  stick: { flexDirection: "row", alignItems: "center", gap: 7, paddingVertical: 7, paddingHorizontal: 12, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.panel },
  stickOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  dot: { width: 8, height: 8, borderRadius: 4 },
  stickName: { color: colors.muted, fontWeight: "700", fontSize: font.small },
  pair: { backgroundColor: colors.panel, borderColor: colors.line, borderWidth: 1, borderRadius: radius.md, padding: 14, marginBottom: 14 },
  pairText: { color: colors.muted, fontSize: font.small, lineHeight: 20 },
  input: { backgroundColor: colors.panel, borderColor: colors.line, borderWidth: 1, borderRadius: radius.md, paddingVertical: 12, paddingHorizontal: 14, color: colors.text, fontSize: 16, marginBottom: 8 },
  row: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.panel, borderColor: colors.line, borderWidth: 1, borderRadius: radius.md, padding: 10, marginBottom: 8 },
  poster: { width: 46, height: 68, borderRadius: 8, backgroundColor: colors.panelAlt, borderWidth: 1, borderColor: colors.line },
  name: { color: colors.text, fontSize: font.body, fontWeight: "600" },
  meta: { color: colors.muted, fontSize: font.tiny, marginTop: 3 },
  castBtn: { paddingVertical: 8, paddingHorizontal: 16, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  castText: { color: colors.accent, fontWeight: "700", fontSize: font.small },
  toast: { position: "absolute", bottom: 28, alignSelf: "center", backgroundColor: colors.panel, borderColor: colors.accentDim, borderWidth: 1, borderRadius: radius.pill, paddingVertical: 12, paddingHorizontal: 20 },
  toastText: { color: colors.text, fontWeight: "600" },
});
