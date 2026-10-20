import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

import type { HeatmapPoint } from "../types/api";

export type HeatmapMetric = "risk" | "wind" | "rain" | "snow";

interface HeatmapLayerProps {
  points: HeatmapPoint[];
  hour: number; // 0–48
  metric: HeatmapMetric;
  visible: boolean;
}

/**
 * Normalizes a raw weather value to 0–1 intensity for the heat layer.
 */
function normalize(metric: HeatmapMetric, value: number): number {
  switch (metric) {
    case "risk":
      // Risk scores are 0–4
      return Math.min(1, Math.max(0, value / 4));
    case "wind":
      // Wind in mph, cap visualization at 80 mph
      return Math.min(1, Math.max(0, value / 80));
    case "rain":
      // Rain in in/hr, cap at 2.0
      return Math.min(1, Math.max(0, value / 2.0));
    case "snow":
      // Snow in in/hr, cap at 4.0
      return Math.min(1, Math.max(0, value / 4.0));
    default:
      return 0;
  }
}

/**
 * Builds [lat, lng, intensity] tuples from heatmap points for a given hour.
 */
function buildHeatData(
  points: HeatmapPoint[],
  hour: number,
  metric: HeatmapMetric
): Array<[number, number, number]> {
  const clampedHour = Math.min(47, Math.max(0, Math.floor(hour)));
  const result: Array<[number, number, number]> = [];

  for (const pt of points) {
    let raw = 0;
    switch (metric) {
      case "risk":
        raw = pt.hourly_risk?.[clampedHour] ?? 0;
        break;
      case "wind":
        raw = pt.hourly_wind?.[clampedHour] ?? 0;
        break;
      case "rain":
        raw = pt.hourly_rain?.[clampedHour] ?? 0;
        break;
      case "snow":
        raw = pt.hourly_snow?.[clampedHour] ?? 0;
        break;
    }
    const intensity = normalize(metric, raw);
    if (intensity > 0.01) {
      result.push([pt.lat, pt.lng, intensity]);
    }
  }

  return result;
}

/**
 * Imperative Leaflet.heat layer managed via React lifecycle.
 * Creates the layer once, then updates latlngs on prop changes.
 */
export function HeatmapLayer({
  points,
  hour,
  metric,
  visible,
}: HeatmapLayerProps) {
  const map = useMap();
  const layerRef = useRef<L.HeatLayer | null>(null);

  // Create layer on mount
  useEffect(() => {
    const layer = L.heatLayer([], {
      radius: 25,
      blur: 20,
      maxZoom: 10,
      minOpacity: 0.05,
      gradient: {
        0.0: "#22c55e",
        0.25: "#eab308",
        0.5: "#f97316",
        0.75: "#dc2626",
        1.0: "#7f1d1d",
      },
    });
    layerRef.current = layer;

    if (visible) {
      layer.addTo(map);
    }

    return () => {
      layer.removeFrom(map);
      layerRef.current = null;
    };
  }, [map]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update data when points, hour, or metric change
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    const data = buildHeatData(points, hour, metric);
    layer.setLatLngs(data);
  }, [points, hour, metric]);

  // Toggle visibility
  useEffect(() => {
    const layer = layerRef.current;
    if (!layer) return;

    if (visible) {
      if (!map.hasLayer(layer)) {
        layer.addTo(map);
      }
    } else {
      if (map.hasLayer(layer)) {
        layer.removeFrom(map);
      }
    }
  }, [visible, map]);

  return null;
}
