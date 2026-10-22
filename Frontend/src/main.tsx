import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./index.css";

// ── Service Worker Registration ──────────────────────────────────────
// registerType: "autoUpdate" in vite.config.ts means the SW
// automatically installs, activates, claims clients, and reloads
// the page when a new version is detected.
// No user prompt. No DevTools. No manual clearing.
registerSW({
  immediate: true,
  onOfflineReady() {
    console.info("[PWA] Dirmile is ready to work offline.");
  },
  onRegisterError(error) {
    console.warn("[PWA] Service worker registration failed:", error);
  },
});

// ── Install Prompt Handling ──────────────────────────────────────────
let deferredInstallPrompt: Event | null = null;

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  window.dispatchEvent(new CustomEvent("dirmile:installable"));
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  console.info("[PWA] Dirmile was installed successfully.");
});

(window as unknown as Record<string, unknown>).__dirmilePromptInstall =
  async function promptInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
    if (!deferredInstallPrompt) {
      return "unavailable";
    }
    const evt = deferredInstallPrompt as Event & {
      prompt: () => Promise<void>;
      userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
    };
    await evt.prompt();
    const { outcome } = await evt.userChoice;
    deferredInstallPrompt = null;
    return outcome;
  };

// ── Mount React App ──────────────────────────────────────────────────
const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error('Root element "#root" not found in index.html.');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
