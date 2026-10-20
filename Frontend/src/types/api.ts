/**
 * TypeScript types mirroring the Dirmile backend API contracts.
 *
 * Backend source of truth:
 *   Backend/plans/serializers.py
 *   Backend/accounts/serializers.py
 *   Backend/core/constants.py
 */

// ── Risk levels ──────────────────────────────────────────────────────

export type RiskLevel =
  | "LOW"
  | "MODERATE"
  | "HIGH"
  | "SEVERE"
  | "NO_TRAVEL";

export const RISK_LEVELS: readonly RiskLevel[] = [
  "LOW",
  "MODERATE",
  "HIGH",
  "SEVERE",
  "NO_TRAVEL",
] as const;

export const RISK_COLORS: Record<RiskLevel, string> = {
  LOW: "var(--color-risk-low)",
  MODERATE: "var(--color-risk-moderate)",
  HIGH: "var(--color-risk-high)",
  SEVERE: "var(--color-risk-severe)",
  NO_TRAVEL: "var(--color-risk-no-travel)",
};

export const RISK_LABELS: Record<RiskLevel, string> = {
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  SEVERE: "Severe",
  NO_TRAVEL: "No Travel",
};

// ── Auth / User ──────────────────────────────────────────────────────

export interface User {
  id: number;
  name: string;
  email: string;
  username: string;
  country_code: string;
  phone: string;
  phone_verified: boolean;
  otp_enabled: boolean;
  preferred_interval_miles: 10 | 25 | 50;
  default_load_lb: number;
  theme: "light" | "dark" | "system";
  is_staff: boolean;
  is_active: boolean;
  date_joined: string;
  created_at: string;
  updated_at: string;
}

export interface RegisterPayload {
  name: string;
  email: string;
  username: string;
  password: string;
  confirm_password: string;
  country_code?: string;
  phone?: string;
  otp_enabled?: boolean;
}

export interface LoginPayload {
  identifier: string;
  password: string;
}

export interface CsrfResponse {
  csrf_token: string;
}

// ── Trip Plan ────────────────────────────────────────────────────────

export interface TripPlanCreatePayload {
  origin: string;
  destination: string;
  departure: string;
  load_lb: number;
  interval_miles: 10 | 25 | 50;
}

export interface Checkpoint {
  id: string;
  mile_marker: number;
  lat: number;
  lng: number;
  eta_utc: string;
  wind_mph: number;
  wind_gust_mph: number | null;
  rain_in_hr: number;
  snow_in_hr: number;
  temperature_f: number | null;
  weather_code: number | null;
  wind_risk: RiskLevel;
  rain_risk: RiskLevel;
  snow_risk: RiskLevel;
  overall_risk: RiskLevel;
  load_override_applied: boolean;
}

export interface RouteOption {
  id: string;
  label: string;
  route_index: number;
  distance_miles: number;
  duration_seconds: number;
  average_risk_score: number;
  low_miles: number;
  moderate_miles: number;
  high_miles: number;
  severe_miles: number;
  no_travel_miles: number;
  is_recommended: boolean;
  recommendation_reasons: string[];
  geometry: GeoJSON.LineString;
  checkpoints: Checkpoint[];
}

export interface TripPlanDetail {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  error_message: string;
  origin_name: string;
  origin_lat: number;
  origin_lng: number;
  origin_timezone: string;
  destination_name: string;
  destination_lat: number;
  destination_lng: number;
  destination_timezone: string;
  departure: string;
  load_lb: number;
  interval_miles: 10 | 25 | 50;
  created_at: string;
  updated_at: string;
  routes: RouteOption[];
}

export interface TripPlanListItem {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
  origin_name: string;
  destination_name: string;
  departure: string;
  load_lb: number;
  interval_miles: 10 | 25 | 50;
  route_count: number;
  recommended_label: string | null;
  created_at: string;
}

// ── GeoJSON (minimal subset used by Dirmile) ─────────────────────────

export namespace GeoJSON {
  export interface LineString {
    type: "LineString";
    coordinates: [number, number][];
  }
}

// ── API error shape ──────────────────────────────────────────────────

export interface ApiError {
  detail?: string;
  [field: string]: unknown;
}
