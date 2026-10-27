# Dirmile — weather-aware truck routing for safer route decisions

<p align="center">
  <strong>Pick the safest corridor, not just the shortest one.</strong><br>
  Enter origin, destination, departure time and load weight. Dirmile samples wind, rain and snow
  <em>at the moment the truck will actually be there</em>, grades every checkpoint against published
  risk thresholds, applies heavy-load crosswind overrides, ranks the route options, and draws the
  whole corridor on an interactive map with a 0–48 hour forecast heatmap.
</p>

<p align="center">
  <a href="https://github.com/S-V-J/dirmile/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/S-V-J/dirmile/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="168 tests" src="https://img.shields.io/badge/tests-168%20passing-22c55e">
  <img alt="Python 3.14" src="https://img.shields.io/badge/Python-3.14-3776ab?logo=python&logoColor=white">
  <img alt="Django 6.1" src="https://img.shields.io/badge/Django-6.1-092e20?logo=django&logoColor=white">
  <img alt="React 18 + TypeScript" src="https://img.shields.io/badge/React%2018-TypeScript%20strict-61dafb?logo=react&logoColor=black">
  <img alt="PWA installable" src="https://img.shields.io/badge/PWA-installable-5a0fc8?logo=pwa&logoColor=white">
  <img alt="MIT License" src="https://img.shields.io/badge/license-MIT-3b82f6">
  <img alt="Last commit" src="https://img.shields.io/github/last-commit/S-V-J/dirmile?color=blue">
  <a href="https://github.com/S-V-J/dirmile/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/S-V-J/dirmile?style=social"></a>
  <a href="https://github.com/sponsors/S-V-J"><img alt="Sponsor" src="https://img.shields.io/badge/Sponsor-S--V--J-ea4aaa?logo=githubsponsors&logoColor=white"></a>
</p>

**Keywords:** weather-aware routing · truck route planner · severe weather risk · crosswind load
override · OSRM alternative routes · Open-Meteo hourly forecast · Leaflet heatmap ·
Django REST Framework · React TypeScript PWA · offline-first map application

---

## Contents

