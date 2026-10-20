import { useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";

import { RISK_HEX, routeLineColor } from "../lib/riskColors";
import type { Checkpoint, RiskLevel, RouteOption } from "../types/api";
import { RISK_LABELS } from "../types/api";

type LatLngTuple = [number, number];

interface TripMapProps {
  routes: RouteOption[];
  selectedRouteId: string | null;
  highlightCheckpointId?: string | null;
}

/**
 * GeoJSON coordinates are [lng, lat]; Leaflet wants [lat, lng].
 * Written defensively so it compiles regardless of how narrowly
 * `geometry` is typed in src/types/api.ts.
 */
function geometryToLatLngs(route: RouteOption): LatLngTuple[] {
  const geometry = route.geometry as { coordinates?: unknown } | null | undefined;
  const coords = geometry?.coordinates;
  if (!Array.isArray(coords)) return [];
  const points: LatLngTuple[] = [];
  for (const c of coords) {
    if (
      Array.isArray(c) &&
      c.length >= 2 &&
      typeof c[0] === "number" &&
      typeof c[1] === "number"
    ) {
      points.push([c[1], c[0]]);
    }
  }
  return points;
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

/**
 * Fits the map to all route geometry whenever the plan changes.
 */
function FitBounds({ routes }: { routes: RouteOption[] }) {
  const map = useMap();

  const bounds = useMemo(() => {
    const pts = routes.flatMap(geometryToLatLngs);
    if (pts.length === 0) return null;
    let minLat = Infinity;
    let minLng = Infinity;
    let maxLat = -Infinity;
    let maxLng = -Infinity;
    for (const [lat, lng] of pts) {
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    }
    return [
      [minLat, minLng],
      [maxLat, maxLng],
    ] as [LatLngTuple, LatLngTuple];
  }, [routes]);

  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [map, bounds]);

  return null;
}

/**
 * Pans to a highlighted checkpoint (e.g. clicked in the list).
 */
function FlyToCheckpoint({ checkpoint }: { checkpoint: Checkpoint | null }) {
  const map = useMap();
  useEffect(() => {
    if (checkpoint) {
      map.panTo([checkpoint.lat, checkpoint.lng]);
    }
  }, [map, checkpoint]);
  return null;
}

const LEGEND_ITEMS: readonly RiskLevel[] = [
  "LOW",
  "MODERATE",
  "HIGH",
  "SEVERE",
  "NO_TRAVEL",
];

export function TripMap({
  routes,
  selectedRouteId,
  highlightCheckpointId,
}: TripMapProps) {
  const [showAllRoutes, setShowAllRoutes] = useState(true);
  const [showCheckpoints, setShowCheckpoints] = useState(true);

  const selected =
    routes.find((r) => r.id === selectedRouteId) ?? null;

  const highlightedCheckpoint = useMemo(() => {
    if (!highlightCheckpointId || !selected) return null;
    return selected.checkpoints.find((cp) => cp.id === highlightCheckpointId) ?? null;
  }, [highlightCheckpointId, selected]);

  const center = useMemo<LatLngTuple>(() => {
    const pts = routes.flatMap(geometryToLatLngs);
    if (pts.length > 0) {
      const lat = pts.reduce((s, p) => s + p[0], 0) / pts.length;
      const lng = pts.reduce((s, p) => s + p[1], 0) / pts.length;
      return [lat, lng];
    }
    // Default view: continental US, used only before a plan exists.
    return [39.5, -86.0];
  }, [routes]);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-brand-800/50 bg-brand-900">
      <MapContainer
        center={center}
        zoom={6}
        preferCanvas
        style={{ height: "100%", width: "100%" }}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <FitBounds routes={routes} />
        <FlyToCheckpoint checkpoint={highlightedCheckpoint} />

        {/* Route polylines */}
        {routes.map((route, index) => {
          const points = geometryToLatLngs(route);
          if (points.length < 2) return null;
          const isSelected = route.id === selectedRouteId;
          if (!showAllRoutes && !isSelected && !route.is_recommended) {
            return null;
          }
          return (
            <Polyline
              key={route.id}
              positions={points}
              pathOptions={{
                color: routeLineColor(index, route.is_recommended),
                weight: isSelected ? 5 : 3,
                opacity: isSelected ? 0.95 : 0.55,
              }}
            />
          );
        })}

        {/* Checkpoints for the selected route */}
        {showCheckpoints &&
          selected?.checkpoints.map((cp) => {
            const isHighlighted = cp.id === highlightCheckpointId;
            return (
              <CircleMarker
                key={cp.id}
                center={[cp.lat, cp.lng]}
                radius={isHighlighted ? 9 : 6}
                pathOptions={{
                  color: isHighlighted ? "#ffffff" : "#0b1220",
                  weight: isHighlighted ? 3 : 1.5,
                  fillColor: RISK_HEX[cp.overall_risk] ?? RISK_HEX.LOW,
                  fillOpacity: 0.9,
                }}
              >
                <Popup>
                  <div className="space-y-1 text-xs">
                    <p className="font-semibold">
                      {selected.label} · Mile {cp.mile_marker.toFixed(0)}
                    </p>
                    <p>ETA: {formatEta(cp.eta_utc)}</p>
                    <p>Wind: {cp.wind_mph.toFixed(1)} mph</p>
                    <p>Rain: {cp.rain_in_hr.toFixed(2)} in/hr</p>
                    <p>Snow: {cp.snow_in_hr.toFixed(2)} in/hr</p>
                    <p className="font-semibold" style={{ color: RISK_HEX[cp.overall_risk] }}>
                      Risk: {RISK_LABELS[cp.overall_risk]}
                    </p>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
      </MapContainer>

      {/* ── Layer toggles (top-left) ─────────────────────────── */}
      <div className="absolute left-3 top-3 z-[1000] space-y-1 rounded-lg border border-brand-800/60 bg-brand-950/85 p-3 text-xs text-brand-200 shadow-lg backdrop-blur">
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={showAllRoutes}
            onChange={(e) => setShowAllRoutes(e.target.checked)}
            className="h-3.5 w-3.5 accent-brand-400"
          />
          Show all routes
        </label>
        <label className="flex cursor-pointer items-center gap-2">
          <input
            type="checkbox"
            checked={showCheckpoints}
            onChange={(e) => setShowCheckpoints(e.target.checked)}
            className="h-3.5 w-3.5 accent-brand-400"
          />
          Show checkpoints
        </label>
      </div>

      {/* ── Risk legend (bottom-left) ────────────────────────── */}
      <div className="absolute bottom-3 left-3 z-[1000] rounded-lg border border-brand-800/60 bg-brand-950/85 p-3 text-xs shadow-lg backdrop-blur">
        <p className="mb-1.5 font-semibold uppercase tracking-wide text-brand-400">
          Risk
        </p>
        <ul className="space-y-1">
          {LEGEND_ITEMS.map((level) => (
            <li key={level} className="flex items-center gap-2 text-brand-200">
              <span
                className="inline-block h-3 w-3 rounded-full border border-black/40"
                style={{ backgroundColor: RISK_HEX[level] }}
                aria-hidden="true"
              />
              {RISK_LABELS[level]}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
