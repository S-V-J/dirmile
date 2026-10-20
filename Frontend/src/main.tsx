import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import App from "./App";
import "./index.css";

// ── Service Worker Registration ──────────────────────────────────────
// vite-plugin-pwa exposes a virtual module that handles registration.
// registerType: "prompt" means we control when updates are applied.
const updateSW = registerSW({
  onNeedRefresh() {
    // Show a lightweight toast-like notification
    if (
      typeof window !== "undefined" &&
      confirm("A new version of Dirmile is available. Reload to update?")
    ) {
      void updateSW(true);
    }
  },
  onOfflineReady() {
    console.info("[PWA] Dirmile is ready to work offline.");
  },
  onRegisteredSW(swUrl, registration) {
    console.info("[PWA] Service worker registered:", swUrl);
    // Optional: check for updates every 60 minutes while the tab is open
    if (registration) {
      setInterval(
        () => {
          void registration.update();
        },
        60 * 60 * 1000,
      );
    }
  },
  onRegisterError(error) {
    console.warn("[PWA] Service worker registration failed:", error);
  },
});

// ── Install Prompt Handling ──────────────────────────────────────────
// Capture the beforeinstallprompt event so we can trigger it from UI.
let deferredInstallPrompt: Event | null = null;

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  // Dispatch a custom event so React components can react
  window.dispatchEvent(new CustomEvent("dirmile:installable"));
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  console.info("[PWA] Dirmile was installed successfully.");
});

// Expose a helper for components to trigger the install dialog
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
