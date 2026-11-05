import { defineConfig } from "vite";

// HighFi controller app. Vanilla TS — no framework plugins needed.
// During dev the app defaults to the built-in emulator, so no proxy is
// required to be usable with zero hardware. If you point it at a real
// device you can set VITE_DEVICE_HOST and the client will use ws://<host>/ws.
export default defineConfig({
  server: {
    host: true,
    port: 5173,
  },
});
