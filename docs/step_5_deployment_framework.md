# Phase 5 — Deployment Framework

## Goal

Create a configuration-driven deployment system that supports four profiles —
`local`, `demo`, `aws`, `production` — switching infrastructure behavior
through config files rather than code changes. Add Docker containerization for
the FastAPI backend, a demo data seeder, and one-command deployment scripts.

## Prerequisites

- **Phases 1–4 complete**: All modules exist, dashboard is functional.
- All tests pass.
- The current deployment is "manual terminal commands" as documented in
  `deploymentsteps.txt` and `commandsteps/*.bat`.

---

## Current State (as-is)

### How deployment works today

- **Backend**: Run `uvicorn` directly on the laptop. Not containerized.
- **Valhalla**: Docker container via `backend/docker-compose.yml` (single service).
- **Database**: Remote Supabase PostgreSQL. No local DB option.
- **Mobile**: Build APK with `--dart-define` flags. Distributed via WhatsApp/Drive.
- **Config**: All config is in `backend/.env` (14 env vars) and mobile `--dart-define`
  (4 vars). No deployment profiles.
- **Demo data**: No seeder. Database must be manually populated via
  `logic/generate_safety_map.py` (10–20 min first run).
- **Tunnel**: ngrok started manually; domain hardcoded in CORS config at
  `backend/app/main.py` line 54.
- **Batch scripts**: 9 `.bat` files in `commandsteps/` for Windows deployment
  steps. Reference path is `C:\test\ResilientStepsCodex\mobile\` (not even this repo's path).

### Config files that do NOT exist

The ADR spec (Section 9) lists these as "everything configurable":
- `city.yaml` — does not exist
- `scoring.yaml` — does not exist
- `deployment.yaml` — does not exist
- `cron.yaml` — does not exist

All configuration is in `.env` files with no structured profiles.

---

## Changes Required

### 1. Config System — Profile-Based YAML

**New directory**: `config/` at project root

```
ResilientSteps/
├── config/
│   ├── profiles/
│   │   ├── local.yaml
│   │   ├── demo.yaml
│   │   ├── aws.yaml
│   │   └── production.yaml
│   ├── city.yaml              ← city-specific parameters
│   └── scoring.yaml           ← safety scoring weights
```

#### `config/city.yaml`

```yaml
# City configuration — change this to deploy for a different city.
city:
  name: "Pune"
  state: "Maharashtra"
  country: "India"
  center:
    lat: 18.5204
    lon: 73.8567
  osmnx_place: "Pune, Maharashtra, India"
  h3_resolution: 9                    # ~150m hexagons
  timezone: "Asia/Kolkata"
  valhalla_tile_url: "https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf"
```

#### `config/scoring.yaml`

```yaml
# Safety scoring weights — sourced from actual code values
road_type_scores:
  footway: 90
  pedestrian: 90
  living_street: 80
  path: 75
  cycleway: 72
  residential: 70
  service: 60
  unclassified: 55
  tertiary: 50
  secondary: 40
  primary: 30
  trunk: 20
  motorway: 5
  default: 50

modifiers:
  lighting_bonus: 10
  sidewalk_bonus: 5
  speed_penalty_per_10kmh: 3

incident_weights:
  stalking: 1.0
  harassment: 0.9
  suspicious_activity: 0.8
  unsafe_infrastructure: 0.7
  poor_lighting: 0.6
  default: 0.65

incident_decay:
  days_7: 1.0
  days_30: 0.8
  days_90: 0.55
  older: 0.3

runtime_risk_engine:
  road_match_distance_m: 20.0
  incident_penalty_scale: 12.0
  max_incident_penalty: 25.0
  incident_match_distance_m: 30.0

zone_thresholds:
  safe: 70       # score >= 70
  cautious: 40   # score >= 40
  risky: 0       # score < 40
```

#### `config/profiles/local.yaml`

```yaml
profile: local
description: "Development on a laptop"

