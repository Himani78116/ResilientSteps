<div align="center">

```
██╗    ██╗ █████╗ ██╗     ██╗  ██╗███████╗ █████╗ ███████╗███████╗
██║    ██║██╔══██╗██║     ██║ ██╔╝██╔════╝██╔══██╗██╔════╝██╔════╝
██║ █╗ ██║███████║██║     █████╔╝ ███████╗███████║█████╗  █████╗
██║███╗██║██╔══██║██║     ██╔═██╗ ╚════██║██╔══██║██╔══╝  ██╔══╝
╚███╔███╔╝██║  ██║███████╗██║  ██╗███████║██║  ██║██║     ███████╗
 ╚══╝╚══╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝
```

**The safer way to walk.**

*Pedestrian safety navigation for Pune — routes that prioritise your safety over speed.*

---

[![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=flat-square&logo=flutter)](https://flutter.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostGIS-enabled-336791?style=flat-square&logo=postgresql)](https://postgis.net)
[![Valhalla](https://img.shields.io/badge/Routing-Valhalla-FF6B35?style=flat-square)](https://valhalla.github.io)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)

</div>

---

## What is WalkSafe?

Most navigation apps optimise for speed. WalkSafe optimises for **safety**.

Instead of asking "how do I get there fastest?" it asks "how do I get there most safely?" — routing pedestrians through well-lit streets, footpaths, and residential roads while avoiding high-speed arterials, poorly-lit stretches, and areas with recent incident reports.

Built for Pune, India. Designed for anyone who has ever felt uncertain walking home.

---

## How it works

```
Your location
      │
      ▼
 ┌─────────────────────────────────────────────────────┐
 │                   WalkSafe Backend                  │
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
| Road type | Footways and residential streets score higher than arterials |
| Street lighting | `lit=yes` OSM tag adds a bonus |
| Sidewalk presence | Dedicated walkways add a bonus |
| Speed limit | Higher limits reduce the score |
| Verified incidents | Community reports apply a proximity penalty |

Routes minimise total risk across all segments, not just distance.

---

## Features

### 🗺️ Safety-first routing
Routes that prefer lit footpaths and residential streets. The safety score for your route is shown before you start walking.

### 🔴 Live danger zone overlay
H3 hexagon polygons colour-coded green / amber / red based on aggregated street safety scores. Toggleable. Cached offline.

### 📍 Real-time navigation
- Live GPS position tracking with map auto-pan
- Heading-up mode — map rotates to face your direction of travel
- Route consumption — walked sections fade as you progress
- Automatic rerouting if you deviate more than 50 metres
- Arrival detection at 30 metres from destination

### 🚨 SOS alert
One-tap emergency alert that records your real GPS location and notifies your saved trusted contacts via the backend. Blocked if GPS is unavailable — never sends a fake location.

### 📋 Incident reporting
Report poor lighting, suspicious activity, or unsafe infrastructure. Reports enter a moderation queue — they do not affect safety scores until an operator verifies them.

### 🔒 Operator moderation
Simple API-based moderation workflow. Verified reports automatically apply a safety score penalty to nearby road segments.

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
| Geocoding | Photon (via backend proxy) |
| Tunnel (demo) | ngrok static domain |

---

## Repository layout

```
walksafe/
├── backend/                    FastAPI server
│   ├── app/
│   │   ├── routers/
│   │   │   ├── routing.py      Route + safety score endpoints
│   │   │   ├── reports.py      Incident + emergency alert endpoints
│   │   │   └── admin.py        Operator moderation endpoints
│   │   ├── services/
│   │   │   ├── routing_service.py        Valhalla integration
│   │   │   ├── risk_engine.py            Safety scoring
│   │   │   ├── safety_dataset_cache.py   STRtree spatial cache
│   │   │   ├── safety_zone_service.py    Zone GeoJSON serving
│   │   │   └── reporting_service.py      Report + alert persistence
│   │   └── db/
│   │       ├── session.py                SQLAlchemy async session
│   │       └── supabase_client.py        Auth + storage client
│   ├── alembic/                Versioned database migrations
│   ├── tests/                  Pytest test suite
│   ├── docker-compose.yml      Valhalla container
│   ├── requirements.txt
│   └── .env.example            ← copy to .env and fill in values
│
├── mobile/                     Flutter app
│   ├── lib/
│   │   ├── screens/
│   │   │   └── home_screen.dart          Main map screen
│   │   ├── controllers/
│   │   │   └── navigation_controller.dart Navigation state machine
│   │   ├── widgets/
│   │   │   ├── walksafe_map_view.dart    Map wrapper
│   │   │   ├── navigation_card.dart      Bottom nav card
│   │   │   ├── map_layers_builder.dart   Route + marker rendering
│   │   │   ├── safety_zone_overlay.dart  Zone polygon overlay
│   │   │   └── incident_modal.dart       Report incident UI
│   │   ├── services/
│   │   │   ├── routing_service.dart
│   │   │   ├── navigation_math.dart
│   │   │   ├── trusted_contacts_service.dart
│   │   │   ├── reporting_api_service.dart
│   │   │   └── safety_heatmap_service.dart
│   │   └── config/
│   │       └── app_config.dart           Compile-time constants
│   └── .env.example
│
└── logic/                      Spatial data pipeline
    ├── generate_safety_map.py  OSMnx ingest + H3 zone generation
    └── safety_feature_engine.py Street scoring weights
```

---

## Prerequisites

Before running WalkSafe locally you need:

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
git clone https://github.com/your-username/walksafe.git
cd walksafe
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

# Admin moderation
ADMIN_API_KEY=choose-a-long-random-string

# Optional: crash reporting
SENTRY_DSN=your-sentry-dsn
```

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

Valhalla downloads the Maharashtra OSM extract on first run (~500 MB). This takes
10–20 minutes. Subsequent starts are fast.

```bash
# From the project root
docker compose -f backend/docker-compose.yml up valhalla
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

When complete you will see:
```
Written 82,341 segments to database.
Written 1,204 safety zone polygons.
Done. Dataset version: 20250103-141200 | Time: 847.3s
```

### 5 — Start the backend

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify:
```bash
curl http://localhost:8000/
# Expected: {"status": "ok", ...}
```

### 6 — Run the mobile app

```bash
cd mobile
flutter pub get

# Chrome (UI testing — some backend calls may not work due to CORS in dev)
flutter run -d chrome \
  --dart-define=API_BASE_URL=http://127.0.0.1:8000 \
  --dart-define=MAPTILER_API_KEY=your-maptiler-key

# Android emulator
flutter run -d <emulator-id> \
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 \
  --dart-define=MAPTILER_API_KEY=your-maptiler-key

# Physical Android device (same WiFi network as your laptop)
flutter run -d <device-id> \
  --dart-define=API_BASE_URL=http://YOUR-LAN-IP:8000 \
  --dart-define=MAPTILER_API_KEY=your-maptiler-key
```

---

## Building a shareable demo APK

WalkSafe uses ngrok to expose the local backend over a permanent HTTPS URL so the APK
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
  --dart-define=API_BASE_URL=https://your-static-domain.ngrok-free.app \
  --dart-define=MAPTILER_API_KEY=your-maptiler-key
```

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
GET /route-safe?start_lat=&start_lon=&end_lat=&end_lon=
```
Combined route fetch + safety score in a single call.

```
GET /safety-zones?min_lat=&max_lat=&min_lon=&max_lon=
```
Returns GeoJSON FeatureCollection of H3 polygon safety zones within the bounding box.

### Reporting

```
POST /report
Authorization: Bearer <supabase-jwt>
Body: { "category": "Poor lighting", "lat": 18.52, "lon": 73.85, "description": "..." }
```
Submit an incident report. Rate limited to 5 per user per hour. Enters as `pending`.

```
POST /report/emergency
Authorization: Bearer <supabase-jwt>
Body: { "lat": 18.52, "lon": 73.85, "trusted_contacts": [...] }
```
Record an SOS alert with real GPS coordinates and trusted contact list.

### Admin moderation

All admin endpoints require `X-Admin-Key: your-admin-key` header.

```
GET  /admin/reports?status=pending
POST /admin/reports/{id}/verify
POST /admin/reports/{id}/reject
```

When a report is verified, a safety score penalty is automatically applied to road
segments within 150 metres of the incident location.

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
cd backend

# Run the full test suite
python -m pytest tests/ -v

# Run specific phase tests
python -m pytest tests/test_routing_phase8.py tests/test_emergency_phase7.py -v
```

```bash
cd mobile

# Analyze the codebase
flutter analyze lib/

# Run widget tests
flutter test test/widget_test.dart
```

---

## Safety scoring reference

### Road type base scores

| OSM highway tag | Base score |
|----------------|-----------|
| `footway` | 90 |
| `pedestrian` | 90 |
| `living_street` | 80 |
| `path` | 75 |
| `residential` | 70 |
| `cycleway` | 72 |
| `service` | 60 |
| `unclassified` | 55 |
| `tertiary` | 50 |
| `secondary` | 40 |
| `primary` | 30 |
| `trunk` | 20 |
| `motorway` | 5 |

### Modifiers

| Condition | Effect |
|-----------|--------|
| `lit=yes` | +10 |
| Sidewalk present | +5 |
| Speed limit > 30 km/h | −3 per 10 km/h above 30 |
| Verified incident within 150m | −(confidence × 10) per incident |

Final score is clamped to [0, 100].

### Zone classification

| Safety score | Zone colour | Risk level |
|-------------|-------------|-----------|
| ≥ 70 | 🟢 Green | Safe |
| 40–69 | 🟡 Amber | Cautious |
| < 40 | 🔴 Red | Risky |

---

## Known limitations

- **Pune-only geography.** The Valhalla tile set and OSMnx pipeline are scoped to
  Maharashtra. Extending to other cities requires re-running the data pipeline with a
  different bounding box and re-preprocessing Valhalla tiles.

- **Demo dependency on local laptop.** The ngrok distribution model requires the host
  machine to remain online. A proper cloud deployment (VPS with Docker Compose) would
  remove this constraint.

- **OSM data quality.** Safety scoring is only as good as the OSM tags. Poorly mapped
  areas of Pune (missing `lit=`, `sidewalk=`, or `highway=` tags) default to a
  conservative middle score.

- **Heading on emulators.** Map rotation during navigation requires a real device
  with a compass. Android emulators return a constant heading of 0 or -1.

- **Media uploads.** Attaching photos to incident reports is planned for a future
  release. The button is hidden in v1.

---

## Roadmap

- [ ] Cloud VPS deployment with Docker Compose (remove ngrok dependency)
- [ ] Play Store release with release keystore and proper signing
- [ ] Scheduled safety data refresh (weekly OSMnx re-ingest via cron)
- [ ] Media upload support for incident reports (Supabase Storage)
- [ ] Real SOS fan-out to trusted contacts via SMS/push
- [ ] Time-of-day scoring (night penalties for poorly-lit areas)
- [ ] Expand beyond Pune to other Indian cities

---

## Contributing

WalkSafe is a private project in active development. If you have been given access to
this repository:

1. Do not push directly to `main`
2. Keep `backend/.env` out of all commits — it is gitignored
3. `logic/generate_safety_map.py` may have local dataset changes — check before staging
4. Run `flutter analyze lib/` and `pytest tests/ -v` before committing mobile or
   backend changes respectively

---

## Acknowledgements

WalkSafe is built on the shoulders of genuinely excellent open-source work:

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
