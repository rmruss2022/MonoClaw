import React, { useState } from "react";
import { View, Text, ScrollView, StyleSheet, TextInput } from "react-native";
import Constants from "expo-constants";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "@/context/AuthContext";
import { usePoll } from "@/api/hooks";
import { Card, SectionTitle, PrimaryButton } from "@/components/ui";
import { colors, radius, font } from "@/theme";

/** Marketing version, and the build number TestFlight shows next to it. */
const version = Constants.expoConfig?.version ?? "?";
// nativeBuildVersion FIRST, deliberately: eas.json uses appVersionSource
// "remote" with autoIncrement, so app.json has no buildNumber at all and the
// config value would read "?" on exactly the builds this line exists to
// identify. The native value is the one TestFlight shows.
const build = Constants.nativeBuildVersion ?? Constants.expoConfig?.ios?.buildNumber ?? "?";

export default function SettingsScreen() {
  const { controlPlane, setControlPlane, signOut, email } = useAuth();
  const health = usePoll<{ status?: string; model?: string; devices?: number }>("/health", 10000);
  const [cp, setCp] = useState(controlPlane);
  const [saved, setSaved] = useState(false);

  const save = async () => {
    await setControlPlane(cp);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>Settings</Text>

        <SectionTitle>Home</SectionTitle>
        <Card>
          <View style={styles.statusRow}>
            <View style={[styles.dot, { backgroundColor: health.data?.status === "ok" ? colors.accent : colors.danger }]} />
            <Text style={styles.statusText}>
              {health.data?.status === "ok"
                ? `Connected · ${health.data.model ?? "agent"} · ${health.data.devices ?? 0} devices`
                : "Not reachable"}
            </Text>
          </View>
        </Card>

        <View style={{ height: 24 }} />
        <SectionTitle>Account</SectionTitle>
        <Card>
          <Text style={styles.body}>{email ? `Signed in as ${email}` : "Signed in"}</Text>
          <View style={{ height: 14 }} />
          <PrimaryButton label="Sign out" onPress={signOut} />
        </Card>

        <View style={{ height: 24 }} />
        <SectionTitle>Advanced</SectionTitle>
        <Card>
          <Text style={styles.label}>Control-plane URL</Text>
          <TextInput
            style={styles.input}
            value={cp}
            onChangeText={setCp}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <View style={{ height: 12 }} />
          <PrimaryButton label={saved ? "Saved ✓" : "Save"} onPress={save} />
        </Card>

        {/* Which build is actually running. Added after a TestFlight update
            silently did not take: the app looked wrong, nothing in it could
            say why, and proving it needed the shipped .ipa pulled apart on a
            laptop. One line here answers it on the device. */}
        <Text style={styles.tag}>
          openhome {version} ({build}) · your home, your keys
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 20, paddingBottom: 40 },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700", marginBottom: 10 },
  label: { color: colors.muted, fontSize: font.tiny, marginBottom: 6 },
  input: {
    backgroundColor: colors.bg,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingVertical: 12,
    paddingHorizontal: 14,
    color: colors.text,
    fontSize: 15,
  },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 9, height: 9, borderRadius: 5 },
  statusText: { color: colors.muted, fontSize: font.small },
  body: { color: colors.muted, fontSize: font.small, lineHeight: 20 },
  tag: { color: colors.muted, fontSize: font.tiny, textAlign: "center", marginTop: 30 },
});
