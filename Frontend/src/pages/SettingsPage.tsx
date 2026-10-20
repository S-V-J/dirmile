/**
 * Settings page (authenticated).
 *
 * Phase 12 creates only the shell.
 * Later phases will add:
 *  - Default checkpoint interval
 *  - Default load weight
 *  - Theme preference
 *  - Heatmap metric
 *  - Map style
 */
export function SettingsPage() {
  return (
    <section className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-bold text-white">Settings</h1>
      <p className="mt-2 text-brand-400">
        Preference controls will be added in a later phase.
      </p>

      <div className="mt-8 space-y-4">
        {[
          "Default checkpoint interval (10 / 25 / 50 miles)",
          "Default load weight (lb)",
          "Theme (light / dark / system)",
          "Heatmap metric (combined risk / wind / rain / snow)",
          "Map style preference",
        ].map((label) => (
          <div
            key={label}
            className="rounded-lg border border-brand-800/50 bg-brand-900/30 px-4 py-3 text-sm text-brand-500"
          >
            {label} — coming soon
          </div>
        ))}
      </div>
    </section>
  );
}
