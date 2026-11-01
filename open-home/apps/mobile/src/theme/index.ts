/**
 * openhome design tokens — ported 1:1 from the web control surface
 * (apps/app/*.html :root variables) so the native app reads as the same product.
 */
export const colors = {
  bg: "#0e1014",
  bgElev: "#141821",
  panel: "#171a21",
  panelAlt: "#0f1216",
  line: "#272c37",
  text: "#e7ebf3",
  muted: "#8b93a7",
  accent: "#3ddc97",
  accentDim: "#1f7a56",
  accentWash: "rgba(61,220,151,0.10)",
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
