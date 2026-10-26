import { useCallback, useState } from "react";

import { useAuth } from "../auth/useAuth";
import { CheckpointList } from "../components/CheckpointList";
import { RouteCards } from "../components/RouteCards";
import { TripForm } from "../components/TripForm";
import { TripMap } from "../components/TripMap";
import type { Checkpoint, RouteOption, TripPlanDetail } from "../types/api";

/**
 * Main Web App page (authenticated).
 *
 * Layout:
 *   Desktop: left panel (form + route cards + checkpoint list) | right panel (map)
 *   Mobile:  stacked sections
 */
export function WebAppPage() {
  const { user } = useAuth();
  const [plan, setPlan] = useState<TripPlanDetail | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<RouteOption | null>(null);
  const [highlightedCheckpoint, setHighlightedCheckpoint] = useState<string | null>(null);

  const handlePlanCreated = useCallback((newPlan: TripPlanDetail) => {
    setPlan(newPlan);
    // Auto-select the recommended route.
    const recommended = newPlan.routes.find((r) => r.is_recommended);
    setSelectedRoute(recommended ?? newPlan.routes[0] ?? null);
    setHighlightedCheckpoint(null);
  }, []);

  const handleSelectRoute = useCallback((route: RouteOption) => {
    setSelectedRoute(route);
    setHighlightedCheckpoint(null);
  }, []);

  const handleCheckpointClick = useCallback((cp: Checkpoint) => {
    setHighlightedCheckpoint(cp.id);
  }, []);

  return (
    <section className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="text-xl font-bold text-white">Web App</h1>
      <p className="mt-1 text-sm text-brand-400">
        Plan a trip and compare weather-safe route options.
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[400px_1fr]">
        {/* ── Left Panel ─────────────────────────────────────── */}
        <div className="space-y-6">
          {/* Trip Form */}
          <div className="rounded-xl border border-brand-800/50 bg-brand-900/30 p-5">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-brand-400">
              Trip Inputs
            </h2>
            <TripForm
              onPlanCreated={handlePlanCreated}
              defaultLoadLb={user?.default_load_lb ?? 30000}
              defaultInterval={user?.preferred_interval_miles ?? 25}
            />
          </div>

          {/* Route Cards */}
          {plan && plan.routes.length > 0 && (
            <div className="rounded-xl border border-brand-800/50 bg-brand-900/30 p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-brand-400">
                Route Options ({plan.routes.length})
              </h2>
              <RouteCards
                routes={plan.routes}
                selectedRouteId={selectedRoute?.id ?? null}
                onSelectRoute={handleSelectRoute}
              />
            </div>
          )}

          {/* Checkpoint List */}
          {selectedRoute && selectedRoute.checkpoints.length > 0 && (
            <div className="rounded-xl border border-brand-800/50 bg-brand-900/30 p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-brand-400">
                Checkpoints — {selectedRoute.label}
              </h2>
              <CheckpointList
                checkpoints={selectedRoute.checkpoints}
                highlightId={highlightedCheckpoint}
                onCheckpointClick={handleCheckpointClick}
              />
            </div>
          )}
        </div>

        {/* ── Right Panel (Map) ──────────────────────────────── */}
        {/* Always mounted: empty basemap before a plan exists,
            routes/checkpoints/heatmap populate after generation.
            TripMap is empty-safe (center fallback + guarded layers). */}
        <div className="h-[720px] lg:h-[880px]">
          <TripMap
            routes={plan?.routes ?? []}
            selectedRouteId={selectedRoute?.id ?? null}
            highlightCheckpointId={highlightedCheckpoint}
            initialMetric={user?.heatmap_metric ?? "risk"}
            onCheckpointClick={handleCheckpointClick}
          />
        </div>
      </div>
    </section>
  );
}
