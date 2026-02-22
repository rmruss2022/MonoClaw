import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/auth": "http://api:8000",
      "/me": "http://api:8000",
      "/onboarding": "http://api:8000",
      "/match": "http://api:8000",
      "/settlements": "http://api:8000",
      "/integrations": "http://api:8000"
    }
  },
  test: {
    environment: "jsdom",
    globals: true
  }
});
