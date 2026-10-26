/**
 * Dirmile API client.
 *
 * Handles:
 *  - Same-origin session cookies (credentials: "include")
 *  - CSRF token fetching and attachment for unsafe methods
 *  - JSON serialisation / deserialisation
 *  - Typed error extraction
 *
 * The base URL defaults to "/api" which works in both:
 *  - Development (Vite proxy forwards /api → Django)
 *  - Production (Django serves the SPA and the API on the same origin)
 */

import type {
  ApiError,
  CsrfResponse,
  LoginPayload,
  Place,
  RegisterPayload,
  TripPlanCreatePayload,
  TripPlanDetail,
  TripPlanListItem,
  User,
} from "../types/api";

const API_BASE = "/api";

let cachedCsrfToken: string | null = null;

// ── CSRF ─────────────────────────────────────────────────────────────

async function getCsrfToken(): Promise<string | null> {
  if (cachedCsrfToken) {
    return cachedCsrfToken;
  }
  try {
    const res = await fetch(`${API_BASE}/auth/csrf/`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    const data: CsrfResponse = await res.json();
    cachedCsrfToken = data.csrf_token ?? null;
    return cachedCsrfToken;
  } catch {
    return null;
  }
}

export function invalidateCsrfToken(): void {
  cachedCsrfToken = null;
}

// ── Core request helper ──────────────────────────────────────────────

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
}

class ApiRequestError extends Error {
  readonly status: number;
  readonly data: ApiError;

  constructor(status: number, data: ApiError) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data);
    super(`API error ${status}: ${detail}`);
    this.name = "ApiRequestError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {} } = options;

  const isUnsafe = method !== "GET";

  const send = async (): Promise<Response> => {
    const finalHeaders: Record<string, string> = {
      Accept: "application/json",
      ...headers,
    };

    if (body !== undefined) {
      finalHeaders["Content-Type"] = "application/json";
    }

    if (isUnsafe) {
      const csrf = await getCsrfToken();
      if (csrf) {
        finalHeaders["X-CSRFToken"] = csrf;
      }
    }

    return fetch(`${API_BASE}${path}`, {
      method,
      credentials: "include",
      headers: finalHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await send();

  // Transparent single retry when Django rejects the token — e.g. it
  // rotated the CSRF secret on login and our cached header still belongs
  // to the previous cookie. Drop the cache, fetch a token paired with the
  // CURRENT cookie, and replay the request exactly once (never loops).
  if (isUnsafe && res.status === 403) {
    const probe: unknown = await res.clone().json().catch(() => null);
    const detail =
      probe !== null && typeof probe === "object" && "detail" in probe
        ? (probe as ApiError).detail
        : undefined;
    if (typeof detail === "string" && detail.includes("CSRF")) {
      invalidateCsrfToken();
      res = await send();
    }
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  let data: unknown;
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    data = await res.json();
  } else {
    data = { detail: await res.text() };
  }

  if (!res.ok) {
    throw new ApiRequestError(res.status, data as ApiError);
  }

  return data as T;
}

// ── Auth endpoints ───────────────────────────────────────────────────

export async function register(payload: RegisterPayload): Promise<User> {
  invalidateCsrfToken();
  const user = await request<User>("/auth/register/", {
    method: "POST",
    body: payload,
  });
  // Register authenticates the new user → same rotation as login.
  // Invalidate AFTER, never rely on a cached re-read.
  invalidateCsrfToken();
  return user;
}

export async function login(payload: LoginPayload): Promise<User> {
  invalidateCsrfToken();
  const user = await request<User>("/auth/login/", {
    method: "POST",
    body: payload,
  });
  // Django rotates the CSRF secret inside login(). The token cached during
  // the call above belongs to the OLD cookie — drop it so the next unsafe
  // request fetches a token paired with the NEW cookie. (A getCsrfToken()
  // here would be a cache-hit no-op: that was the original bug.)
  invalidateCsrfToken();
  return user;
}

export async function logout(): Promise<void> {
  await request<void>("/auth/logout/", { method: "POST" });
  invalidateCsrfToken();
}

export async function getCurrentUser(): Promise<User> {
  return request<User>("/auth/me/");
}

export async function updateSettings(
  partial: Partial<
    Pick<
      User,
      | "name"
      | "country_code"
      | "phone"
      | "preferred_interval_miles"
      | "default_load_lb"
      | "theme"
      | "heatmap_metric"
      | "map_style"
    >
  >,
): Promise<User> {
  return request<User>("/account/settings/", {
    method: "PATCH",
    body: partial,
  });
}

export async function deleteAccount(
  password: string,
  confirmation: string,
): Promise<void> {
  await request<void>("/account/", {
    method: "DELETE",
    body: { password, confirmation },
  });
  invalidateCsrfToken();
}

// ── Plan endpoints ───────────────────────────────────────────────────

export async function createTripPlan(
  payload: TripPlanCreatePayload,
): Promise<TripPlanDetail> {
  return request<TripPlanDetail>("/plans/", {
    method: "POST",
    body: payload,
  });
}

export async function listTripPlans(): Promise<TripPlanListItem[]> {
  return request<TripPlanListItem[]>("/plans/");
}

export async function getTripPlan(planId: string): Promise<TripPlanDetail> {
  return request<TripPlanDetail>(`/plans/${planId}/`);
}

// ── Health ───────────────────────────────────────────────────────────

export async function healthCheck(): Promise<{ status: string; service: string; time: string }> {
  return request("/health/");
}

export { ApiRequestError };

// ── Places (autocomplete) ────────────────────────────────────────────

/**
 * Best-effort place search backing the Origin/Destination comboboxes.
 * Returns an empty array on ANY failure (offline, 401, upstream 502):
 * the dropdown simply hides and the user can still type free text,
 * which the backend geocodes on submit anyway. GET needs no CSRF.
 */
export async function searchPlaces(query: string, count = 5): Promise<Place[]> {
  const q = query.trim();
  if (q.length < 2) return [];

  const params = new URLSearchParams({ q, count: String(count) });
  try {
    const res = await fetch(`${API_BASE}/places/?${params.toString()}`, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return [];
    const data: unknown = await res.json();
    return Array.isArray(data) ? (data as Place[]) : [];
  } catch {
    return [];
  }
}
