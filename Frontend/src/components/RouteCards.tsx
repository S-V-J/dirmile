import type { RouteOption, RiskLevel } from "../types/api";
import { RISK_COLORS, RISK_LABELS } from "../types/api";

interface RouteCardsProps {
  routes: RouteOption[];
  selectedRouteId: string | null;
  onSelectRoute: (route: RouteOption) => void;
}

function riskBadgeColor(risk: RiskLevel): string {
  return RISK_COLORS[risk] ?? "var(--color-risk-low)";
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatEta(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function RouteCards({
  routes,
  selectedRouteId,
  onSelectRoute,
}: RouteCardsProps) {
  if (routes.length === 0) {
    return (
      <p className="text-sm text-brand-500">
        No routes generated yet. Fill in the trip form above.
      </p>
    );
  }

  return (
    <div className="space-y-3" role="list" aria-label="Route options">
      {routes.map((route) => {
        const isSelected = route.id === selectedRouteId;
        const worstRisk: RiskLevel =
          route.no_travel_miles > 0
            ? "NO_TRAVEL"
            : route.severe_miles > 0
              ? "SEVERE"
              : route.high_miles > 0
                ? "HIGH"
                : route.moderate_miles > 0
                  ? "MODERATE"
                  : "LOW";

        return (
          <button
            key={route.id}
            type="button"
            role="listitem"
            onClick={() => onSelectRoute(route)}
            className={`w-full rounded-xl border p-4 text-left transition-colors ${
              isSelected
                ? "border-brand-400 bg-brand-800/60 ring-1 ring-brand-400"
                : "border-brand-800/50 bg-brand-900/30 hover:border-brand-600"
            }`}
            aria-pressed={isSelected}
          >
            {/* Header row */}
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold text-white">
                {route.label}
              </span>
              {route.is_recommended && (
                <span className="rounded-full bg-green-900/60 px-2 py-0.5 text-xs font-semibold text-green-300 border border-green-700">
                  ★ Recommended
                </span>
              )}
            </div>

            {/* Metrics grid */}
            <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <Metric label="Distance" value={`${route.distance_miles.toFixed(1)} mi`} />
              <Metric label="Duration" value={formatDuration(route.duration_seconds)} />
              <Metric label="Avg Risk" value={route.average_risk_score.toFixed(2)} />
              <Metric
                label="Worst"
                value={RISK_LABELS[worstRisk]}
                valueColor={riskBadgeColor(worstRisk)}
              />
            </div>

            {/* Risk breakdown */}
            <div className="mt-2 flex flex-wrap gap-1.5">
              {route.no_travel_miles > 0 && (
                <RiskChip level="NO_TRAVEL" miles={route.no_travel_miles} />
              )}
              {route.severe_miles > 0 && (
                <RiskChip level="SEVERE" miles={route.severe_miles} />
              )}
              {route.high_miles > 0 && (
                <RiskChip level="HIGH" miles={route.high_miles} />
              )}
              {route.moderate_miles > 0 && (
                <RiskChip level="MODERATE" miles={route.moderate_miles} />
              )}
              {route.low_miles > 0 && route.no_travel_miles === 0 && route.severe_miles === 0 && route.high_miles === 0 && route.moderate_miles === 0 && (
                <RiskChip level="LOW" miles={route.low_miles} />
              )}
            </div>

            {/* Recommendation reasons */}
            {route.is_recommended && route.recommendation_reasons.length > 0 && (
              <ul className="mt-2 space-y-0.5 text-xs text-brand-400">
                {route.recommendation_reasons.slice(0, 3).map((reason, i) => (
                  <li key={i}>• {reason}</li>
                ))}
              </ul>
            )}

            {/* Checkpoint count */}
            <p className="mt-2 text-xs text-brand-500">
              {route.checkpoints.length} checkpoints · Arrives{" "}
              {route.checkpoints.length > 0
                ? formatEta(route.checkpoints[route.checkpoints.length - 1]!.eta_utc)
                : "—"}
            </p>
          </button>
        );
      })}
    </div>
  );
}

function Metric({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div>
      <span className="text-brand-500">{label}:</span>{" "}
      <span className="font-medium" style={valueColor ? { color: valueColor } : undefined}>
        {value}
      </span>
    </div>
  );
}

function RiskChip({ level, miles }: { level: RiskLevel; miles: number }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: `${RISK_COLORS[level]}22`,
        color: RISK_COLORS[level],
        border: `1px solid ${RISK_COLORS[level]}44`,
      }}
    >
      {RISK_LABELS[level]}: {miles.toFixed(0)} mi
    </span>
  );
}
