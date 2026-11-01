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
};

export const radius = {
  sm: 10,
  md: 14,
  lg: 18,
  pill: 999,
};

export const space = (n: number) => n * 4;

export const font = {
  h1: 24,
  h2: 18,
  body: 15,
  small: 13,
  tiny: 11,
};

export type Theme = typeof colors;
