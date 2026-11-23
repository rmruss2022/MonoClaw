/**
 * "We can't find your hub" — the screen that must never dead-end.
 *
 * Before this existed, signing in with no reachable hub left you on the login
 * screen reading "no hub is paired to this account yet" with nothing to tap.
 * That is the worst moment in the product: the user has done everything right
 * and the app has nothing to offer.
 *
 * So every branch here offers a next step, in order of how little the user has
 * to know:
 *
 *   1. Searching…        automatic, covers the common case with zero effort
 *   2. Pairing code      read 6 characters off the hub — no networking knowledge
 *   3. Address by hand   for people who run their own DNS
 *   4. Help              for people who have not set a hub up at all
 */
import React, { useCallback, useEffect, useState } from "react";
import { View, Text, ScrollView, StyleSheet, TextInput, Pressable, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import * as client from "@/api/client";
import { Card, SectionTitle, PrimaryButton } from "@/components/ui";
import { colors, radius, font } from "@/theme";

type Phase = "searching" | "failed" | "connecting" | "connected";

/** Addresses worth trying on a local network when the cloud knows nothing. */
const LAN_GUESSES = ["http://openhome.local:4700", "http://raspberrypi.local:4700"];

export default function ConnectHubScreen({ onConnected }: { onConnected?: () => void }) {
  const [phase, setPhase] = useState<Phase>("searching");
  const [code, setCode] = useState("");
  const [manual, setManual] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [showManual, setShowManual] = useState(false);

  const search = useCallback(async () => {
    setPhase("searching");
    setNote(null);
    const ok = await client.ensureHome();
    if (ok) { setPhase("connected"); onConnected?.(); }
    else setPhase("failed");
  }, [onConnected]);

  useEffect(() => { void search(); }, [search]);

  const candidates = () => [
    ...client.getKnownAddresses().map((a) => a.url),
    ...LAN_GUESSES,
  ];

  const submitCode = async () => {
    if (code.trim().length < 4) { setNote("That code looks too short."); return; }
    setPhase("connecting");
    setNote(null);
    const url = await client.claimWithCode(code, candidates());
    if (url) { setPhase("connected"); onConnected?.(); }
    else {
      setPhase("failed");
      setNote("That code didn't work. Codes expire after 10 minutes — check the hub for a fresh one, and make sure your phone is on the same WiFi.");
    }
  };

  const submitManual = async () => {
    if (!manual.trim()) return;
    setPhase("connecting");
    setNote(null);
    const ok = await client.setHubUrlManual(manual);
    if (ok) { setPhase("connected"); onConnected?.(); }
    else {
      setPhase("failed");
      setNote("Couldn't reach a hub at that address. Check it's running and includes the port (usually :4700).");
    }
  };

  return (
    <SafeAreaView style={s.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
        {phase === "searching" || phase === "connecting" ? (
          <View style={s.center}>
            <ActivityIndicator color={colors.accent} size="large" />
            <Text style={s.big}>
              {phase === "searching" ? "Finding your hub…" : "Connecting…"}
            </Text>
            <Text style={s.help}>
              Checking your home network and your account at the same time.
            </Text>
          </View>
        ) : phase === "connected" ? (
          <View style={s.center}>
            <Text style={s.big}>Connected ✓</Text>
            <Text style={s.help}>Your hub is reachable.</Text>
          </View>
        ) : (
          <>
            <Text style={s.title}>We can't find your hub</Text>
            <Text style={s.help}>
              Your account is signed in — we just can't reach a hub right now.
              Any of these will fix it.
            </Text>
            {note ? <Text style={s.note}>{note}</Text> : null}

            <View style={s.gap} />
            <PrimaryButton label="Search again" onPress={search} />

            <View style={s.gap} />
            <SectionTitle>Enter the pairing code</SectionTitle>
            <Card>
              <Text style={s.help}>
                Your hub shows a 6-character code. Works on the same WiFi, no setup needed.
              </Text>
              <TextInput
                style={[s.input, s.codeInput]}
                value={code}
                onChangeText={(t) => setCode(t.toUpperCase())}
                placeholder="ABC123"
                placeholderTextColor={colors.muted}
                autoCapitalize="characters"
                autoCorrect={false}
                maxLength={6}
              />
              <View style={{ height: 12 }} />
              <PrimaryButton label="Pair hub" onPress={submitCode} />
            </Card>

            <View style={s.gap} />
            <Pressable onPress={() => setShowManual((v) => !v)}>
              <SectionTitle>{showManual ? "Hide advanced" : "Advanced — enter an address"}</SectionTitle>
            </Pressable>
            {showManual && (
              <Card>
                <Text style={s.help}>
                  If you run your own domain or know your hub's local address, put it here.
                  It takes priority over everything else.
                </Text>
                <TextInput
                  style={s.input}
                  value={manual}
                  onChangeText={setManual}
                  placeholder="https://home.example.com  or  http://192.168.1.50:4700"
                  placeholderTextColor={colors.muted}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                />
                <View style={{ height: 12 }} />
                <PrimaryButton label="Use this address" onPress={submitManual} />
              </Card>
            )}

            <View style={s.gap} />
            <SectionTitle>No hub yet?</SectionTitle>
            <Card>
              <Text style={s.help}>
                A hub is a small computer that runs your home — usually a Raspberry Pi.
                It keeps everything local, so your home keeps working even when the
                internet doesn't.
              </Text>
            </Card>
            <View style={{ height: 40 }} />
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 20, paddingBottom: 60, flexGrow: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", paddingVertical: 80 },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700", marginBottom: 8 },
  big: { color: colors.text, fontSize: font.h2, fontWeight: "600", marginTop: 18 },
  help: { color: colors.muted, fontSize: font.small, lineHeight: 19, marginBottom: 4, textAlign: "left" },
  note: { color: colors.warn, fontSize: font.small, lineHeight: 19, marginTop: 10 },
  gap: { height: 22 },
  input: {
    backgroundColor: colors.panelAlt, color: colors.text, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 11, fontSize: font.body, marginTop: 8,
  },
  codeInput: { fontSize: 26, letterSpacing: 6, textAlign: "center", fontWeight: "700" },
});
