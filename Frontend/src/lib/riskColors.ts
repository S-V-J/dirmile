import type { RiskLevel } from "../types/api";

/**
 * Hex colors for each risk level, used by map markers and polylines.
 * These match the PRD specification.
 */
export const RISK_HEX: Record<RiskLevel, string> = {
  LOW: "#22c55e",
  MODERATE: "#eab308",
  HIGH: "#f97316",
  SEVERE: "#dc2626",
  NO_TRAVEL: "#7f1d1d",
};

/**
 * Route line colors — neutral to avoid confusion with risk colors.
 */
export const ROUTE_LINE_COLORS = [
  "#3b82f6", // blue-500   (Route A / recommended)
  "#8b5cf6", // violet-500 (Route B)
  "#06b6d4", // cyan-500   (Route C)
] as const;

/**
 * Returns the line color for a route by its index.
 * Recommended route always gets the first (blue) color.
 *
 * Note: with `noUncheckedIndexedAccess` enabled in tsconfig,
 * indexing a tuple with a computed number yields `string | undefined`.
 * The fallback uses a literal index (`[1]`) which is always defined,
 * so the overall expression narrows to `string`.
 */
export function routeLineColor(index: number, isRecommended: boolean): string {
  if (isRecommended) return ROUTE_LINE_COLORS[0];
  const adjustedIndex = ((index - 1) % (ROUTE_LINE_COLORS.length - 1)) + 1;
  return ROUTE_LINE_COLORS[adjustedIndex] ?? ROUTE_LINE_COLORS[1];
}
