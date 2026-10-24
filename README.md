<div align="center">

```
╔═══════════════════════════════════════════════════════════════════╗
║                     R E S I L I E N T S T E P S                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

**The safer, cooler way to walk.**

*Pedestrian safety & comfort navigation for Pune — routes that prioritise your safety and shade over speed.*

---

[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=flat-square&logo=flutter)](https://flutter.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostGIS-enabled-336791?style=flat-square&logo=postgresql)](https://postgis.net)
[![Valhalla](https://img.shields.io/badge/Routing-Valhalla-FF6B35?style=flat-square)](https://valhalla.github.io)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)

</div>

---

## What is ResilientSteps?

Most navigation apps optimise for speed. ResilientSteps optimises for **safety**.

Instead of asking "how do I get there fastest?" it asks "how do I get there most safely?" — routing pedestrians through well-lit streets, footpaths, and residential roads while avoiding high-speed arterials, poorly-lit stretches, and areas with recent incident reports.

Built for Pune, India. Designed for anyone who has ever felt uncertain walking home.

---

## How it works

```
Your location
      │
      ▼
 ┌─────────────────────────────────────────────────────┐
 │                   ResilientSteps Backend                  │
 │                                                     │
 │  ┌──────────┐    ┌───────────┐    ┌──────────────┐  │
 │  │ Valhalla │───▶│   Risk    │───▶│  Safe Route │  │
 │  │ Routing  │    │  Engine   │    │   Response   │  │
 │  └──────────┘    └───────────┘    └──────────────┘  │
 │        ▲               ▲                            │
 │        │               │                            │
 │  ┌──────────┐    ┌───────────┐                      │
 │  │   OSM    │    │ PostGIS   │                      │
 │  │  Graph   │    │  + H3     │                      │
 │  │ (Pune)   │    │  Zones    │                      │
 │  └──────────┘    └───────────┘                      │
 └─────────────────────────────────────────────────────┘
      │
      ▼
  Flutter app
  with live navigation,
  safety overlays,
  and incident reporting