backend:
  host: "0.0.0.0"
  port: 8000
  reload: true
  workers: 1

database:
  source: "env"                       # reads DATABASE_URL from .env

storage:
  type: "local"                       # images stored on local disk
  path: "backend/uploads/"

valhalla:
  url: "http://localhost:8002"

tunnel:
  enabled: false

demo:
  seed_data: false
  mock_users: false

cache:
  safety_dataset_refresh_seconds: 60

cors:
  origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
    - "http://127.0.0.1:3000"
    - "http://127.0.0.1:8080"
```

#### `config/profiles/demo.yaml`

```yaml
profile: demo
description: "Competition day demo with seeded data"

backend:
  host: "0.0.0.0"
  port: 8000
  reload: false
  workers: 1

database:
  source: "env"

storage:
  type: "local"
  path: "backend/uploads/"

valhalla:
  url: "http://localhost:8002"

tunnel:
  enabled: true
  provider: "ngrok"
  domain: "${NGROK_DOMAIN}"           # from .env

demo:
  seed_data: true
  mock_users: true
  mock_user_count: 10
  mock_report_count: 200
  precompute_heatmaps: true

cache:
  safety_dataset_refresh_seconds: 300  # less frequent for demo stability

cors:
  origins:
    - "*"                              # open for demo
```

#### `config/profiles/aws.yaml`

```yaml
profile: aws
description: "AWS pilot deployment"

backend:
  host: "0.0.0.0"
  port: 8000
  reload: false
  workers: 4

database:
  source: "env"                       # Supabase or RDS connection string

storage:
  type: "s3"
  bucket: "${S3_BUCKET}"
  region: "${AWS_REGION}"

valhalla:
  url: "${VALHALLA_URL}"              # ECS service or separate EC2

tunnel:
  enabled: false

demo:
  seed_data: false

cache:
  safety_dataset_refresh_seconds: 300

cors:
  origins: "${CORS_ORIGINS}"          # comma-separated list from env
```

#### `config/profiles/production.yaml`

```yaml
profile: production
description: "Production deployment with monitoring"

backend:
  host: "0.0.0.0"
  port: 8000
  reload: false
  workers: 8

database:
  source: "env"

storage:
  type: "s3"
  bucket: "${S3_BUCKET}"
  region: "${AWS_REGION}"

valhalla:
  url: "${VALHALLA_URL}"

tunnel:
  enabled: false

monitoring:
  sentry_dsn: "${SENTRY_DSN}"
  log_level: "WARNING"

cache:
  safety_dataset_refresh_seconds: 600

cors:
  origins: "${CORS_ORIGINS}"

backup:
  enabled: true
  schedule: "0 2 * * *"               # daily at 2 AM
```

### 2. Backend — Config Loader

**New file**: `backend/app/core/config.py`

```python
import os
import yaml
from pathlib import Path

PROFILE = os.environ.get("CITYOS_PROFILE", "local")
CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"

def load_config() -> dict:
    """Load city config + profile config, with env var interpolation."""
    city = _load_yaml(CONFIG_DIR / "city.yaml")
    scoring = _load_yaml(CONFIG_DIR / "scoring.yaml")
    profile = _load_yaml(CONFIG_DIR / "profiles" / f"{PROFILE}.yaml")
    return {"city": city, "scoring": scoring, "profile": profile}

def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        raw = f.read()
    # Interpolate ${ENV_VAR} references
    for key, value in os.environ.items():
        raw = raw.replace(f"${{{key}}}", value)
    return yaml.safe_load(raw) or {}
