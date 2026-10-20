/**
 * Main web application page (authenticated).
 *
 * Phase 12 creates only the shell.
 * Phase 13 will add the trip input form.
 * Phase 14 will add the map and route visualisation.
 * Phase 15 will add the heatmap slider.
 */
export function WebAppPage() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-12">
      <h1 className="text-2xl font-bold text-white">Web App</h1>
      <p className="mt-2 text-brand-400">
        Trip planning interface will appear here.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[380px_1fr]">
        {/* Left panel placeholder */}
        <div className="rounded-xl border border-brand-800/50 bg-brand-900/30 p-6">
          <h2 className="text-lg font-semibold text-brand-200">
            Trip Inputs
          </h2>
          <p className="mt-2 text-sm text-brand-500">
            Origin, destination, departure, load weight, and checkpoint
            interval controls will be added in Phase 13.
          </p>
        </div>

        {/* Right panel placeholder */}
        <div className="flex min-h-[400px] items-center justify-center rounded-xl border border-brand-800/50 bg-brand-900/30">
          <p className="text-sm text-brand-500">
            Map, routes, checkpoints, and heatmap will be added in
            Phases 14–15.
          </p>
        </div>
      </div>
    </section>
  );
}