```

Every street segment in Pune carries a **safety score** (0–100) derived from:

| Signal | How it's used |
|--------|--------------|
| Nearby incident reports | Reports within 75 m of a segment raise its incident risk (saturates at 5) |
| Road type | Drives lighting & crowd heuristics (arterials read busier/well-lit, footpaths/paths quieter — see scoring reference) |
| Nearby intersections | Intersections boost estimated crowd density |
| Time of day (IST) | Late-night segments score lower than daytime ones at ingest time |

In-motion, the route score additionally subtracts a penalty from **verified
community incident reports** near the road segments being walked.

Before you start walking, the app also shows a **comfort score** built from two
climate signals:

| Signal | How it's used |
|--------|--------------|
| Shade score | OSM tree canopy + green areas around each street segment (live data, not predefined) |
| Heat index | Live Open-Meteo "feels-like" temperature, banded Pleasant / Mild / High / Extreme |

Routes minimise total risk across all segments, not just distance.

### Concrete data flow

1. **Routing** — the app sends `GET /route-safe?start_lat=…&end_lat=…`. The
   backend asks self-hosted Valhalla for a pedestrian route, then `score_route`
   matches the route geometry to precomputed `road_segments` (STRtree cache,
   re-warmed automatically when the dataset version changes) and returns
   per-segment safety/shade/heat plus route comfort. The app renders the
   polyline, the zone overlay (from `/safety-zones`, cached offline in
   `shared_preferences`), and the card metrics.
2. **Destination search / geocoding** — the app calls Nominatim directly
   (search + reverse geocode, cached and rate-gated client-side). No backend
   proxy involved.
3. **Incident reporting** — the app `POST /reports` (Supabase JWT) → stored as
   `pending` in `incident_reports` → an operator verifies/rejects via the
   admin API using the `X-Admin-Key` header → verified reports influence
   future route scores (nearest-segment match within 30 m, weighted by
   confidence/category/status/recency). Nothing touches road segments at
   moderation time.
4. **SOS** — the app records `POST /reports/emergency` (GPS location +
   trusted contacts → `emergency_alerts`) and the **device** sends SMS to
   trusted contacts on its own. If GPS is unavailable the SOS is blocked.
5. **Precomputed vs live** — segment scores, zone hexagons and shade scores
   are precomputed by the `logic/` pipeline into PostGIS; weather heat
   penalty is fetched live per request (cached 15 min, degrades to 0 on
   failure); reports/scores interplay is live at scoring time.

---

## Features

### 🗺️ Safety-first routing
Routes scored segment-by-segment against the weighted safety model — picking routes that avoid high-incident stretches. The safety score for your route is shown before you start walking.

### 🔴 Live danger zone overlay
H3 hexagon polygons colour-coded green / amber / red based on aggregated street safety scores. Toggleable. Cached offline.

### 📍 Real-time navigation
- Live GPS position tracking with map auto-pan
- Heading-up mode — map rotates to face your direction of travel
- Route consumption — walked sections fade as you progress
- Automatic rerouting when you drift too far off-route (dynamic threshold,
  roughly 40–80 m depending on GPS fix quality, with a 15 s cooldown)
- Arrival detection near the destination

### 🚨 SOS alert
One-tap emergency alert. Your phone sends SMS messages to your saved trusted
contacts **directly from the device** (no backend needed for delivery), records
your real GPS location and the contact list against the backend
(`POST /reports/emergency`), and blocks the SOS if GPS is unavailable — never
sends a fake location. The backend records the event; it does not deliver
messages.

### 📋 Incident reporting
Report poor lighting, suspicious activity, or unsafe infrastructure. Reports enter a moderation queue — they do not affect safety scores until an operator verifies them.

### 🔒 Operator moderation
Simple API-based moderation workflow. Verified reports then affect scores
dynamically (see API reference) — segment data itself is not rewritten.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Mobile | Flutter 3.x |
| Backend | FastAPI (Python 3.11) |
| Routing engine | Valhalla (self-hosted via Docker) |
| Database | Supabase PostgreSQL + PostGIS |
| Migrations | Alembic |
| Spatial indexing | STRtree in-memory cache (Shapely) |
| Safety zones | H3 hexagons (resolution 9 ≈ 150m cells) |
| Street data | OpenStreetMap via OSMnx |
| Map tiles | Maptiler streets-v2 |
| Geocoding | Nominatim (called directly by the app) |
| Tunnel (demo) | ngrok static domain |

---

## Repository layout

```
ResilientSteps/
├── docker-compose.yml            Root stack: valhalla + backend services
├── linuxinstructions.md          Linux-specific setup notes
├── LOCAL_SETUP_STATUS.md         Three-terminal runbook + fresh-vs-stale checklist
├── config/                       City config (city.yaml: city name, OSM place)
├── docs/                         Learning log and project documentation
├── scripts/                      Miscellaneous helper scripts
│
├── backend/                      FastAPI server
│   ├── app/
│   │   ├── core/                 Database, auth middleware, rate limiting
│   │   ├── modules/walksafe/
│   │   │   ├── routers/          routing.py (route/scoring), reports.py (SOS),
│   │   │   │                     admin.py (moderation), nearby tile endpoints
│   │   │   ├── services/         Valhalla integration, risk engine, safety
│   │   │   │                     dataset cache (STRtree), weather (Open-Meteo)
│   │   │   └── schemas/
│   │   └── routers/, services/   Legacy import shims (2–4 lines, re-export
│                                 the app/modules/* code for old tests)
│   ├── alembic/                  Versioned database migrations
│   ├── tests/                    Pytest test suite (100 tests)
│   ├── docker-compose.yml        Same stack, paths relative to backend/
│   ├── requirements.txt
│   └── .env.example              ← copy to .env and fill in values
│
├── mobile/                       Flutter app
│   ├── lib/
│   │   ├── screens/home_screen.dart           Main map screen
│   │   ├── controllers/navigation_controller.dart  Navigation state machine
│   │   ├── widgets/               Map wrapper, nav card, route cards,
│   │   │                          zone overlay, incident modal, nearby sheet
│   │   ├── services/              Routing, place search (Nominatim), safety
│   │   │                          heatmap (offline zone cache), SOS (device
│   │   │                          SMS), trusted contacts, reporting APIs
│   │   └── config/app_config.dart Dart-defines bridge
│   ├── config/dart_defines.json   ← GITIGNORED: create locally with all 4 keys
│   └── .env.example
│
└── logic/                        Spatial data pipeline
    ├── generate_safety_map.py    OSMnx ingest + H3 zone generation
    ├── generate_shade_map.py     Tree-canopy shade_score seed (run AFTER safety map)
    ├── generate_street_graph.py  Standalone street graph builder
    ├── generate_incidents.py     Synthetic demo incident generator
    ├── seed_demo_data.py         Demo categories/reports seeding
    └── safety_feature_engine.py  Weighted-risk scoring engine
```

---

## Prerequisites

Before running ResilientSteps locally you need:

- [Flutter SDK](https://docs.flutter.dev/get-started/install) (stable channel)
- [Python 3.11+](https://www.python.org/downloads/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for Valhalla)
- A [Supabase](https://supabase.com) project with PostGIS enabled
- A [Maptiler](https://www.maptiler.com) free account (for map tiles)
- [ngrok](https://ngrok.com) free account with a static domain (for sharing the demo)

---

## Local setup

### 1 — Clone and configure

```bash
git clone https://github.com/suzannet-menon/ResilientSteps.git
cd ResilientSteps
```

Copy the environment template and fill in your values:

```bash
cp backend/.env.example backend/.env
```

Open `backend/.env` and set:

```env
# Supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Database (Supabase direct connection string)
DATABASE_URL=postgresql+asyncpg://postgres:password@db.your-project-ref.supabase.co:5432/postgres

# Routing
VALHALLA_BASE_URL=http://localhost:8002

# Admin moderation (generate with: python -c "import secrets; print(secrets.token_urlsafe(36))")
ADMIN_API_KEY=choose-a-long-random-string

# Optional: crash reporting
SENTRY_DSN=your-sentry-dsn
```

The mobile side has no standalone `.env` — its configuration is via
dart-defines. See `mobile/.env.example` for the same four values as a template.

## Environment configuration reference

The backend reads `backend/.env` at runtime; the Flutter app receives its
values **baked in at build time** (dart-defines / `mobile/config/dart_defines.json`).
Privileged keys (service role, admin key, JWT secret) belong only in the
backend `.env` — never in dart-defines, never in Git.

| Variable | Purpose | Required | Belongs in |
|---|---|---|---|
| `SUPABASE_URL` | Supabase REST/auth base URL | Yes | Backend + mobile |
| `SUPABASE_ANON_KEY` | Public anon key (RLS-enforced reads) | Yes | Backend + mobile |
| `SUPABASE_SERVICE_KEY` | Privileged service-role operations | Yes | **Backend only** |
| `SUPABASE_JWT_SECRET` | Local Supabase JWT validation (HS256) | Yes (auth) | **Backend only** |
| `DATABASE_URL` | Postgres/PostGIS async connection | Yes | **Backend only** |
| `VALHALLA_BASE_URL` | Routing engine (default `http://localhost:8002`) | Yes | Backend |
| `ADMIN_API_KEY` | Header key for `/admin/*` moderation | Yes (moderation) | **Backend only** |
| `MAPTILER_API_KEY` | Map tile access | Yes | Mobile (dart-define) |
| `SENTRY_DSN` | Crash reporting | Optional | Backend |
| `PHOTON_BASE_URL` | Placeholder in `.env.example`; not read by backend code today | Optional | Backend |

### Which address for the mobile app?

| Target | `API_BASE_URL` |
|---|---|
| Flutter web (Chrome) on the same machine | `http://127.0.0.1:8000` |
| Android emulator | `http://10.0.2.2:8000` — android's alias for the host loopback; plain `localhost` refers to the *emulator itself* |
| Physical phone | `http://<your-computer's-LAN-IP>:8000` — phone and computer must be on the same Wi-Fi with the backend started with `--host 0.0.0.0` |
| Shared demo APK | ngrok HTTPS URL (see below) |

Dart-defines are **frozen into the binary at build time** — commits do not
update an installed APK; rebuild is required.

### 2 — Set up the database

Enable the PostGIS extension in your Supabase dashboard:
> Database → Extensions → search "postgis" → enable

Run migrations:

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
```

### 3 — Start Valhalla (routing engine)

The root `docker-compose.yml` defines both `valhalla` and `backend`. Valhalla
downloads the OSM western-zone (western India) extract on first run (~500 MB).
This takes 10–20 minutes. Subsequent starts reuse the `valhalla_tiles` volume.

```bash
# From the project root — requires backend/.env to exist (the backend
# service mounts ./backend/.env, and docker compose validates it)
docker compose up -d valhalla
```

Wait until the terminal shows `Valhalla server running on port 8002`, then verify:

```bash
curl http://localhost:8002/status
# Expected: JSON response with tileset_last_modified
```

### 4 — Populate the safety database

Run the ingest pipeline to score every walkable street in Pune and generate H3 safety
zones. Takes 10–20 minutes on first run. The OSMnx graph is cached locally so
re-runs are fast.

```bash
cd logic
python generate_safety_map.py
```

When complete you will see (counts and versions are illustrative — they depend
on the current OSM data and pipeline run):
```
Written 449,342 segments to database.
Written 1,204 safety zone polygons.
Done. Dataset version: 20250103-141200 | Time: 847.3s
```

### 5 — Populate the shade scores

Safety-map rows start with `shade_score = NULL`; without this step every route
shows "Shade: -". The script fetches OSM canopy features (trees, parks, forests,
grass) once, scores a ~15 m buffer around each street segment, and updates the
rows written by `generate_safety_map.py` — it never inserts segments, so it must
run *after* step 4. It reads the same `DATABASE_URL` from `backend/.env`, and
creates the `(osm_way_id, dataset_version)` index it needs on first run.
Expect 10–30 minutes on first run (Overpass download); afterwards it runs from
the local cache.

```bash
cd logic
python generate_shade_map.py
```

When complete you will see (counts again illustrative):
```
Updating shade for dataset_version 20250103-141200...
Done writing 450,000 rows, committing...
Scored 450,000 segments. Mean shade 1.9 (skipped 1,102 edges without an OSM way id).
Done. Time: 1234.5s
```

> The shade job is **idempotent** — re-running rewrites the same rows and does
> not re-ingest geometry. Both seeds never overwrite the DB schema and can be
> re-run safely.

### 6 — Start the backend

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify:
```bash
curl http://localhost:8000/
# Expected: {"message":"ResilientSteps API is running","status":"online"}
curl http://localhost:8000/ready
# Expected: {"ready":true} once the safety dataset cache is warmed (503 during warmup)
```

### 7 — Run the mobile app

The app reads four compile-time constants (dart-defines). Create
`mobile/config/dart_defines.json` (gitignored — never committed) with all four
keys; the app asserts on all of them at startup:

```json
{
  "API_BASE_URL": "http://127.0.0.1:8000",
  "MAPTILER_API_KEY": "your-maptiler-key",
  "SUPABASE_URL": "https://your-project-ref.supabase.co",
  "SUPABASE_ANON_KEY": "your-anon-key"
}
```

Then run with the override for your target (dart-defines are **baked at build
time** — after any change, rebuild; APKs do not pick up new values from
commits):

```bash
cd mobile
flutter pub get

# Create config/dart_defines.json first, then:
flutter run -d chrome --dart-define-from-file=config/dart_defines.json

# Android emulator (10.0.2.2 = host loopback from inside the emulator):
# flutter run -d <emulator-id> --dart-define-from-file=config/dart_defines.json \
#   --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Physical Android device (same WiFi network as your laptop):
# flutter run -d <device-id> --dart-define-from-file=config/dart_defines.json \
#   --dart-define=API_BASE_URL=http://YOUR-LAN-IP:8000
```

> If the backend calls fail silently and the route shows **no shade score and
> no heat index at all**, check `API_BASE_URL` first — the backend always
> returns `heat_penalty` (it degrades to `0.0` → "Pleasant" if the weather API
> is down), so a missing heat index means the app never received the scored
> payload. Verify with:
> `curl "http://API_BASE_URL/route-safe?start_lat=18.5204&start_lon=73.8567&end_lat=18.53&end_lon=73.86"`

## Verification checklist & troubleshooting

After setup, confirm each layer before blaming the next one:

| Check | Command | Success looks like |
|---|---|---|
| Database | `alembic upgrade head` in `backend/` (idempotent) | "nothing to update" / migrations applied |
| Safety data | `SELECT count(*), count(shade_score) FROM road_segments;` in Supabase SQL editor | Both counts > 0 (else re-run steps 4–5) |
| Safety-zone endpoint non-empty | `curl "http://localhost:8000/safety-zones?min_lat=18.5&max_lat=18.6&min_lon=73.8&max_lon=73.9"\| jq ".features \| length"` (raw curl also fine) | `features` array length > 0 |
| Valhalla | `curl http://localhost:8002/status` | JSON with `tileset_last_modified` |
| Backend | `curl http://localhost:8000/ready` | `{"ready":true}` — 503 means the cache was still warming at startup; restart the backend (it warms on boot) |
| Route scoring | the `/route-safe` probe above | `segments[0].shade_score` and `heat_penalty` present |
| Mobile config | app starts without assertion errors | dart-defines file has all 4 keys (see step 7) |

### Common failures

| Symptom | Likely cause | Next step |
|---|---|---|
| Docker can't start (WSL2) | Docker Desktop not fully booted / WSL2 not enabled | Ensure `wsl --status` works; start Docker Desktop first, then `docker compose up -d valhalla` |
| Valhalla builds forever | First-run tile download (~500 MB western-India extract) | It can take 10–20+ min; watch the container logs (`docker compose logs -f valhalla`). Rebuild only when `force_rebuild=True` |
| Backend 500 / DB errors | `.env` missing or `DATABASE_URL` unreachable | `curl http://localhost:8000/ready`; check the pooler/DB URL; wait for startup warmup |
| Mobile: routes draw but no Safety/Shade/Heat card | `API_BASE_URL` wrong for the target (emulator vs phone vs Chrome — see config table) | Hit `/route-safe` via curl from the same machine; if JSON is fine, it is the baked URL — rebuild with the right override |
| Port 8000 already in use (Windows, WinError 10013) | A stale uvicorn holds the port | `Get-NetTCPConnection -LocalPort 8000 \| Select OwningProcess`, stop it, restart |
| Flutter web CORS errors | Dev origins / `CITYOS_PROFILE` config | CORS origins come from `config/` city/profile config (default `*`); check the backend console |
| Map tiles blank (403) | Wrong `MAPTILER_API_KEY` baked in | Fix `dart_defines.json`, rebuild |
| Zone hexagons missing | Safety map not run, or wrong mini bbox values | Run `/safety-zones` curl above; if empty, run step 4 |
| GPS never found (emulator) | Emulator returns heading 0/-1 and may have no fix | Inject a location in emulator controls; test GPS features on a real device |
| SOS sends nothing | No SMS permission / real SIM limitations | Device SMS needs the Android SMS permission and a working SIM; the backend record confirms the alert was triggered |

---

## Building a shareable demo APK

ResilientSteps uses ngrok to expose the local backend over a permanent HTTPS URL so the APK
works anywhere — not just on your local network.

### Set up ngrok

1. Sign up at [ngrok.com](https://ngrok.com) (free)
2. Claim your free static domain at [dashboard.ngrok.com/domains](https://dashboard.ngrok.com/domains)
3. Install ngrok and authenticate:
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN
   ```

### Start the demo stack

Open three terminals:

```bash
# Terminal 1 — Valhalla
docker compose -f backend/docker-compose.yml up valhalla

# Terminal 2 — Backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 3 — ngrok tunnel
ngrok http --domain=your-static-domain.ngrok-free.app 8000
```

Verify at `https://your-static-domain.ngrok-free.app/` — you should see the backend
health response.

### Build the APK

```bash
cd mobile
flutter build apk --release \
  --dart-define-from-file=config/dart_defines.json \
  --dart-define=API_BASE_URL=https://your-static-domain.ngrok-free.app
```

> The `dart_defines.json` file must contain all four keys (`API_BASE_URL`,
> `MAPTILER_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`) — the app asserts on
> all of them at startup. Here you override `API_BASE_URL` to the ngrok URL.

APK output:
```
mobile/build/app/outputs/flutter-apk/app-release.apk
```

Share this file via WhatsApp, Google Drive, or any method. Recipients install it by
opening the file on their Android device (requires "Install from unknown sources").

> **Note:** The app requires your laptop to be running and ngrok to be active. If
> your laptop sleeps, the app will show connection errors until you restart the stack.

---

## API reference

Interactive docs (FastAPI default, enabled): `http://localhost:8000/docs`

### Routing

```
GET /route?start_lat=&start_lon=&end_lat=&end_lon=
```
Returns a pedestrian route from Valhalla with encoded polyline.

```
POST /route/risk
Body: { "coordinates": [[lat, lon], ...] }
```
Scores a route's safety using the cached road segment data and live verified incidents.

```
GET /route-safe?start_lat=&start_lon=&end_lat=&end_lon=&prefer=balanced
```
Combined route fetch + safety scoring in a single call. Each segment includes
`safety_score`, `shade_score`, `heat_penalty`, and `comfort_score`; the top
level adds the route-wide comfort score/level. `prefer` selects the comfort
weighting: `balanced`, `safety`, `shade`, or `heat`.

```
GET /safety-zones?min_lat=&max_lat=&min_lon=&max_lon=
```
Returns GeoJSON FeatureCollection of H3 polygon safety zones within the bounding box.

### Reporting

```
POST /reports
Authorization: Bearer <supabase-jwt>
Body: { "category": "Poor lighting", "lat": 18.52, "lon": 73.85, "description": "..." }
```
Submit an incident report (auth required). Rate limited to 5 requests/hour per
IP. Enters as `pending`.

```
GET /reports/recent?limit=50
```
Most recent reports for the map feed (limit clamped to 200, no auth).

```
POST /reports/emergency
Authorization: Bearer <supabase-jwt>
Body: { "lat": 18.52, "lon": 73.85, "trusted_contacts": [{"name": "...", "phone": "..."}] }
```
Record an SOS alert with real GPS coordinates and trusted contact list.
Rate limited to 3 requests/10 minutes per IP. The backend only **records** the
alert — message delivery to contacts is done by the phone via on-device SMS.

### Admin moderation

All admin endpoints require `X-Admin-Key: your-admin-key` header.

```
GET  /admin/reports?status=pending
POST /admin/reports/{id}/verify
POST /admin/reports/{id}/reject
```

Verification flips the report's status — it does **not** rewrite road-segment
data. Verified reports affect scores dynamically at scoring time: an incident
report influences the nearest road segment within 30 metres of its location
(weighted by confidence, category, status and recency), and shade-relevant
categories ("no shade / heavy sun", "cool shaded spot / water available") add a
shade correction to that segment. Pending and rejected reports have no effect.

**Example moderation workflow:**

```bash
# List pending reports
curl "http://localhost:8000/admin/reports?status=pending" \
  -H "X-Admin-Key: your-admin-key"

# Verify report ID 42
curl -X POST "http://localhost:8000/admin/reports/42/verify" \
  -H "X-Admin-Key: your-admin-key"
```

---

## Running tests

```bash
# Backend tests (use the project venv)
cd backend
.\.venv\Scripts\python.exe -m pytest tests\ -q   # Windows
# or: python -m pytest tests/ -v                  (macOS/Linux, venv activated)

cd ..

# Flutter checks
cd mobile
flutter pub get
flutter analyze     # expected clean (2 pre-existing plugin deprecation infos)
flutter test        # expected 100% pass
```

---

## Safety scoring reference

Scores come from `logic/safety_feature_engine.py` (pipe:line-time base scores)
plus `backend/.../services/risk_engine.py` (route-time adjustments). There is
**no static road-type lookup table** — the score is a weighted-risk blend:

### Base segment score (`safety_feature_engine.py`)

risk = 0.45 × incident-risk + 0.25 × lighting-risk + 0.20 × crowd-risk
+ 0.10 × time-of-day-risk; score = (1 − risk) × 100, clamped to [0, 100].

Each component is estimated per segment:

| Component | Source | Notes |
|-----------|--------|-------|
| Incident risk | OSM incidents within 75 m of the segment (saturates at 5) | Cluster-driven, see below |
| Lighting score | Road-type heuristics (e.g. motorway 90, residential 58, footway 48, path 42 — **higher = better lit** since arterials carry lit stats) | Unknown road types default to 55 |
| Crowd density | Road-type base + 6 per nearby intersection (max +30) | Residential ≈ 50, pedestrian ≈ 72 |
| Time-of-day factor | 1.0 (07:00–18:00 IST), 0.7 (05–06 / 19–20), 0.5 (21–22), 0.3 (late night) | |

### Incident heat (community reports)

Verified/known incident reports cluster within 120 m and radiate influence
~140 m (grows with cluster size). Each report carries a weight of
confidence × status (verified 1.0, resolved 0.4, pending 0.65) × category
(stalking 1.0, harassment 0.9, suspicious 0.8, poor lighting 0.6) × recency
(≤7 days 1.0 → >90 days 0.3). Segment penalty = min(18, weight × 8).

### Route-time adjustments (`risk_engine.py`)

- Verified incident reports are matched to road segments within **30 m** and
  apply an additional incident penalty.
- Shade corrections from verified "no shade" / "cool shaded spot" reports are
  added to the base shade score (clamped).

### Zone classification

| Safety score | Zone colour | Risk level |
|-------------|-------------|-----------|
| ≥ 70 | 🟢 Green | Safe |
| 40–69 | 🟡 Amber | Cautious |
| < 40 | 🔴 Red | Risky |

## Shade & heat scoring reference

Every route segment also carries a shade score and the route carries live heat
data, which combine into the comfort score shown before you start walking.

### Shade score (`logic/generate_shade_map.py`)

Scores a ~15 m buffer around each street segment against OSM canopy features
(`natural=tree/wood/scrub`, `landuse=forest/grass`, `leisure=park/garden`):

| Component | Contribution |
|-----------|-------------|
| Tree points in buffer | 0.7 × min(1.0, trees ÷ 6) |
| Green-area coverage of buffer | 0.3 × min(1.0, coverage ÷ 0.6) |

Result clamped to [0, 100] and written as `shade_score` with
`shade_source='osm_canopy'`. The visual Shade % on a route is the average
across matched segments.

> **Data caveat:** OSM's canopy tagging in Pune is sparse — most segments
> score 0. A 0% reading is expected in unmapped areas, not a data error.

### Heat penalty (`backend/.../services/weather_service.py`)

Live Open-Meteo `apparent_temperature` (keyless, no API account):

| Feels-like temp | Heat penalty |
|----------------|-------------|
| ≥ 42 °C | 30 |
| ≥ 38 °C | 20 |
| ≥ 32 °C | 12 |
| ≥ 28 °C | 5 |
| below 28 °C | 0 |

UV index ≥ 8 adds +5. Weather failures **degrade, never block**: heat penalty
falls back to `0.0`, displayed as "Pleasant".

### Comfort score

Weighted blend of the safety, shade and heat signals. The `prefer` query
parameter on `/route-safe` selects the weighting profile: `balanced`,
`safety`, `shade`, or `heat`.

---

## Known limitations

- **Pune-only geography.** The Valhalla tile set covers an OSM western-India
  extract while the OSMnx scoring pipeline is scoped to Pune. Extending to
  other cities requires re-running the data pipeline and re-preprocessing
  Valhalla tiles.

- **Demo dependency on local laptop.** The ngrok distribution model requires the host
  machine to remain online. A proper cloud deployment (VPS with Docker Compose) would
  remove this constraint.

- **Road-type heuristics, not point tags.** The pipeline does not currently read
  point-level OSM tags like `lit=` or `sidewalk=` — lighting and crowd inputs
  come from road-type heuristics and intersection density. Unmapped/unknown
  road types fall back to middle-of-the-road defaults.

- **Sparse canopy data.** OSM tree/park tagging is sparse in Pune — most street
  segments shade-score 0, so route Shade % is often `0%`/`<1%` unless the route
  passes mapped greenery. Upgrading to satellite-derived canopy would fix this.

- **Heading on emulators.** Map rotation during navigation requires a real device
  with a compass. Android emulators return a constant heading of 0 or -1.

- **Media uploads.** Attaching photos to incident reports is planned for a future
  release. The button is hidden in v1.

---

## Privacy, security & safety disclaimer

Grounded in what the code actually does:

- **Location data sent to the backend:** your origin/destination coordinates
  go to the backend with every route request. Active navigation uses the
  device GPS fixes on-device only (camera anchoring, off-route detection);
  report/SOS submissions include the GPS coordinate recorded at that moment.
  The backend does not continuously track you.
- **Incident reports** are stored with the coordinates and link back to your
  Supabase user ID (JWT-derived hash on the server); they enter `pending` and
  are only surfaced on the map/reports feed.
- **SOS alerts** are stored in `emergency_alerts` together with the GPS
  coordinate, a timestamp and the trusted-contact list you supplied for that
  alert. Delivery happens via on-device SMS; the backend does not message
  anyone.
- **Trusted-contact details** are stored in the alert record and on-device
  (`shared_preferences`); they are not used beyond SMS fan-out and emergency
  records.
- **Secrets:** the Supabase service-role key, JWT secret, `ADMIN_API_KEY` and
  `DATABASE_URL` are server-side secrets in `backend/.env` (gitignored). The
  mobile app only needs the two public values (`SUPABASE_URL`,
  `SUPABASE_ANON_KEY`) plus the MapTiler key and `API_BASE_URL`.
- **Safety-score honesty:** scores are *estimates* derived from OSM tags and
  community reports — they can be stale, biased or wrong. They are decision
  support only, **not** a guarantee that a street is safe or dangerous.
- **Not an emergency service.** The SOS feature is an aid, never a substitute
  for contacting police/ambulance services (call 112 in India).

---

## Roadmap

- [ ] Cloud VPS deployment with Docker Compose (remove ngrok dependency)
- [ ] Play Store release with release keystore and proper signing
- [ ] Scheduled safety data refresh (weekly OSMnx re-ingest via cron — currently manual)
- [ ] Media upload support for incident reports (Supabase Storage)
- [ ] Backend-driven emergency fan-out (push notifications; on-device SMS already works today)
- [ ] Per-request time-of-day scoring (the pipeline currently bakes a time factor at ingest; route-time night penalties are not computed live)
- [ ] Expand beyond Pune to other Indian cities

---

## Contributing

ResilientSteps is a private project in active development. If you have been given access to
this repository:

1. Do not push directly to `main` — branch, PR, and wait for review
2. Keep `backend/.env` and `mobile/config/dart_defines.json` out of all commits — both are gitignored
3. `logic/generate_safety_map.py` may have local dataset changes — check before staging;
   never commit anything under `logic/outputs/`, `logic/cache/` or `backend/valhalla_tiles/`
4. Before committing:
   - Backend: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\ -q` (expected: all pass)
   - Mobile: `flutter analyze` (expected clean apart from 2 pre-existing plugin
     deprecation infos) and `flutter test` (expected all pass)
5. PRs should update this README if they change setup, endpoints or scoring behaviour

License: MIT (see [LICENSE](LICENSE)).

---

## Acknowledgements

ResilientSteps is built on the shoulders of genuinely excellent open-source work:

- **[OpenStreetMap](https://www.openstreetmap.org)** — the street data that makes
  safety scoring possible
- **[Valhalla](https://github.com/valhalla/valhalla)** — open-source routing engine
  with excellent pedestrian costing
- **[OSMnx](https://github.com/gboeing/osmnx)** — street network analysis in Python
- **[H3](https://h3geo.org)** — Uber's hexagonal spatial indexing system
- **[flutter_map](https://github.com/fleaflet/flutter_map)** — Flutter map rendering
- **[Supabase](https://supabase.com)** — open-source Firebase alternative
- **[Maptiler](https://www.maptiler.com)** — clean map tiles for production apps

---

<div align="center">

*Built for the people of Pune who deserve to walk home safely.*

</div>