- [What it does](#what-it-does) · [Quick start](#quick-start) · [Screenshots](#screenshots)
- [Features](#features) · [Architecture](#architecture) · [Tech stack](#tech-stack)
- [The `dirmile` CLI](#the-dirmile-cli) · [Configuration](#configuration) · [API reference](#api-reference)
- [Risk model](#risk-model) · [Route recommendation](#route-recommendation)
- [Testing and CI](#testing-and-ci) · [Deployment](#deployment) · [PWA and offline](#pwa-and-offline)
- [Guided tour](#guided-tour) · [Troubleshooting](#troubleshooting)
- [Limitations and honest notes](#limitations-and-honest-notes) · [Security](#security) · [Contributing](#contributing)
- [Credits and attribution](#credits-and-attribution) · [Disclaimer](#disclaimer) · [License](#license)
- [Author](#author) · [Sponsor](#sponsor)

---

## What it does

Long-haul drivers decide route safety from gut feel and a weather app built for commuters. Both
fail the same way: they describe the weather **now**, at a point you'll reach in six hours.

Dirmile models the trip instead of the map. It takes your departure time and gross vehicle weight,
walks each candidate route forward mile by mile, computes when you'll pass each checkpoint, and asks
the forecast model for conditions *at that instant, in that place*. Every checkpoint is graded
Low → Moderate → High → Severe → No Travel against fixed wind, rain and snow thresholds, then
adjusted for load: a 40,000 lb tractor-trailer faces crosswind forces an empty one doesn't, so the
same 38 mph gust that is "High" for a light rig is "Severe" for a heavy one.

Checkpoints roll up into **mileage per risk band** per route, and routes are ranked by a
deterministic key — fewest No-Travel miles, fewest Severe miles, fewest High miles, lowest average
risk, then shortest travel time — so the recommendation is explainable rather than a black-box score.
The winning route carries plain-English reasons ("No severe miles", "Arrives 22m earlier than Route
B", "Trades 1h 10m extra time for lower weather risk").

Everything renders on one Leaflet map: all route polylines, risk-coloured checkpoint markers with
detail popups, summary cards, a sortable checkpoint table, and a **0–48 hour weather heatmap** along
the corridor that you scrub with a slider and switch between combined-risk, wind, rain and snow.

**Who it's for** — truck drivers comparing routes before departure, fleet safety managers who need
severe and no-travel segments surfaced, and engineers wanting a complete, tested, self-hostable
example of arrival-time weather risk applied to real routing data.

## Quick start

Works from a clean clone. No API keys, no accounts, no cloud bill.

```bash
git clone https://github.com/S-V-J/dirmile.git && cd dirmile

# 1. Backend environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Frontend build
cd Frontend && npm install && npm run build && cd ..

# 3. Configuration — copy the template and generate a real secret
cp .env.example .env
python - <<'PY'
import secrets, pathlib
p = pathlib.Path(".env"); t = p.read_text()
t = t.replace("SECRET_KEY=replace-with-long-random-string",
              "SECRET_KEY=" + secrets.token_urlsafe(50))
p.write_text(t)
print("SECRET_KEY generated and written to .env")
PY

# 4. Database
cd Backend && python manage.py migrate && cd ..

# 5. Run
./dirmile start
```

`./dirmile start` allocates a free ephemeral port, collects static files, launches Django, and
prints both the local URL and the public tunnel URL. Smoke-test it:

```bash
PORT=$(tr -d '\r' < runtime/dirmile.port)
curl -sS "http://127.0.0.1:${PORT}/api/health/"     # {"status":"ok",...}
python -m pytest -q                                  # 168 passed
```

Open the printed URL, register, and plan a trip.

**Prerequisites**

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.14 | developed and tested on 3.14.4 |
| Node.js | 20+ | build-time only; the runtime needs none |
| `cloudflared` | any recent | only for the public URL — the app runs fine on its local URL without it |
| OS | Linux / WSL2 | `./dirmile` is bash; macOS should work, Windows native is untested |

> **Running `./dirmile start` from a fresh clone?** Step 4 above creates `db.sqlite3`. If you skip
> it, the first request that touches the database fails. `migrate` is idempotent — re-running it on
> an existing database is harmless.

## Screenshots

| | |
|---|---|
| ![Dirmile trip planner form with origin and destination autocomplete, departure date time picker and load weight input](docs/screenshots/01-trip-form-autocomplete.png) | ![Three route option cards with risk coloured checkpoint markers and the 0 to 48 hour weather heatmap on a Leaflet OpenStreetMap basemap](docs/screenshots/02-routes-heatmap-map.png) |
| **Trip inputs** — population-ranked place autocomplete, local-time departure picker, gross load weight, 10/25/50-mile checkpoint interval | **Map and heatmap** — route polylines in distinct colours, risk-graded checkpoint markers, corridor heatmap with forecast slider |
| ![Checkpoint table showing mile markers, estimated arrival times, wind speed, rain and snow with risk level badges](docs/screenshots/03-checkpoint-table-risk.png) | ![Settings page with default checkpoint interval, default load weight and default heatmap metric controls](docs/screenshots/04-settings-defaults.png) |
| **Checkpoint detail** — per-milepoint ETA, wind mph, rain and snow in/hr, and the overall risk grade, with load overrides flagged | **Persisted defaults** — saved preferences drive the app on next load, including the heatmap's opening metric |

## Features

**Input and validation**

- Origin and destination with **typeahead autocomplete**, population-ranked, backed by a cached
  same-origin geocoding endpoint
- Departure date/time with local-time and timezone display; naive input treated as local
- Gross load weight in pounds, with helper text and bounds validation
- Checkpoint interval of **10, 25 or 50 miles**, per trip and as a saved default
- Structured errors for geocoding failure, routing failure, weather failure, rate limiting,
  invalid departure, invalid load and unsupported route length — never a stack trace

**Routing and weather pipeline**

- Up to **3 route alternatives** from OSRM, with full GeoJSON geometry, distance, duration and
  turn-by-turn steps
- **Step-wise ETA derivation** — arrival at each checkpoint computed by walking OSRM step durations
  forward from departure, with a linear-distance fallback when steps are unavailable, and clamping
  so no checkpoint lands before the origin or after the destination
- **Corridor sampling** — mile markers placed along the decoded geometry at the chosen interval
- **Batched hourly forecasts** from Open-Meteo for every sampled point, buffered around the arrival
  window so a 06:00 departure and a 22:00 arrival are both covered
- Results cached, so re-planning the same corridor doesn't re-hit upstream APIs

**Risk engine** (`Backend/weather/risk.py` — pure functions, no I/O, fully unit tested)

- Exact wind / rain / snow thresholds, half-open boundaries
- Three **load-based overrides** for crosswind exposure, with `load_override_applied` surfaced so
  the UI can explain why a segment escalated
- Per-checkpoint overall risk as the most severe of wind / rain / snow
- Conservative **segment rule**: each stretch between two checkpoints takes the more severe of its
  endpoints

**Recommendation** (`Backend/plans/recommendation.py`)

- Mileage aggregated into **five risk bands** per route, plus a mileage-weighted average risk score
- Deterministic 8-level sort key — no dict-ordering surprises
- Plain-English `recommendation_reasons` on the winner, and comparisons against the runner-up

**Map and visualisation**

- All routes on one Leaflet map, canvas-rendered for performance
- Risk-coloured `CircleMarker` checkpoints with detail popups (label, mile, ETA, wind, rain, snow, risk)
- **Bidirectional selection** — click a table row to pan the map; click a map marker to highlight
  the table row
- **0–48 h heatmap** along the corridor via leaflet.heat, with a forecast slider and metric switch
  (combined risk / wind / rain / snow)
- Layer toggles for all-routes and checkpoints, plus a persistent risk legend
- Controls sit in a bar **below** the map, never floating over it

**Application**

- Session-cookie authentication with CSRF enforcement and transparent token rotation
- Per-user trip plans with server-side ownership enforcement
- Saved user settings (interval, default load, heatmap metric) that actually drive the app
- **Installable PWA** with auto-update and offline shell
- `dirmile` lifecycle CLI — dynamic ports, no background processes unless you ask

## Architecture

A **single Django process** serves the API, the admin, the built React SPA and the proxied map tiles
from one origin. That is deliberate: same-origin means session cookies need no CORS exceptions, the
service worker can cache tiles normally, and every tile request becomes visible in the application
log instead of vanishing into the browser's cross-origin network layer.

```text
Browser (React PWA)
   │  same-origin
   ▼
Django  ── WhiteNoise + SPA fallback view
 ├── /api/health/  /api/auth/*  /api/account/*  /api/plans/*  /api/places/
 ├── /tiles/{z}/{x}/{y}.png ──► tile.openstreetmap.org   (bounds-checked proxy)
 ├── /assets/*  /icons/*  /sw.js  /manifest.webmanifest  /* (SPA fallback)
 │
 ├── plans/services.py            orchestrates one trip plan
 │     ├── routing/osrm.py ───────► OSRM (alternatives=3)
 │     ├── core/geo.py ──────────► corridor sampling, mile markers, geometry decode
 │     ├── routing/eta.py ───────► step-wise ETA from departure
 │     ├── weather/services.py ──► Open-Meteo batched hourly forecast
 │     ├── weather/risk.py ──────► thresholds + load overrides  (pure, no I/O)
 │     └── plans/recommendation.py ► aggregate mileage bands, rank, explain
 │
 └── SQLite: TripPlan · RouteOption · Checkpoint · HeatmapPoint
```

**Data model**

| Model | Holds |
|---|---|
| `TripPlan` | owner, origin/destination (raw input + resolved name and coordinates), departure, load, interval, status, error message |
| `RouteOption` | label, index, distance, duration, GeoJSON geometry, the five risk-band mileages, average risk score, `is_recommended`, `recommendation_reasons` |
| `Checkpoint` | mile marker, lat/lng, ETA, wind/rain/snow values, the three component risks, overall risk, `load_override_applied` |
| `HeatmapPoint` | dense corridor point — mile marker, lat/lng, and 49-element hourly arrays for risk, wind, rain and snow |

**Cache policy** (asserted by `Backend/core/test_frontend.py` and `Backend/core/test_tiles.py`)

| Path | Headers | Why |
|---|---|---|
| `/assets/*`, `/workbox-*` | `public, max-age=31536000, immutable` | filename carries the content hash |
| `/tiles/*` (200) | `public, max-age=604800, immutable` | OSM tiles are immutable |
| `/tiles/*` (204 blank) | `no-store` | a transient upstream hiccup must never punch a week-long hole in the map |
| `/sw.js`, `/index.html` | `no-cache, no-store, must-revalidate` | the browser must always see the newest build |

**Tile proxy** — `/tiles/` forwards to OpenStreetMap with a single honest `User-Agent` identifying
Dirmile, as the OSM tile usage policy asks, rather than one per visitor. It is bounds-checked at
every layer (extension whitelist, zoom ≤ 19, tile coordinates within `2^z`) so it can never be
repurposed as an open crawler or an SSRF pivot. Upstream failure returns `204` rather than `500`, so
one flaky tile cannot break the map. Nine regression tests cover the happy path, `HEAD` support,
uppercase extensions, all three guard rejections, and both no-store blank paths.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.14 · Django 6.1 · Django REST Framework 3.18 · WhiteNoise · requests |
| Frontend | React 18 · TypeScript (strict) · Vite 6 · Tailwind CSS · React Router |
| Maps | Leaflet · leaflet.heat · OpenStreetMap raster tiles |
| Data APIs | Open-Meteo Forecast · Open-Meteo Geocoding · OSRM |
| Database | SQLite (dev/demo) · PostgreSQL-ready via `DATABASE_URL` |
| PWA | vite-plugin-pwa / Workbox, `generateSW` |
| Testing | pytest · pytest-django — 168 tests, no network calls |
| Hosting | WSL2 / Linux · Cloudflare Tunnel (`cloudflared`) |
| CI | GitHub Actions — backend tests + typecheck + production build on every push |

Production bundle: 479 kB JavaScript (146 kB gzipped), 47 kB CSS (13 kB gzipped), 18 precached PWA
entries.

## The `dirmile` CLI

One lifecycle script at the repo root. **No hardcoded port, and nothing runs in the background by
default** — the app starts only when you say so.

| Command | Effect |
|---|---|
| `./dirmile start` | allocate a free ephemeral port → rebuild the frontend if any source is newer → `collectstatic` → launch Django (`--noreload`, backgrounded) → print the local URL → launch the tunnel and print the public URL |
| `./dirmile stop` | kill the Django process group and the tunnel, clean runtime files |
| `./dirmile restart` | stop + start (rebuilds the frontend when needed) |
| `./dirmile status` | running state, PID, port, URLs, log path, health probe |
| `./dirmile logs` | tail the log (`Ctrl+C` to stop) |
| `./dirmile tunnel` | (re)launch the tunnel only |
| `./dirmile tunnel-stop` | stop the tunnel, leave Django up |
| `./dirmile enable` | install a systemd user service for auto-run (**opt-in**, off by default) |
| `./dirmile disable` | remove that service |

Design rules worth knowing:

- Ports are allocated dynamically from the ephemeral range and recorded in `runtime/dirmile.port`;
  nothing assumes `8000`, and nothing collides with another project on the same box.
- Django runs with `--noreload` so the PID the script tracks *is* the real server, not a reloader
  parent — which is what makes clean shutdown possible.
- The frontend rebuilds automatically when a source file is newer than the last build stamp, so
  `./dirmile restart` is always sufficient after a code change.
- `sw.js` is served `no-cache` and the worker uses `skipWaiting` + `clientsClaim` + `autoUpdate`, so
  browsers pick up every new build with no manual refresh and no DevTools.
- The tunnel wrapper records the real `cloudflared` PID and reaps it on exit, so restarts never
  accumulate orphaned proxies.
- All runtime state (`runtime/`, `logs/`, `*.pid`, `*.port`) is git-ignored.

## Configuration

Copy `.env.example` to `.env`. Secrets stay out of git; the template carries placeholders only.

| Variable | Default | Purpose |
|---|---|---|
| `DEBUG` | `False` | never `True` in a hosted deployment |
| `SECRET_KEY` | — | **required**; generate with `secrets.token_urlsafe(50)` |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,…` | comma-separated; must include the public hostname |
| `CSRF_TRUSTED_ORIGINS` | — | `https://` origins; **required** for cookie auth over a tunnel |
| `CORS_ALLOWED_ORIGINS` | *(empty)* | unused — the SPA is same-origin |
| `ROUTING_BASE_URL` | `https://router.project-osrm.org` | point at self-hosted OSRM for guaranteed 3 alternatives |
| `ROUTING_TIMEOUT_SECONDS` | `10` | per-request timeout |
| `ROUTING_MAX_ALTERNATIVES` | `3` | clamped to 1–10 |
| `ROUTING_CACHE_TTL_SECONDS` | `900` | |
| `GEOCODING_BASE_URL` | `https://geocoding-api.open-meteo.com` | |
| `GEOCODING_TIMEOUT_SECONDS` / `_CACHE_TTL_SECONDS` | `10` / `86400` | |
| `WEATHER_BASE_URL` | `https://api.open-meteo.com` | |
| `WEATHER_TIMEOUT_SECONDS` / `_CACHE_TTL_SECONDS` | `15` / `900` | |
| `WEATHER_MAX_BATCH_COORDINATES` | `1000` | batch ceiling per forecast request |
| `PLAN_MAX_HEATMAP_POINTS` | `500` | corridor density cap |
| `PLAN_HEATMAP_HOURS` | `49` | departure hour + 0–48 h |
| `PLAN_WEATHER_BUFFER_HOURS` | `2` | forecast padding around arrival times |
| `PLAN_MAX_CHECKPOINTS_PER_ROUTE` | `1000` | |
| `TUNNEL_MODE` | `quick` | `named` for a stable hostname, `quick` for an ephemeral one |
| `TUNNEL_NAME` / `TUNNEL_ID` / `TUNNEL_CREDS` / `TUNNEL_HOSTNAME` | — | named-tunnel wiring |

## API reference

All `/api/` endpoints require an authenticated session except `health`, `csrf`, `register` and
`login`. Authentication is cookie-based DRF session auth, with CSRF enforced on unsafe methods.

| Method | Path | Name | Auth | Purpose |
|---|---|---|---|---|
| `GET` | `/api/health/` | `health-check` | — | liveness probe → `{"status":"ok","service":"dirmile-backend","time":…}` |
| `GET` | `/api/auth/csrf/` | `csrf-token` | — | fetch a CSRF token for unsafe methods |
| `POST` | `/api/auth/register/` | `register` | — | create account — name, email, username, password, optional country / phone |
| `POST` | `/api/auth/login/` | `login` | — | establish session |
| `POST` | `/api/auth/logout/` | `logout` | ✓ | end session |
| `GET` | `/api/auth/me/` | `me` | ✓ | current user profile |
| `GET`/`PATCH` | `/api/account/settings/` | `account-settings` | ✓ | read and update checkpoint interval, default load, heatmap metric |
| `DELETE` | `/api/account/` | `account-delete` | ✓ | delete the account and all its plans |
| `GET` | `/api/plans/` | `plan-create-list` | ✓ | list the caller's plans (summary rows) |
| `POST` | `/api/plans/` | `plan-create-list` | ✓ | create a plan — origin, destination, departure, load, interval → routes, checkpoints, heatmap |
| `GET` | `/api/plans/<uuid:pk>/` | `plan-detail` | ✓ | re-read a stored plan; **byte-identical** to the creating response's heatmap arrays; `404` (not `403`) for other users' plans, so existence isn't leaked |
| `GET` | `/api/places/?q=` | `places-search` | ✓ | geocoding autocomplete, population-ranked, cached, slim payload |
| `GET`/`HEAD` | `/tiles/<int:z>/<int:x>/<int:y>.<ext>` | `tile-proxy` | — | same-origin OSM tile proxy — immutable on success, `204 no-store` on upstream failure |

Django admin is mounted at `/admin/` for the four plan models.

**Creating a plan**

```bash
curl -sS -c cookies.txt https://HOST/api/auth/csrf/
curl -sS -b cookies.txt -c cookies.txt -X POST https://HOST/api/auth/login/ \
  -H 'Content-Type: application/json' -H 'X-CSRFToken: TOKEN' \
  -d '{"username":"driver","password":"***"}'

curl -sS -b cookies.txt -X POST https://HOST/api/plans/ \
  -H 'Content-Type: application/json' -H 'X-CSRFToken: TOKEN' \
  -d '{"origin":"Cincinnati, OH","destination":"Chicago, IL",
       "departure":"2026-11-03T06:00:00Z","load_lb":36000,"interval_miles":25}'
```

The response carries the plan id, resolved places, and for each route: label, distance, duration,
risk-band mileages, `is_recommended`, `recommendation_reasons`, the checkpoint list and the heatmap
arrays.

## Risk model

Implemented exactly as specified in `Backend/weather/risk.py`. Boundaries are half-open, so 34.9 mph
is Moderate and 35.0 is High.

**Wind**

| Level | Range |
|---|---|
| Low | < 25 mph |
| Moderate | 25 – 34 mph |
| High | 35 – 44 mph |
| Severe | 45 – 54 mph |
| No Travel | ≥ 55 mph |

**Rain**

| Level | Range |
|---|---|
| Low | < 0.10 in/hr |
| Moderate | 0.10 – 0.24 in/hr |
| High | 0.25 – 0.49 in/hr |
| Severe | 0.50 – 1.00 in/hr |
| No Travel | > 1.00 in/hr |

**Snow**

| Level | Range |
|---|---|
| Low | < 0.5 in/hr |
| Moderate | 0.5 – 0.9 in/hr |
| High | 1.0 – 1.9 in/hr |
| Severe | 2.0 – 3.0 in/hr |
| No Travel | > 3.0 in/hr |

**Load overrides**, applied to wind in priority order:

| Condition | Result |
|---|---|
| wind ≥ 55 mph | **No Travel**, any load |
| 45 – 54 mph **and** load > 30,000 lb | **No Travel** |
| 35 – 44 mph **and** load > 40,000 lb | **Severe** |

When an override fires, `load_override_applied` is set on the checkpoint so the UI can explain *why*
that segment escalated. A checkpoint's overall risk is the most severe of its wind, rain and snow
grades. Each **segment** between two checkpoints takes the more severe of its two endpoints —
conservative, which is the right bias for a safety tool.

## Route recommendation

`Backend/plans/recommendation.py` aggregates checkpoint risk into per-band mileage and a
mileage-weighted average, then sorts ascending on a deterministic key:

1. routes without No-Travel segments first (safety precedence)
2. fewest No-Travel miles
3. **fewest Severe miles**
4. **fewest High miles**
5. **lowest average risk score**
6. **shortest travel time**
7. shortest distance (tie-breaker)
8. label (final tie-breaker, so output never depends on dict ordering)

Items 3–6 are the specified preference order; 1–2 add a safety floor so a route containing a
No-Travel segment is never recommended over one without it. The winner is flagged `is_recommended`
and carries human-readable reasons, for example:

```text
No No-Travel segments
No severe miles
High-risk miles: 18 mi
Average risk score: 0.42
Estimated travel time: 4h 12m
Fewer severe miles than Route B
Arrives 22m earlier than Route C
```

## Testing and CI

```bash
python -m pytest -q              # 168 passed
python -m pytest -q --tb=short
python -m pytest Backend/weather/tests.py -v
```

Coverage spans the risk engine (every threshold boundary and load override), ETA derivation, corridor
geometry sampling, OSRM request building and response normalisation (asserting `alternatives=3` is
actually sent), recommendation ordering, trip-plan models, authentication and ownership semantics,
the SPA fallback and its cache headers, path-traversal rejection, and the tile proxy's nine cases.

External APIs are mocked throughout — **the suite makes no network calls** and is deterministic, so
it passes identically on a laptop, in CI, and on a train.

GitHub Actions runs the backend suite plus a frontend typecheck and production build on every push
and pull request (`.github/workflows/ci.yml`). The build badge at the top of this file reflects it.

## Deployment

Dirmile is designed to run on a single Linux box — including WSL2 on a developer laptop — and be
reachable from the public internet without opening a single inbound port.

### Cloudflare Tunnel

`scripts/run-tunnel.sh` supports two modes, selected by `TUNNEL_MODE` in `.env`:

| Mode | Hostname | Use |
|---|---|---|
| `quick` | random `*.trycloudflare.com`, **new on every restart** | development, zero setup |
| `named` | a hostname you control, **stable forever** | demos, sharing a link, submissions |

Named mode regenerates a per-launch ingress config, so the tunnel always points at whatever port
Django allocated this time — the hostname is fixed while the local port is not. Readiness is
detected by the connector registering with the Cloudflare edge, not by a DNS lookup, so a pending
zone delegation never looks like a failure.

```bash
cloudflared tunnel login
cloudflared tunnel create dirmile
cloudflared tunnel route dns dirmile dirmile.example.com
```

Then in `.env`:

```ini
TUNNEL_MODE=named
TUNNEL_NAME=dirmile
TUNNEL_ID=<uuid printed by tunnel create>
TUNNEL_CREDS=/home/you/.cloudflared/<uuid>.json
TUNNEL_HOSTNAME=dirmile.example.com
ALLOWED_HOSTS=…,dirmile.example.com
CSRF_TRUSTED_ORIGINS=…,https://dirmile.example.com
```

```bash
./dirmile restart
```

**Both modes are outbound-only.** No inbound port is ever opened, no firewall rule is required, and
the host can sit behind NAT or CGNAT. The credentials JSON is never committed — `.env` and
`runtime/` are git-ignored.

### Production checklist

```text
[ ] DEBUG=False
[ ] A real SECRET_KEY (token_urlsafe(50) or longer), not the template placeholder
[ ] ALLOWED_HOSTS pinned to the exact public hostname — no wildcards in production
[ ] CSRF_TRUSTED_ORIGINS includes the https origin
[ ] python manage.py check --deploy reviewed (HSTS and SSL-redirect warnings are
    expected and acceptable when Cloudflare terminates TLS; fix them if you don't)
[ ] python manage.py migrate applied
[ ] Frontend built (npm run build) and static files collected — ./dirmile start does both
[ ] python -m pytest -q green
```

### Going beyond a single box

SQLite is correct for development and demo. For concurrent writers, point `DATABASE_URL` at
PostgreSQL and add a real cache (`CACHE_URL=redis://…`) — the application already uses Django's cache
framework for geocoding, routing and weather results, so the swap is configuration, not code. For
multiple instances, replace the local-filesystem tile and asset caches with shared storage and run
the tunnel against a load-balanced origin.

## PWA and offline

`vite-plugin-pwa` in `generateSW` mode precaches the app shell — 18 entries, ~586 KiB. The app
installs from any modern browser, launches standalone, and survives a disconnect.

- **Auto-update** — `sw.js` served `no-cache`, worker configured `skipWaiting` + `clientsClaim` +
  `autoUpdate`. A new build is picked up on next load; no manual refresh, no DevTools.
- **Runtime caching** — `/tiles/` is `CacheFirst` (immutable map data), `/api/*` is `NetworkFirst`
  (last-viewed plans survive a disconnect), app shell from precache.
- **Correctness guard** — blank responses are never written to cache (`statuses: [0, 200]`), so a
  `204` from the tile proxy cannot be mistaken for a cached tile.
- **Install UX** — `beforeinstallprompt` is bridged into a dismissible in-app banner.

Offline is deliberately scoped: the shell and previously viewed corridors work without a network, but
**route planning requires one** — weather and routing are live data by definition, and pretending
otherwise would produce confidently wrong safety advice.

## Guided tour

Dirmile is built to be used, not watched. Six things worth trying, in order, take about three minutes
on a running instance:

1. **Type a place.** Start typing `Cin` in Origin — the autocomplete returns population-ranked
   matches, so `Cincinnati, Ohio` wins over the small town of the same name.
2. **Plan a real trip.** Cincinnati → Chicago, depart tomorrow 06:00, load 36,000 lb, interval 25 mi.
   Watch the progress steps: geocoding → routes → weather sampling → risk → map.
3. **Compare the cards.** Each route shows distance, duration, risk-band mileage and the plain-English
   reasons behind the recommendation. Notice which route wins and why.
4. **Click both ways.** Click a checkpoint row in the table — the map pans. Click a marker on the map —
   the table row highlights. Same selection state, two directions.
5. **Scrub the forecast.** Drag the heatmap slider from 0 to 48 hours and watch the corridor change
   colour as the storm cell moves. Switch the metric to Wind, then Rain, then Snow — same points,
   different signal.
6. **Change a default.** Set Default Heatmap Metric to Wind in Settings, save, and plan a new trip —
   the slider opens on Wind. Saved settings genuinely drive the app.

Then read the code backwards from `plans/services.py`: it calls the same six modules the UI just
exercised, each independently testable, none of them touching the network except through a mock.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ValueError: Missing staticfiles manifest entry` | `collectstatic` not run, or run before the frontend build | `./dirmile restart` — it builds, then collects |
| Database errors on first request, `no such table` | migrations not applied | `cd Backend && python manage.py migrate` |
| `400 (Bad Request)` on the public URL, fine on localhost | hostname missing from `ALLOWED_HOSTS` | add it, then `./dirmile restart` |
| Login or save returns `403 CSRF` | `CSRF_TRUSTED_ORIGINS` doesn't include the https origin | add `https://your-host`, then restart |
| Tunnel prints a URL that returns 530 | the tunnel process was restarted, so the old hostname is dead | re-read `runtime/tunnel.url` — Quick Tunnel hostnames rotate per restart |
| `WARNING: DNS not yet resolved (30s)` during start | WSL name-resolution lag on a brand-new record | benign; the browser still loads. If it persists, check `logs/tunnel.log` |
| Multiple `cloudflared` processes running | a previous run wasn't reaped | `pkill -f cloudflared && ./dirmile restart` |
| Map shows grey tiles | upstream OSM hiccup, or no network | the proxy returns `204 no-store` by design so the hole isn't cached — reload after a moment |
| Heatmap looks empty | fewer than 2 route points, or heatmap toggled off | check the "Weather Heatmap" visibility toggle in the control bar |
| `pytest` collection errors after editing | stale bytecode | `find Backend -type d -name __pycache__ -exec rm -rf {} +` |

## Limitations and honest notes

Deliberately listed rather than hidden.

| Area | Status | Detail |
|---|---|---|
| **Route count** | requests 3, receives 1–2 | `alternatives=3` is sent and honoured (asserted in `test_osrm.py`). The public OSRM demo rejects `alternatives ≥ 4` with HTTP 400, and across **26 US and European corridors** tested it returned **at most 2** routes — including Los Angeles→San Francisco, which has three genuine parallel freeways. This is the provider's alternative-route diversity filter, not an application cap. Point `ROUTING_BASE_URL` at self-hosted OSRM, or a provider that honours the requested count, for a deterministic 3. |
| **Trip history UI** | not built | `GET /api/plans/` and `GET /api/plans/<uuid>/` exist, are tested, and return payloads byte-identical to the creating `POST` (verified on the heatmap arrays). No frontend page consumes them yet — reopening a saved plan is API-only today. |
| **OTP** | field only | `User.otp_enabled` exists and defaults to `False`. No second-factor flow is implemented, so the flag is inert. |
| **Email** | console backend | No mail-sending code exists; Django's console backend is intentional, not a misconfiguration. |
| **Display prefs** | persisted, unused | `theme` and `map_style` remain on the user model and API for forward-compatibility, but their UI controls were **removed** so the app ships no dead buttons. Wiring them (OSM-only terrain, or a satellite provider) is future work. |
| **Database** | SQLite | Correct for development and demo; swap to PostgreSQL for concurrent writers. |
| **Rate limiting** | not applied | `/api/plans/`, `/api/places/` and `/tiles/` are unthrottled. |
| **TLS hardening** | partial | Behind Cloudflare: `SECURE_HSTS_SECONDS` and `SECURE_SSL_REDIRECT` are unset — both expected warnings from `manage.py check --deploy` for a tunnel-fronted app. `DEBUG=False`, a 67-character `SECRET_KEY`, pinned `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are set. |
| **Forecast horizon** | 48 h | Risk beyond ~24 h inherits real forecast uncertainty. See the [disclaimer](#disclaimer). |
| **Offline planning** | not supported | By design — weather and routing are live data. |

## Security

- Cookie-based session auth; CSRF enforced on unsafe methods, with transparent token rotation after
  login and register so a rotated cookie never surfaces a 403 to the user.
- Ownership enforced server-side: another user's plan returns `404`, not `403`, so resource existence
  isn't leaked. Unauthenticated account endpoints return an explicit `401`.
- The SPA fallback rejects `..` path traversal and file-looking paths before serving `index.html`.
- The tile proxy whitelists extensions, caps zoom, validates tile coordinates against `2^z`, and
  bounds upstream fetches — it cannot be used as an open crawler or an SSRF pivot.
- Secrets (`SECRET_KEY`, tunnel credentials) live in git-ignored `.env` and `runtime/`;
  `.env.example` carries placeholders only, and CI injects a throwaway key rather than reading one.
- No third-party analytics, no tracking scripts, no fonts or CDNs loaded cross-origin. The only
  outbound calls are to the documented open APIs, made server-side where they can be logged and
  rate-limited.
- Passwords are hashed by Django's default PBKDF2; no plaintext or reversible storage anywhere.

For anything you'd rather not post publicly, open a private security advisory on GitHub rather than
an issue.

## Contributing

Contributions are welcome — bug reports, typo fixes, and especially corridor evidence for the route
count limitation above.

1. Fork and branch from `main`.
2. `pip install -r requirements.txt`, `cd Frontend && npm install`.
3. Make the change. `python -m pytest -q` must stay green; `npx tsc -b --noEmit` must stay clean.
4. If you touched the risk engine or the recommendation key, **add tests** — those two modules are
   the contract, and every boundary is enumerated on purpose.
5. Open a PR describing what changed and why, with the test output.

Please don't open a PR that swaps the tile provider, adds an API key requirement, or introduces a
build step without saying so first — several of those were evaluated and rejected deliberately.

## Credits and attribution

Dirmile stands entirely on open work. Thank you.

**Data and APIs**

| Service | Used for | Licence and terms |
|---|---|---|
| **OpenStreetMap** | basemap raster tiles | ODbL; subject to the tile usage policy. © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) |
| **OSRM** public demo server | route geometry, distance, duration, steps | FOSS routing engine; the demo carries no SLA or accuracy warranty |
| **Open-Meteo Forecast API** | hourly wind / rain / snow along the corridor | CC BY 4.0 — [open-meteo.com](https://open-meteo.com/en/docs) |
| **Open-Meteo Geocoding API** | origin and destination autocomplete | data © GeoNames and OpenStreetMap |

**Libraries** — [Django](https://www.djangoproject.com/),
[Django REST framework](https://www.django-rest-framework.org/),
[WhiteNoise](https://whitenoise.readthedocs.io/),
[requests](https://requests.readthedocs.io/) ·
[React](https://react.dev/), [TypeScript](https://www.typescriptlang.org/),
[Vite](https://vite.dev/), [Tailwind CSS](https://tailwindcss.com/),
[React Router](https://reactrouter.com/) ·
[Leaflet](https://leafletjs.com/), [leaflet.heat](https://github.com/Leaflet/Leaflet.heat) ·
[vite-plugin-pwa](https://vite-pwa-org.netlify.app/) and
[Workbox](https://developer.chrome.com/docs/workbox) ·
[pytest](https://docs.pytest.org/), [pytest-django](https://pytest-django.readthedocs.io/)

**Tooling and hosting** — [Cloudflare Tunnel / `cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
· WSL2 on Windows · GitHub Actions

The in-app map attribution — "© OpenStreetMap contributors", linking to the copyright page — is
rendered by the Leaflet `TileLayer` and **must remain present**; it is a condition of the OSM tile
usage policy, not a courtesy. Tiles are fetched through Dirmile's own same-origin `/tiles/` proxy
precisely so that one honest `User-Agent` identifies the application to OpenStreetMap rather than one
per visitor.

## Disclaimer

**Dirmile is a decision-support and educational project. It is not a safety system, and it must not
be used as the sole basis for any real-world go / no-go travel decision.**

- **Forecasts are estimates.** Weather is sampled from numerical-weather-prediction models at the
  truck's *estimated* arrival time. Skill degrades with lead time; conditions at a checkpoint may
  differ materially from the predicted values, particularly beyond 24 hours.
- **Risk levels are simplified heuristics.** The thresholds and load overrides are fixed, published
  rules applied uniformly. They do **not** consider vehicle or trailer configuration, driver
  experience, fatigue or hours-of-service limits, road grade, bridge or overpass exposure, crosswind
  geometry, pavement temperature, black ice, visibility, flooding, winterisation status, or any local
  advisory.
- **"No Travel" is advisory, not authoritative.** It is derived from weather thresholds alone. It
  does not reflect road closures, commercial-vehicle bans, DOT or emergency declarations, or carrier
  policy. Always consult official sources — state DOT, 511, the National Weather Service, and your
  dispatcher — before departing.
- **Routing data has no warranty.** Geometry, distances and durations come from the public OSRM demo
  server, which is rate-limited, may return fewer alternatives than requested, and offers no
  availability or accuracy guarantee. Travel times are idealised and exclude congestion, stops,
  inspections and mandatory breaks.
- **No affiliation.** This project is not affiliated with, endorsed by, or sponsored by the
  OpenStreetMap Foundation, Open-Meteo, Project OSRM, Cloudflare, or any other party named here.
  Trademarks belong to their owners.
- **No warranty; no liability.** Provided under the MIT License, "as is", without warranty of any
  kind, express or implied. To the maximum extent permitted by law, the author accepts no liability
  for any damage arising from the use of this software — including, without limitation, loss, delay
  or accident resulting from reliance on a route, risk grade or recommendation it produced.
- **Demo data.** Trip plans are stored in a local SQLite database for demonstration. Do not enter
  confidential, commercial or personal data you would not willingly share.

**If the weather is dangerous, do not drive. Trust official authorities and your own judgement over
any application, including this one.**

## License

Released under the **MIT License**. See [LICENSE](LICENSE).

Third-party data and services remain under their own terms — see
[Credits and attribution](#credits-and-attribution), which is not merely courtesy but a licensing
condition of the OpenStreetMap and Open-Meteo data used here.

## Author

**Siddhant Kumar** — Full-Stack Developer · VoIP and Telephony Engineer · AI Developer

Career started in enterprise technical support in 2021; three years and eight months as a Network
Associate at TELUS Digital on Canadian telecom infrastructure, then independent contracting from
2025 delivering PBX, AI-voice and full-stack systems for clients in **Switzerland, Germany and
India**.

- **This project:** Python / Django + DRF, React / TypeScript / Vite, Leaflet, PWA, Linux and WSL, Cloudflare Tunnel
- **Also:** Asterisk and Kamailio, FastAPI, LLM and agentic systems, AWS and Hetzner, Docker / Kubernetes / Terraform
- **Open to global remote roles** — full-time, up to 40 hrs/week, available immediately

| | |
|---|---|
| GitHub | [@S-V-J](https://github.com/S-V-J) |
| LinkedIn | [sid-093](https://linkedin.com/in/sid-093) — employment, education and certificates verifiable |
| Email | [stjl093@gmail.com](mailto:stjl093@gmail.com) |
| Based in | Bihar, India · remote-first |

Full work history, research publication and certifications are on LinkedIn, or in my
[profile README](https://github.com/S-V-J).

## Sponsor

If Dirmile or any of my other open-source work saves you time, sponsorship is what lets me keep
building and maintaining things in public.

<p align="center">
  <a href="https://github.com/sponsors/S-V-J">
    <img src="https://img.shields.io/badge/Sponsor%20-%20S--V--J-ea4aaa?style=for-the-badge&logo=githubsponsors&logoColor=white" alt="Sponsor S-V-J on GitHub Sponsors">
  </a>
</p>

<p align="center"><sub>Every tier, and every pass, is genuinely appreciated. 🙏</sub></p>

---

<p align="center"><sub>
Dirmile · weather-aware truck routing · Django + React + Leaflet + Open-Meteo + OSRM ·
PWA · MIT License
</sub></p>