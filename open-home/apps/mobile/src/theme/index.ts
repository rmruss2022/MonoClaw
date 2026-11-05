/**
 * openhome design tokens — ported 1:1 from the web control surface
 * (apps/app/*.html :root variables) so the native app reads as the same product.
 */
export const colors = {
  // Lumen-inspired cosmic palette (deep purple-black, gold + purple accents).
  bg: "#0b0a12",
  bgElev: "#13111d",
  panel: "#181527",
  panelAlt: "#0e0b1a",
  line: "#2a2540",
  text: "#ece9f5",
  muted: "#9a93b8",
  accent: "#f5c977",
  accentDim: "#b78a2e",
  accentWash: "rgba(245,201,119,0.10)",
  purple: "#a855f7",
  purple2: "#7c3aed",
  pink: "#ec4899",
  danger: "#ff6b6b",
  warn: "#f5b544",
  // Status: online / playing / "on" indicators (AA on the night bg).
  success: "#5fd38d",
  // Ink used on top of the gold accent (buttons, active knobs). High-contrast.
  onAccent: "#1a1205",
  // Pressable feedback overlay.
  press: "rgba(255,255,255,0.06)",
};

export const radius = {
  sm: 10,
  md: 14,
  lg: 18,
  pill: 999,
};

// 8pt-based spacing scale: space(1)=4, space(2)=8, space(3)=12, space(4)=16…
export const space = (n: number) => n * 4;

/** Calm, consistent card elevation shared across every surface. */
export const elevation = {
  card: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.28,
    shadowRadius: 14,
    elevation: 5,
  },
} as const;

export const font = {
  h1: 24,
  h2: 18,
  body: 15,
  small: 13,
  tiny: 11,
};

export type Theme = typeof colors;
