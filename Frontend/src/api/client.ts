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

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    credentials: "include",
    headers: finalHeaders,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

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
  // Refresh CSRF after login state changes.
  await getCsrfToken();
  return user;
}

export async function login(payload: LoginPayload): Promise<User> {
  invalidateCsrfToken();
  const user = await request<User>("/auth/login/", {
    method: "POST",
    body: payload,
  });
  await getCsrfToken();
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
  partial: Partial<Pick<User, "name" | "country_code" | "phone" | "preferred_interval_miles" | "default_load_lb" | "theme">>,
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