```

Add `pyyaml` to `backend/requirements.txt`.

### 3. Backend — Dockerfile

**New file**: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV CITYOS_PROFILE=local

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. Docker Compose — Full Stack

**Modified file**: `backend/docker-compose.yml` → move to project root as
`docker-compose.yml`:

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    environment:
      - CITYOS_PROFILE=${CITYOS_PROFILE:-local}
    depends_on:
      - valhalla
    restart: unless-stopped
    volumes:
      - ./config:/app/../config:ro
      - ./backend/uploads:/app/uploads

  valhalla:
    image: ghcr.io/gis-ops/docker-valhalla/valhalla:latest
    ports:
      - "8002:8002"
    volumes:
      - valhalla_tiles:/custom_files
    environment:
      - tile_urls=https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf
      - build_elevation=False
      - build_admins=True
      - build_time_zones=True
      - force_rebuild=False
    restart: unless-stopped

volumes:
  valhalla_tiles:
```

### 5. Demo Data Seeder

**New file**: `logic/seed_demo_data.py`

```python
"""
ResilientSteps Demo Data Seeder
========================
Seeds the database with realistic mock data for competition demos.

Usage:
    cd logic
    python seed_demo_data.py

Depends on: backend/.env for DATABASE_URL
"""

# Generates:
# - 10 mock users (user_hash values)
# - 100 safety incident reports (various categories, statuses, locations in Pune)
# - 50 infrastructure reports (potholes, streetlights, etc.)
# - 50 waste reports (bins, dumping, etc.)
# - Distributes reports across Pune within ARCHITECTURE.md radius (2500m)
# - Sets 60% as verified, 30% pending, 10% rejected
# - Backfills submitted_at across last 90 days for realistic trends
```

### 6. One-Command Scripts

**New file**: `scripts/start.sh` (Linux/Mac) and `scripts/start.ps1` (Windows)

```bash
#!/bin/bash
# Usage: ./scripts/start.sh [profile]
# Example: ./scripts/start.sh demo

PROFILE=${1:-local}
export CITYOS_PROFILE=$PROFILE

echo "Starting ResilientSteps with profile: $PROFILE"

if [ "$PROFILE" = "demo" ]; then
    echo "Seeding demo data..."
    cd logic && python seed_demo_data.py && cd ..
fi

docker compose up -d
echo "ResilientSteps is running at http://localhost:8000"
```

---

## Verification

### Automated Tests

**New file**: `backend/tests/test_config.py`

Test cases:
- Load local profile → correct defaults
- Load demo profile → seed_data=true
- Env var interpolation works
- Missing profile file → clear error
- Config values match actual code constants (cross-reference with scoring.yaml)

### Manual Verification

1. `CITYOS_PROFILE=local docker compose up` → backend + valhalla start
2. `CITYOS_PROFILE=demo ./scripts/start.sh demo` → seeds data + starts services
3. `curl http://localhost:8000/` → API responds
4. `curl http://localhost:8000/dashboard/summary` → shows seeded report counts

---

## Done Criteria

- [ ] `config/` directory exists with `city.yaml`, `scoring.yaml`, and 4 profile YAMLs
- [ ] `backend/app/core/config.py` loads and interpolates config
- [ ] `backend/Dockerfile` builds and runs the backend
- [ ] Root `docker-compose.yml` runs backend + valhalla
- [ ] `logic/seed_demo_data.py` seeds realistic demo data
- [ ] `scripts/start.sh` and `scripts/start.ps1` exist
- [ ] `CITYOS_PROFILE` env var switches behavior without code changes
- [ ] All existing tests pass
- [ ] Demo mode works end-to-end: seed → start → dashboard shows data

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| YAML config breaks existing `.env` workflow | Config system supplements `.env`, doesn't replace it; database credentials stay in `.env` |
| Profile interpolation exposes env vars in config files | Config files are in the repo; secrets stay in `.env` (gitignored) |
| Docker build adds 5+ min to CI | Use multi-stage builds; cache pip install layer |
| Demo seeder creates unrealistic data patterns | Generate reports along actual Pune streets using the cached OSMnx graph |
| pyyaml dependency adds attack surface | Pin version; pyyaml is widely used and audited |
| Old `commandsteps/*.bat` scripts reference wrong paths | Update or deprecate; point to new `scripts/` directory |
