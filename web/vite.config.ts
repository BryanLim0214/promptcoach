import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5183,
    proxy: {
      "/api": "http://127.0.0.1:8823",
    },
  },
  build: {
    outDir: "dist",
    // Fonts are vendored via @fontsource so the build works with no network and
    // the committee is not depending on a CDN staying up.
    assetsInlineLimit: 0,
  },
});
