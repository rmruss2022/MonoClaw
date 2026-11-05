import React from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  StyleProp,
} from "react-native";
import { colors, radius, font, space, elevation } from "@/theme";

/**
 * The single card surface for the whole app. Rounded, softly elevated, calm.
 * `active` lifts a card into the "on / playing" state with an accent edge.
 */
export function Card({
  children,
  style,
  active,
}: {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  active?: boolean;
}) {
  return <View style={[styles.card, active && styles.cardActive, style]}>{children}</View>;
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <Text style={styles.section}>{children}</Text>;
}

/** Small status dot — green=online/on, muted=off/offline. `glow` adds a soft halo. */
export function StatusDot({ color, glow }: { color: string; glow?: boolean }) {
  return (
    <View
      style={[
        styles.dot,
        { backgroundColor: color },
        glow && { shadowColor: color, shadowOpacity: 0.9, shadowRadius: 7, shadowOffset: { width: 0, height: 0 } },
      ]}
    />
  );
}

/** Presentational switch (the row around it owns the Pressable + a11y state). */
export function Toggle({ on }: { on: boolean }) {
  return (
    <View style={[styles.toggle, on && styles.toggleOn]}>
      <View style={[styles.knob, on && styles.knobOn]} />
    </View>
  );
}

export function Pill({
  label,
  active,
  onPress,
}: {
  label: string;
  active?: boolean;
  onPress?: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: !!active }}
      style={({ pressed }) => [styles.pill, active && styles.pillOn, pressed && styles.pressed]}
    >
      <Text style={[styles.pillText, active && styles.pillTextOn]}>{label}</Text>
    </Pressable>
  );
}

export function PrimaryButton({
  label,
  onPress,
  loading,
  disabled,
}: {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityState={{ disabled: !!(disabled || loading) }}
      style={({ pressed }) => [styles.btn, (disabled || loading) && { opacity: 0.6 }, pressed && { opacity: 0.85 }]}
    >
      {loading ? (
        <ActivityIndicator color={colors.onAccent} />
      ) : (
        <Text style={styles.btnText}>{label}</Text>
      )}
    </Pressable>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

export function Loading() {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.accent} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.lg,
    padding: space(4),
    ...elevation.card,
  },
  cardActive: {
    borderColor: colors.accentDim,
    backgroundColor: colors.bgElev,
  },
  section: {
    color: colors.muted,
    fontSize: font.tiny,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
  toggle: {
    width: 48,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 3,
    justifyContent: "center",
  },
  toggleOn: { backgroundColor: colors.accentWash, borderColor: colors.accentDim },
  knob: { width: 20, height: 20, borderRadius: 10, backgroundColor: colors.muted },
  knobOn: { backgroundColor: colors.accent, alignSelf: "flex-end" },
  pill: {
    minHeight: 44,
    paddingVertical: space(2),
    paddingHorizontal: space(4),
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    alignItems: "center",
    justifyContent: "center",
  },
  pillOn: {
    borderColor: colors.accentDim,
    backgroundColor: colors.accentWash,
  },
  pillText: { color: colors.muted, fontWeight: "700", fontSize: font.small },
  pillTextOn: { color: colors.accent },
  pressed: { opacity: 0.7 },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: radius.md,
    minHeight: 48,
    paddingVertical: space(3),
    alignItems: "center",
    justifyContent: "center",
  },
  btnText: { color: colors.onAccent, fontWeight: "700", fontSize: font.body },
  empty: { padding: space(6), alignItems: "center" },
  emptyText: { color: colors.muted, fontSize: font.small, textAlign: "center", lineHeight: 20 },
  loading: { padding: space(10), alignItems: "center" },
});
