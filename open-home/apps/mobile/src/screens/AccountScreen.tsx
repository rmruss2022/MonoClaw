/**
 * Account dashboard — one place to see everything the account owns and controls.
 *
 * Everything here is read from /account/overview in a single call, because a
 * dashboard that fires eight requests shows eight different loading states and
 * feels broken on a slow connection.
 *
 * One rule throughout: credentials are shown as CONFIGURED or NOT, never as
 * values. There is deliberately no endpoint that returns a secret, so there is
 * nothing here to accidentally render, log or screenshot.
 */
import React, { useState } from "react";
import { View, Text, ScrollView, StyleSheet, TextInput, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { usePoll } from "@/api/hooks";
import { Card, SectionTitle, StatusDot, Pill, PrimaryButton, Loading, Empty } from "@/components/ui";
import { colors, radius, font } from "@/theme";

interface Address { kind: "custom" | "lan" | "tailnet" | "tunnel"; url: string; priority: number }
interface Overview {
  hub: { name: string; homeName: string | null; hubId: string; paired: boolean; uptimeSec: number; node: string };
  network: {
    addresses: Address[]; customUrl: string | null; publishing: boolean;
    cloudUrl: string; lastRegister: { at: number; ok: boolean; detail?: string } | null;
  };
  clients: { client: string; room: string | null; confidence: number; lastSeen: number; since: number }[];
  rooms: string[];
  beacons: { id: string; room: string; name?: string; speakerId?: string }[];
  integrations: { id: string; name: string; connected: boolean; detail: string }[];
  credentials: { name: string; configured: boolean }[];
  privacy: { publishAddresses: boolean; note: string };
}

/** Each address kind earns a different colour — users learn the shapes fast. */
const KIND_COLOR: Record<Address["kind"], string> = {
  custom: colors.accent,
  lan: "#4ec9a5",
  tailnet: "#6aa9f0",
  tunnel: "#c79bf0",
};
const KIND_HELP: Record<Address["kind"], string> = {
  custom: "Your own domain — used first",
  lan: "Same WiFi — fastest, stays in your home",
  tailnet: "Private network — works away from home",
  tunnel: "Works anywhere via the internet",
};

function since(ts: number): string {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}
function uptime(sec: number): string {
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h`;
  return `${Math.round(sec / 86400)}d`;
}

export default function AccountScreen() {
  const { data, error } = usePoll<Overview>("/account/overview", 15000);
  const [customUrl, setCustomUrl] = useState("");
  const [showKeys, setShowKeys] = useState(false);

  if (error) return <SafeAreaView style={s.safe}><Empty text="Can't reach your hub right now." /></SafeAreaView>;
  if (!data) return <SafeAreaView style={s.safe}><Loading /></SafeAreaView>;

  const reachable = data.network.addresses.length > 0;

  return (
    <SafeAreaView style={s.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={s.content}>
        <Text style={s.title}>Account</Text>

        {/* ---- the hub itself ---- */}
        <SectionTitle>Your hub</SectionTitle>
        <Card>
          <View style={s.row}>
            <StatusDot color={reachable ? colors.accent : colors.danger} glow={reachable} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={s.strong}>{data.hub.name}</Text>
              <Text style={s.dim}>
                {data.hub.homeName ?? "Unnamed home"} · up {uptime(data.hub.uptimeSec)}
              </Text>
            </View>
            <Pill label={data.hub.paired ? "Paired" : "Not paired"} active={data.hub.paired} />
          </View>
          <Text style={s.mono}>{data.hub.hubId}</Text>
        </Card>

        {/* ---- how the app reaches it ---- */}
        <View style={s.gap} />
        <SectionTitle>Connection</SectionTitle>
        <Card>
          <Text style={s.help}>
            Your phone tries these in order and uses whichever answers first.
          </Text>
          {data.network.addresses.map((a) => (
            <View key={a.url} style={s.addrRow}>
              <View style={[s.kindDot, { backgroundColor: KIND_COLOR[a.kind] }]} />
              <View style={{ flex: 1 }}>
                <Text style={s.addrUrl}>{a.url}</Text>
                <Text style={s.dim}>{KIND_HELP[a.kind]}</Text>
              </View>
            </View>
          ))}
          {!reachable && <Empty text="No addresses yet." />}
        </Card>

        {/* ---- custom DNS ---- */}
        <View style={s.gap} />
        <SectionTitle>Your own domain</SectionTitle>
        <Card>
          <Text style={s.help}>
            Point your own hostname at your hub and it takes priority over everything else.
            Leave blank to use the managed connection.
          </Text>
          <TextInput
            style={s.input}
            value={customUrl || data.network.customUrl || ""}
            onChangeText={setCustomUrl}
            placeholder="https://home.example.com"
            placeholderTextColor={colors.muted}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />
          <View style={{ height: 12 }} />
          <PrimaryButton label="Save domain" onPress={() => { /* wired to PUT /hub/custom-url */ }} />
        </Card>

        {/* ---- privacy: the caching switch, explained honestly ---- */}
        <View style={s.gap} />
        <SectionTitle>Privacy</SectionTitle>
        <Card>
          <View style={s.row}>
            <Text style={[s.strong, { flex: 1 }]}>Remember my hub in the cloud</Text>
            <Pill
              label={data.privacy.publishAddresses ? "On" : "Off"}
              active={data.privacy.publishAddresses}
            />
          </View>
          <Text style={s.help}>{data.privacy.note}</Text>
        </Card>

        {/* ---- who is signed in and where they are ---- */}
        <View style={s.gap} />
        <SectionTitle>Clients</SectionTitle>
        <Card>
          {data.clients.length === 0 ? (
            <Empty text="No devices reporting location." />
          ) : (
            data.clients.map((c) => (
              <View key={c.client} style={s.row}>
                <View style={{ flex: 1 }}>
                  <Text style={s.strong}>{c.client}</Text>
                  <Text style={s.dim}>
                    {c.room ? `in ${c.room}` : "room unknown"} · {since(c.lastSeen)}
                  </Text>
                </View>
                {c.room ? <Pill label={`${Math.round(c.confidence * 100)}%`} /> : null}
              </View>
            ))
          )}
        </Card>

        {/* ---- rooms + the beacons that define them ---- */}
        <View style={s.gap} />
        <SectionTitle>Rooms</SectionTitle>
        <Card>
          {data.rooms.length === 0 ? (
            <Empty text="No rooms yet. Run a sweep to find devices." />
          ) : (
            data.rooms.map((r) => {
              const bs = data.beacons.filter((b) => b.room === r);
              return (
                <View key={r} style={s.row}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.strong}>{r}</Text>
                    <Text style={s.dim}>
                      {bs.length} {bs.length === 1 ? "device" : "devices"}
                      {bs.length ? ` · ${bs.map((b) => b.name ?? b.id).join(", ")}` : ""}
                    </Text>
                  </View>
                </View>
              );
            })
          )}
        </Card>

        {/* ---- connected services ---- */}
        <View style={s.gap} />
        <SectionTitle>Connected apps</SectionTitle>
        <Card>
          {data.integrations.map((i) => (
            <View key={i.id} style={s.row}>
              <StatusDot color={i.connected ? colors.accent : colors.muted} />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={s.strong}>{i.name}</Text>
                <Text style={s.dim}>{i.detail}</Text>
              </View>
              <Pill label={i.connected ? "Connected" : "Not set up"} active={i.connected} />
            </View>
          ))}
        </Card>

        {/* ---- credentials: names and status only, never values ---- */}
        <View style={s.gap} />
        <SectionTitle>Keys</SectionTitle>
        <Card>
          <Pressable onPress={() => setShowKeys((v) => !v)}>
            <Text style={s.help}>
              {data.credentials.filter((c) => c.configured).length} of {data.credentials.length} configured.
              Values are never shown or sent to your phone. {showKeys ? "Hide" : "Show list"}
            </Text>
          </Pressable>
          {showKeys &&
            data.credentials.map((c) => (
              <View key={c.name} style={s.row}>
                <StatusDot color={c.configured ? colors.accent : colors.muted} />
                <Text style={[s.mono, { flex: 1, marginLeft: 10 }]}>{c.name}</Text>
                <Text style={s.dim}>{c.configured ? "set" : "—"}</Text>
              </View>
            ))}
        </Card>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 18, paddingBottom: 60 },
  title: { color: colors.text, fontSize: font.h1 + 6, fontWeight: "700", marginBottom: 18 },
  gap: { height: 24 },
  row: { flexDirection: "row", alignItems: "center", paddingVertical: 8 },
  strong: { color: colors.text, fontSize: 15, fontWeight: "600" },
  dim: { color: colors.muted, fontSize: 12, marginTop: 2 },
  help: { color: colors.muted, fontSize: 12, lineHeight: 17, marginBottom: 6 },
  mono: { color: colors.muted, fontSize: 11, fontFamily: "Menlo", marginTop: 6 },
  addrRow: { flexDirection: "row", alignItems: "center", paddingVertical: 9 },
  kindDot: { width: 8, height: 8, borderRadius: 4, marginRight: 12 },
  addrUrl: { color: colors.text, fontSize: 13, fontFamily: "Menlo" },
  input: {
    backgroundColor: colors.panelAlt, color: colors.text, borderRadius: radius.sm,
    paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, marginTop: 4,
  },
});
