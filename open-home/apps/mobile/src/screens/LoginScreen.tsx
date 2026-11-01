import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Pressable,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "@/context/AuthContext";
import { PrimaryButton } from "@/components/ui";
import { colors, radius, font } from "@/theme";

export default function LoginScreen() {
  const { signIn, controlPlane, setControlPlane } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [cp, setCp] = useState(controlPlane);
  const [showCp, setShowCp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setErr(null);
    setBusy(true);
    try {
      if (cp && cp !== controlPlane) await setControlPlane(cp);
      const r = await signIn(email.trim(), password);
      if (r === "bad") setErr("Wrong email or password.");
      else if (r === "error") setErr("Couldn't reach openhome. Check your connection.");
      else if (r === "no_home") setErr("Signed in, but no hub is paired to this account yet.");
    } catch {
      setErr("Something went wrong signing in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.center}
      >
        <View style={styles.card}>
          <View style={styles.brand}>
            <View style={styles.dot} />
            <Text style={styles.brandText}>openhome</Text>
          </View>
          <Text style={styles.sub}>Sign in to your home.</Text>

          <Text style={styles.label}>Email</Text>
          <TextInput
            style={styles.input}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="username"
            placeholder="you@email.com"
            placeholderTextColor={colors.muted}
          />

          <Text style={[styles.label, { marginTop: 14 }]}>Password</Text>
          <TextInput
            style={styles.input}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            textContentType="password"
            placeholder="••••••••"
            placeholderTextColor={colors.muted}
            onSubmitEditing={onSubmit}
            returnKeyType="go"
          />

          {showCp && (
            <>
              <Text style={[styles.label, { marginTop: 14 }]}>Control-plane URL</Text>
              <TextInput
                style={styles.input}
                value={cp}
                onChangeText={setCp}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                placeholder="https://…"
                placeholderTextColor={colors.muted}
              />
            </>
          )}

          <View style={{ height: 16 }} />
          <PrimaryButton label="Sign in" onPress={onSubmit} loading={busy} />

          {err && <Text style={styles.err}>{err}</Text>}

          <Pressable onPress={() => setShowCp((s) => !s)} style={styles.footBtn}>
            <Text style={styles.foot}>{showCp ? "Hide advanced" : "Advanced"}</Text>
          </Pressable>
          <Text style={styles.tag}>Your home. Your keys.</Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  card: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: 28,
  },
  brand: { flexDirection: "row", alignItems: "center", gap: 10, marginBottom: 6 },
  dot: {
    width: 11,
    height: 11,
    borderRadius: 6,
    backgroundColor: colors.accent,
    shadowColor: colors.accent,
    shadowOpacity: 0.9,
    shadowRadius: 6,
  },
  brandText: { color: colors.text, fontWeight: "700", fontSize: font.h2 },
  sub: { color: colors.muted, fontSize: font.small, marginBottom: 22 },
  label: { color: colors.muted, fontSize: font.tiny, marginBottom: 6 },
  input: {
    backgroundColor: colors.bg,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingVertical: 13,
    paddingHorizontal: 14,
    color: colors.text,
    fontSize: 16,
  },
  err: { color: colors.danger, fontSize: font.small, marginTop: 12 },
  footBtn: { marginTop: 18, alignItems: "center" },
  foot: { color: colors.accent, fontSize: font.small, fontWeight: "600" },
  tag: { marginTop: 16, color: colors.muted, fontSize: font.tiny, textAlign: "center" },
});
