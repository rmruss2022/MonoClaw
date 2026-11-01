/**
 * openhome TV — stick client (Android TV).
 *
 * Boots into this app. If unpaired, shows a 6-digit code the user enters in the
 * phone app. Once paired it:
 *   - opens an SSE control channel to the content-router,
 *   - renders trending/search rails,
 *   - on a `launch` command, fires the Android deep-link intent (Linking.openURL)
 *     to open the right streaming app to the exact title,
 *   - reports which streaming apps are installed (improves routing).
 *
 * Built with react-native-tvos so it shares TypeScript + the openhome design
 * language with the phone app. See README for the TV toolchain setup.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { View, Text, FlatList, Image, Pressable, StyleSheet, Linking } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import EventSource from "react-native-sse";
import { RouterClient, type Title, type LaunchCommand } from "./src/router";

// Point at your deployed content-router.
const ROUTER_URL = "https://tv.bedrock.casa";
// Streaming apps whose Android packages are installed on this stick. In P3 this
// is auto-detected via a native module; for now it's declared.
const INSTALLED = ["netflix", "prime", "hbomax", "youtube", "disney", "spotify"];

const colors = { bg: "#0e1014", panel: "#171a21", line: "#272c37", text: "#e7ebf3", muted: "#8b93a7", accent: "#3ddc97" };

async function stickIdentity() {
  let id = await AsyncStorage.getItem("oh_stick_id");
  if (!id) { id = "stick-" + Math.random().toString(36).slice(2, 10); await AsyncStorage.setItem("oh_stick_id", id); }
  let token = await AsyncStorage.getItem("oh_stick_token");
  return { id, token };
}

export default function App() {
  const [code, setCode] = useState<string | null>(null);
  const [rows, setRows] = useState<Title[]>([]);
  const [status, setStatus] = useState("Starting…");
  const client = useRef(new RouterClient(ROUTER_URL));
  const stick = useRef<{ id: string; token: string | null }>({ id: "", token: null });

  const launch = useCallback(async (cmd: LaunchCommand) => {
    setStatus(`Opening ${cmd.service} → ${cmd.title.name}`);
    try { await Linking.openURL(cmd.deepLink); } catch { setStatus(`Couldn't open ${cmd.service}`); }
  }, []);

  useEffect(() => {
    let es: EventSource | null = null;
    (async () => {
      const ident = await stickIdentity();
      stick.current = ident;
      // Always (re)register for a pairing code; it's harmless once claimed and
      // gives us a fresh stick token to authenticate the channel.
      const pair = await client.current.beginPairing(ident.id, "openhome TV");
      stick.current.token = (pair as any).stickToken;
      await AsyncStorage.setItem("oh_stick_token", stick.current.token!);
      client.current.setToken(stick.current.token!);
      setCode(pair.code);
      try { await client.current.reportApps(ident.id, INSTALLED, INSTALLED); } catch {}
      try { setRows(await client.current.trending()); } catch {}

      // Open the control channel.
      es = new EventSource(client.current.streamUrl(ident.id), {
        headers: { Authorization: `Bearer ${stick.current.token}` },
      });
      es.addEventListener("open", () => { setStatus("Connected"); setCode(null); });
      es.addEventListener("launch", (e: any) => launch(JSON.parse(e.data)));
      es.addEventListener("error", () => setStatus("Reconnecting…"));
    })();
    return () => es?.close();
  }, [launch]);

  if (code) {
    return (
      <View style={[styles.full, styles.center]}>
        <Text style={styles.brand}>openhome TV</Text>
        <Text style={styles.sub}>Open the openhome app on your phone and enter this code to pair:</Text>
        <Text style={styles.code}>{code}</Text>
      </View>
    );
  }

  return (
    <View style={styles.full}>
      <View style={styles.top}>
        <Text style={styles.brand}>openhome TV</Text>
        <Text style={styles.status}>{status}</Text>
      </View>
      <Text style={styles.rail}>Trending</Text>
      <FlatList
        horizontal
        data={rows}
        keyExtractor={(t) => t.id}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: 32, gap: 16 }}
        renderItem={({ item }) => (
          <Pressable style={styles.card}>
            {item.poster ? <Image source={{ uri: item.poster }} style={styles.poster} /> : <View style={styles.poster} />}
            <Text style={styles.cardName} numberOfLines={1}>{item.name}</Text>
            <Text style={styles.cardMeta} numberOfLines={1}>{item.sources.map((s) => s.serviceName).join(" · ")}</Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  full: { flex: 1, backgroundColor: colors.bg, paddingTop: 48 },
  center: { alignItems: "center", justifyContent: "center", gap: 18 },
  brand: { color: colors.text, fontSize: 34, fontWeight: "800", letterSpacing: -1 },
  sub: { color: colors.muted, fontSize: 20, maxWidth: 680, textAlign: "center", lineHeight: 28 },
  code: { color: colors.accent, fontSize: 72, fontWeight: "900", letterSpacing: 10, marginTop: 8 },
  top: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", paddingHorizontal: 32, marginBottom: 28 },
  status: { color: colors.accent, fontSize: 18, fontWeight: "600" },
  rail: { color: colors.muted, fontSize: 16, fontWeight: "700", textTransform: "uppercase", letterSpacing: 1, paddingHorizontal: 32, marginBottom: 14 },
  card: { width: 220 },
  poster: { width: 220, height: 320, borderRadius: 14, backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.line },
  cardName: { color: colors.text, fontSize: 18, fontWeight: "700", marginTop: 10 },
  cardMeta: { color: colors.muted, fontSize: 14, marginTop: 2 },
});
