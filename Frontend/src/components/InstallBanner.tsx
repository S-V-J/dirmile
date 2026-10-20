import { useCallback, useEffect, useState } from "react";

/**
 * A subtle banner that appears when the browser fires
 * `beforeinstallprompt`, offering a one-click install.
 *
 * The actual prompt is triggered via the global helper
 * exposed in main.tsx (__dirmilePromptInstall).
 */
export function InstallBanner() {
  const [visible, setVisible] = useState(false);
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem("dirmile-install-dismissed") === "1",
  );

  useEffect(() => {
    const handler = () => {
      if (!dismissed) {
        setVisible(true);
      }
    };
    window.addEventListener("dirmile:installable", handler);

    // Also check if already installable on mount
    // (the event may have fired before this component mounted)
    const promptFn = (window as unknown as Record<string, unknown>)
      .__dirmilePromptInstall;
    if (promptFn && !dismissed) {
      setVisible(true);
    }

    return () => {
      window.removeEventListener("dirmile:installable", handler);
    };
  }, [dismissed]);

  const handleInstall = useCallback(async () => {
    const promptFn = (
      window as unknown as Record<string, (() => Promise<string>) | undefined>
    ).__dirmilePromptInstall;

    if (!promptFn) {
      setVisible(false);
      return;
    }

    const outcome = await promptFn();
    if (outcome === "accepted") {
      setVisible(false);
    }
  }, []);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    setDismissed(true);
    sessionStorage.setItem("dirmile-install-dismissed", "1");
  }, []);

  if (!visible || dismissed) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-4 left-1/2 z-50 flex w-[calc(100%-2rem)] max-w-md -translate-x-1/2 items-center gap-3 rounded-xl border border-brand-700 bg-brand-900/95 px-5 py-3 shadow-2xl backdrop-blur-sm"
    >
      <img
        src="/icons/icon-192.png"
        alt=""
        className="h-10 w-10 rounded-lg"
        aria-hidden="true"
      />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white">Install Dirmile</p>
        <p className="text-xs text-brand-400 truncate">
          Add to your home screen for quick access
        </p>
      </div>
      <button
        type="button"
        onClick={() => void handleInstall()}
        className="shrink-0 rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-400 transition-colors"
      >
        Install
      </button>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss install banner"
        className="shrink-0 rounded-lg px-2 py-2 text-brand-500 hover:text-white hover:bg-brand-800 transition-colors"
      >
        ✕
      </button>
    </div>
  );
}
