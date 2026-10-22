import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

function getBackendPort(): string {
  if (process.env.DIRMILE_BACKEND_PORT) {
    return process.env.DIRMILE_BACKEND_PORT;
  }
  const runtimePortFile = resolve(__dirname, "..", "runtime", "dirmile.port");
  if (existsSync(runtimePortFile)) {
    try {
      const port = readFileSync(runtimePortFile, "utf-8").trim();
      if (port && /^\d+$/.test(port)) {
        return port;
      }
    } catch {
      // ignore
    }
  }
  const legacyPortFile = resolve(__dirname, "..", "runtime", "dev-port");
  if (existsSync(legacyPortFile)) {
    try {
      const port = readFileSync(legacyPortFile, "utf-8").trim();
      if (port && /^\d+$/.test(port)) {
        return port;
      }
    } catch {
      // ignore
    }
  }
  return "8000";
}

const backendPort = getBackendPort();

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // autoUpdate: SW installs and activates silently,
      // then reloads the page. No user prompt, no DevTools.
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "offline.html"],
      manifest: {
        name: "Dirmile",
        short_name: "Dirmile",
        description:
          "Weather-aware truck routing for safer route decisions.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "any",
        background_color: "#0f172a",
        theme_color: "#0f172a",
        categories: ["navigation", "travel", "utilities"],
        icons: [
          {
            src: "/icons/icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icons/icon-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "/icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
          {
            src: "/icons/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        navigateFallback: "/offline.html",
        navigateFallbackDenylist: [/^\/api/],
        // Ensure SW itself is never cached by the browser
        // (Django also sends no-cache headers for sw.js)
        cleanupOutdatedCaches: true,
        skipWaiting: true,
        clientsClaim: true,
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/tile\.openstreetmap\.org\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "osm-tiles",
              expiration: {
                maxEntries: 200,
                maxAgeSeconds: 60 * 60 * 24 * 7,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /^\/api\/.*/i,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              networkTimeoutSeconds: 10,
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60 * 24,
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
        ],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  server: {
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${backendPort}`,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
