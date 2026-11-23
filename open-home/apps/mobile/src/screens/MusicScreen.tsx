/**
 * Music — the library that the web surface (apps/app/music.html) always had and
 * the native app never did: AI-curated mixes, your liked songs, your playlists
 * and search, all playable into a room.
 *
 * Everything here already existed on the hub (/audio/spotify/home,
 * /audio/curator, /audio/spotify/search); this screen is the missing client.
 *
 * Playback always targets a *room*, never a device. The room picker is the one
 * piece of state the whole screen shares, because "play this" is meaningless
 * without "where".
 */
import React, { useCallback, useEffect, useState } from "react";
import {
  View, Text, ScrollView, StyleSheet, Pressable, Image,
  TextInput, ActivityIndicator, RefreshControl,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Ionicons from "@expo/vector-icons/Ionicons";
import { api } from "@/api/client";
import { usePoll, useCommand } from "@/api/hooks";
import { Card, SectionTitle, Empty, Loading } from "@/components/ui";
import { colors, radius, font, space } from "@/theme";

interface Track { id?: string; uri?: string; title?: string; artist?: string; image?: string }
interface Playlist { id?: string; uri?: string; name?: string; tracks?: number; image?: string; owner?: string }
interface Pick { label?: string; vibe?: string; image?: string; count?: number; uris?: string[] }
interface Home { mixes: Playlist[]; playlists: Playlist[]; liked: Track[]; top: Track[] }
interface Room { id: string; name: string; online: boolean }
interface NowPlaying { title?: string; artist?: string; image?: string; playing?: boolean; device?: string }

export default function MusicScreen() {
  // The room list rides along with /audio/state, which the Speakers tab already
  // polls; one more consumer is cheaper than a second endpoint.
  const { data: state, refresh: refreshState } = usePoll<{
    rooms: Room[]; spotify?: { connected?: boolean }; nowPlaying?: NowPlaying;
  }>("/audio/state", 6000);
  const run = useCommand();

  const [home, setHome] = useState<Home | null>(null);
  const [picks, setPicks] = useState<Pick[] | null>(null);
  const [room, setRoom] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Track[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const rooms = (state?.rooms ?? []).filter((r) => r.online);
  const np = state?.nowPlaying;

  const transport = useCallback(async (action: string) => {
    await run("/audio/command", { cmd: "transport", action });
    refreshState();
  }, [run, refreshState]);
  // Default to the only room rather than making the user pick in a one-room home.
  useEffect(() => {
    if (!room && rooms.length) setRoom(rooms[0].name);
  }, [rooms.length, room]);

  const loadLibrary = useCallback(async () => {
    try { setHome(await api<Home>("/audio/spotify/home")); } catch { setHome({ mixes: [], playlists: [], liked: [], top: [] }); }
    // The curator calls Spotify several times to build each mix, so it is slow
    // and allowed to arrive after the library rather than blocking it.
    try { const r = await api<{ picks: Pick[] }>("/audio/curator"); setPicks(r.picks ?? []); } catch { setPicks([]); }
  }, []);

  useEffect(() => { loadLibrary(); }, [loadLibrary]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await loadLibrary();
    setRefreshing(false);
  }, [loadLibrary]);

  const flash = (m: string) => { setNote(m); setTimeout(() => setNote(null), 3500); };

  const search = useCallback(async () => {
    const q = query.trim();
    if (!q) { setResults(null); return; }
    setSearching(true);
    try { const r = await api<{ tracks: Track[] }>(`/audio/spotify/search?q=${encodeURIComponent(q)}`); setResults(r.tracks ?? []); }
    catch { setResults([]); }
    finally { setSearching(false); }
  }, [query]);

  /** Play a set of track URIs, or a playlist context, into the chosen room. */
  const play = useCallback(async (
    key: string,
    body: { uris?: string[]; contextUri?: string },
    label: string,
  ) => {
    if (!room) { flash("Pick a room first"); return; }
    setBusy(key);
    try {
      const r: any = await run("/audio/command", { cmd: "spotify-play", room, ...body });
      flash(r?.hint || `Playing ${label} in ${room}`);
    } catch (e) {
      flash((e as Error).message || "Couldn't start playback");
    } finally {
      setBusy(null);
    }
  }, [room, run]);

  if (!home && !picks) return <Loading />;

  const connected = state?.spotify?.connected !== false;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
      >
        <Text style={styles.title}>Music</Text>

        {/* What's playing, and the transport. This used to be its own Speakers
            tab, but "what's playing" and "what to play" are the same errand —
            splitting them meant leaving the library to hit pause. */}
        {np?.title && (
          <Card active={!!np.playing} style={styles.np}>
            <View style={styles.npTop}>
              <Art uri={np.image} size={56} />
              <View style={{ flex: 1 }}>
                <Text style={styles.npTitle} numberOfLines={1}>{np.title}</Text>
                <Text style={styles.npArtist} numberOfLines={1}>
                  {np.artist}{np.device ? ` · ${np.device}` : ""}
                </Text>
              </View>
            </View>
            <View style={styles.transport}>
              <Pressable onPress={() => transport("prev")} accessibilityLabel="Previous track" style={styles.tbtn}>
                <Ionicons name="play-skip-back" size={22} color={colors.text} />
              </Pressable>
              <Pressable
                onPress={() => transport(np.playing ? "pause" : "play")}
                accessibilityLabel={np.playing ? "Pause" : "Play"}
                style={[styles.tbtn, styles.tmain]}
              >
                <Ionicons name={np.playing ? "pause" : "play"} size={22} color={colors.onAccent} />
              </Pressable>
              <Pressable onPress={() => transport("next")} accessibilityLabel="Next track" style={styles.tbtn}>
                <Ionicons name="play-skip-forward" size={22} color={colors.text} />
              </Pressable>
            </View>
          </Card>
        )}

        {/* Where it plays. */}
        {rooms.length > 0 && (
          <View style={styles.roomRow}>
            {rooms.map((r) => (
              <Pressable
                key={r.id}
                onPress={() => setRoom(r.name)}
                accessibilityRole="button"
                accessibilityState={{ selected: room === r.name }}
                style={[styles.roomChip, room === r.name && styles.roomChipOn]}
              >
                <Ionicons
                  name="volume-medium"
                  size={14}
                  color={room === r.name ? colors.accent : colors.muted}
                />
                <Text style={[styles.roomChipText, room === r.name && { color: colors.accent }]}>{r.name}</Text>
              </Pressable>
            ))}
          </View>
        )}

        {!connected && (
          <Card style={styles.warn}>
            <Text style={styles.warnText}>Spotify isn't linked. Open Settings to connect your account.</Text>
          </Card>
        )}

        {note && (
          <Card style={styles.note}>
            <Text style={styles.noteText}>{note}</Text>
          </Card>
        )}

        {/* Search */}
        <View style={styles.searchRow}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            value={query}
            onChangeText={setQuery}
            onSubmitEditing={search}
            returnKeyType="search"
            placeholder="Search songs and artists"
            placeholderTextColor={colors.muted}
            style={styles.searchInput}
            autoCorrect={false}
          />
          {searching
            ? <ActivityIndicator size="small" color={colors.accent} />
            : query.length > 0 && (
              <Pressable onPress={() => { setQuery(""); setResults(null); }} accessibilityLabel="Clear search">
                <Ionicons name="close-circle" size={18} color={colors.muted} />
              </Pressable>
            )}
        </View>

        {results !== null && (
          <>
            <SectionTitle>Results</SectionTitle>
            {results.length === 0 && <Empty text="Nothing matched that." />}
            {results.map((t, i) => (
              <TrackRow
                key={(t.id ?? "") + i}
                track={t}
                busy={busy === `s${i}`}
                onPlay={() => play(`s${i}`, { uris: [t.uri!] }, t.title ?? "track")}
              />
            ))}
          </>
        )}

        {/* AI mixes */}
        {picks && picks.length > 0 && (
          <>
            <SectionTitle>Made for you</SectionTitle>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hscroll}>
              {picks.map((p, i) => (
                <Pressable
                  key={(p.label ?? "") + i}
                  onPress={() => play(`p${i}`, { uris: p.uris }, p.label ?? "mix")}
                  disabled={!p.uris?.length || busy === `p${i}`}
                  accessibilityRole="button"
                  accessibilityLabel={`Play ${p.label}`}
                  style={({ pressed }) => [styles.mix, pressed && { opacity: 0.7 }]}
                >
                  <Art uri={p.image} size={132} busy={busy === `p${i}`} />
                  <Text style={styles.mixLabel} numberOfLines={1}>{p.label}</Text>
                  <Text style={styles.mixVibe} numberOfLines={2}>{p.vibe}</Text>
                </Pressable>
              ))}
            </ScrollView>
          </>
        )}

        {/* Playlists */}
        {!!home?.playlists?.length && (
          <>
            <SectionTitle>Your playlists</SectionTitle>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hscroll}>
              {home.playlists.map((p, i) => (
                <PlaylistCard
                  key={(p.id ?? "") + i}
                  playlist={p}
                  busy={busy === `pl${i}`}
                  onPlay={() => play(`pl${i}`, { contextUri: p.uri }, p.name ?? "playlist")}
                />
              ))}
            </ScrollView>
          </>
        )}

        {!!home?.mixes?.length && (
          <>
            <SectionTitle>Your mixes</SectionTitle>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.hscroll}>
              {home.mixes.map((p, i) => (
                <PlaylistCard
                  key={(p.id ?? "") + i}
                  playlist={p}
                  busy={busy === `mx${i}`}
                  onPlay={() => play(`mx${i}`, { contextUri: p.uri }, p.name ?? "mix")}
                />
              ))}
            </ScrollView>
          </>
        )}

        {/* Liked */}
        {!!home?.liked?.length && (
          <>
            <SectionTitle>Recently liked</SectionTitle>
            {home.liked.slice(0, 20).map((t, i) => (
              <TrackRow
                key={(t.id ?? "") + i}
                track={t}
                busy={busy === `l${i}`}
                // Start from this track but hand Spotify the rest of the liked
                // list, so playback keeps going instead of stopping after one song.
                onPlay={() => play(`l${i}`, { uris: home.liked.slice(i).map((x) => x.uri!).filter(Boolean) }, t.title ?? "track")}
              />
            ))}
          </>
        )}

        {!!home?.top?.length && (
          <>
            <SectionTitle>Your top tracks</SectionTitle>
            {home.top.slice(0, 10).map((t, i) => (
              <TrackRow
                key={(t.id ?? "") + i}
                track={t}
                busy={busy === `t${i}`}
                onPlay={() => play(`t${i}`, { uris: home.top.slice(i).map((x) => x.uri!).filter(Boolean) }, t.title ?? "track")}
              />
            ))}
          </>
        )}

        {home && !home.liked.length && !home.playlists.length && !picks?.length && (
          <Empty text="Nothing to show yet. Link Spotify in Settings and pull to refresh." />
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Art({ uri, size, busy }: { uri?: string; size: number; busy?: boolean }) {
  return (
    <View style={[styles.art, { width: size, height: size }]}>
      {uri ? <Image source={{ uri }} style={{ width: size, height: size, borderRadius: radius.md }} /> : null}
      {!uri && <Ionicons name="musical-notes" size={size / 3} color={colors.muted} />}
      {busy && (
        <View style={styles.artBusy}>
          <ActivityIndicator color={colors.accent} />
        </View>
      )}
    </View>
  );
}

function TrackRow({ track, onPlay, busy }: { track: Track; onPlay: () => void; busy: boolean }) {
  return (
    <Pressable
      onPress={onPlay}
      disabled={!track.uri || busy}
      accessibilityRole="button"
      accessibilityLabel={`Play ${track.title} by ${track.artist}`}
      style={({ pressed }) => [styles.row, pressed && { backgroundColor: colors.press }]}
    >
      <Art uri={track.image} size={44} />
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle} numberOfLines={1}>{track.title}</Text>
        <Text style={styles.rowSub} numberOfLines={1}>{track.artist}</Text>
      </View>
      {busy
        ? <ActivityIndicator size="small" color={colors.accent} />
        : <Ionicons name="play-circle" size={28} color={colors.accent} />}
    </Pressable>
  );
}

function PlaylistCard({ playlist, onPlay, busy }: { playlist: Playlist; onPlay: () => void; busy: boolean }) {
  return (
    <Pressable
      onPress={onPlay}
      disabled={!playlist.uri || busy}
      accessibilityRole="button"
      accessibilityLabel={`Play ${playlist.name}`}
      style={({ pressed }) => [styles.mix, pressed && { opacity: 0.7 }]}
    >
      <Art uri={playlist.image} size={132} busy={busy} />
      <Text style={styles.mixLabel} numberOfLines={1}>{playlist.name}</Text>
      <Text style={styles.mixVibe} numberOfLines={1}>
        {playlist.tracks ? `${playlist.tracks} tracks` : playlist.owner ?? ""}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.bg },
  content: { padding: space(5), paddingBottom: space(10) },
  title: { color: colors.text, fontSize: font.h1, fontWeight: "700", marginBottom: space(3) },

  roomRow: { flexDirection: "row", flexWrap: "wrap", gap: space(2), marginBottom: space(4) },
  roomChip: {
    flexDirection: "row", alignItems: "center", gap: space(2),
    minHeight: 36, paddingHorizontal: space(4),
    borderRadius: radius.pill, borderWidth: 1, borderColor: colors.line,
  },
  roomChipOn: { borderColor: colors.accentDim, backgroundColor: colors.accentWash },
  roomChipText: { color: colors.muted, fontSize: font.small, fontWeight: "700" },

  warn: { padding: space(4), marginBottom: space(4) },
  warnText: { color: colors.muted, fontSize: font.small },
  note: { padding: space(4), marginBottom: space(4) },
  noteText: { color: colors.text, fontSize: font.small },

  searchRow: {
    flexDirection: "row", alignItems: "center", gap: space(3),
    backgroundColor: colors.panelAlt, borderWidth: 1, borderColor: colors.line,
    borderRadius: radius.pill, paddingHorizontal: space(4), minHeight: 46,
    marginBottom: space(5),
  },
  searchInput: { flex: 1, color: colors.text, fontSize: font.body, paddingVertical: space(2) },

  np: { padding: space(4), marginBottom: space(4) },
  npTop: { flexDirection: "row", gap: space(3), alignItems: "center" },
  npTitle: { color: colors.text, fontSize: font.h2, fontWeight: "700" },
  npArtist: { color: colors.muted, fontSize: font.small, marginTop: space(1) },
  transport: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space(6), marginTop: space(4) },
  tbtn: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center" },
  tmain: { backgroundColor: colors.accent },

  hscroll: { gap: space(3), paddingRight: space(5), paddingBottom: space(4) },
  mix: { width: 132 },
  mixLabel: { color: colors.text, fontSize: font.small, fontWeight: "700", marginTop: space(2) },
  mixVibe: { color: colors.muted, fontSize: font.tiny, marginTop: space(1) },

  art: {
    borderRadius: radius.md, backgroundColor: colors.panelAlt,
    borderWidth: 1, borderColor: colors.line,
    alignItems: "center", justifyContent: "center", overflow: "hidden",
  },
  artBusy: {
    position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
    alignItems: "center", justifyContent: "center", backgroundColor: "rgba(0,0,0,0.45)",
  },

  row: {
    flexDirection: "row", alignItems: "center", gap: space(3),
    paddingVertical: space(2), paddingHorizontal: space(2),
    borderRadius: radius.md, marginBottom: space(1),
  },
  rowTitle: { color: colors.text, fontSize: font.body, fontWeight: "600" },
  rowSub: { color: colors.muted, fontSize: font.tiny, marginTop: 2 },
});
