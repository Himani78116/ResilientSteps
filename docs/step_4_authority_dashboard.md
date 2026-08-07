# Phase 4 — Authority Dashboard

## Goal

Build a web-based dashboard for municipal authorities that visualizes all
CityOS data — safety reports, infrastructure issues, waste reports — on a
unified map with ward-level analytics, heatmaps, and report management
capabilities. This is the first feature that serves the *authority* persona
rather than citizens.

## Prerequisites

- **Phases 1–3 complete**: WalkSafe, infrastructure, and waste modules exist.
- `report_categories` table is populated for all three modules.
- `incident_reports` has `report_type` and `severity` columns.
- Admin moderation endpoints support `report_type` filtering.

---

## Current State (as-is)

### What exists for authorities

- **Admin API endpoints** (`/admin/reports`, `/admin/reports/{id}/verify`,
  `/admin/reports/{id}/reject`): Simple moderation via `X-Admin-Key` header.
- **`GET /reports/recent`**: Returns recent verified safety reports with lat/lon.
- **`GET /safety-zones`**: Returns H3 zone GeoJSON.
- **No dashboard UI**: There is no web frontend. The admin workflow is
  curl/Postman only.

### What does NOT exist

- No web frontend of any kind.
- No ward boundary data.
- No report counts, trends, or aggregated analytics.
- No time-series data or report-age analysis.
- No export functionality.
- No role-based access control (RBAC) — admin auth is a single API key.

---

## Changes Required

### 1. Database — Alembic Migration (`0005`)

**File**: `backend/alembic/versions/0005_dashboard_support.py`

```sql
-- Ward boundaries for Pune (static GeoJSON import)
-- These would be loaded from a GeoJSON file of Pune's ward boundaries.
-- The exact source is the Pune Municipal Corporation ward map.
CREATE TABLE IF NOT EXISTS wards (
    id          SERIAL PRIMARY KEY,
    ward_id     TEXT NOT NULL UNIQUE,
    ward_name   TEXT NOT NULL,
    geometry    GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    zone        TEXT,                      -- e.g., 'Zone 1', 'Zone 2'
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wards_geom ON wards USING GIST (geometry);

-- Materialized view for ward-level report counts (refreshed periodically)
CREATE MATERIALIZED VIEW IF NOT EXISTS ward_report_summary AS
SELECT
    w.ward_id,
    w.ward_name,
    ir.report_type,
    ir.status,
    COUNT(*) AS report_count,
    AVG(ir.severity) AS avg_severity,
    MAX(ir.submitted_at) AS latest_report_at
FROM wards w
JOIN incident_reports ir
  ON ST_Contains(w.geometry, ir.location::geometry)
GROUP BY w.ward_id, w.ward_name, ir.report_type, ir.status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_ward_report_summary_pk
  ON ward_report_summary (ward_id, report_type, status);
```

### 2. Backend — Dashboard Module

**New directory**: `backend/app/modules/dashboard/`

```
backend/app/modules/dashboard/
├── __init__.py
├── routers/
│   ├── __init__.py
│   ├── analytics.py          ← aggregated stats endpoints
│   └── management.py         ← enhanced report management
├── services/
│   ├── __init__.py
│   ├── analytics_service.py  ← ward-level aggregation queries
│   └── export_service.py     ← CSV/JSON export
└── schemas/
    ├── __init__.py
    └── analytics.py          ← response models
```

#### Analytics Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/dashboard/summary` | `X-Admin-Key` | City-wide report counts by type, status, severity |
| `GET` | `/dashboard/wards` | `X-Admin-Key` | Ward-level summary (from materialized view) |
| `GET` | `/dashboard/wards/{ward_id}/reports` | `X-Admin-Key` | Reports within a specific ward |
| `GET` | `/dashboard/heatmap` | `X-Admin-Key` | H3 heatmap of all report types (not just safety) |
| `GET` | `/dashboard/trends` | `X-Admin-Key` | Time-series report counts (daily/weekly) |
| `GET` | `/dashboard/export` | `X-Admin-Key` | Export reports as CSV or JSON |
| `POST` | `/dashboard/refresh-summary` | `X-Admin-Key` | Trigger materialized view refresh |

#### Response Schemas

```python
class CitySummary(BaseModel):
    total_reports: int
    pending_count: int
    verified_count: int
    rejected_count: int
    by_type: dict[str, int]           # {"safety": 42, "infrastructure": 18, "waste": 7}
    by_severity: dict[int, int]       # {1: 5, 2: 12, 3: 30, 4: 8, 5: 3}
    average_verification_hours: float | None

class WardSummary(BaseModel):
    ward_id: str
    ward_name: str
    report_count: int
    avg_severity: float
    latest_report_at: datetime | None
    breakdown: dict[str, int]         # by report_type

class TrendPoint(BaseModel):
    date: str                         # ISO date
    count: int
    report_type: str
```

### 3. Backend — Register Module in `main.py`

```python
from app.modules.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
```

### 4. Backend — Analytics Service

**`analytics_service.py`** — key queries:

#### City-wide summary

```sql
SELECT
    report_type,
    status,
    COUNT(*) AS cnt,
    AVG(severity) AS avg_sev
FROM incident_reports
GROUP BY report_type, status;
```

#### Verification time metric

```sql
SELECT
    AVG(EXTRACT(EPOCH FROM (moderated_at - submitted_at)) / 3600.0)
    AS avg_hours_to_moderate
FROM incident_reports
WHERE moderated_at IS NOT NULL;
```

#### Time-series trends

```sql
SELECT
    DATE(submitted_at AT TIME ZONE 'Asia/Kolkata') AS report_date,
    report_type,
    COUNT(*) AS cnt
FROM incident_reports
WHERE submitted_at >= :since
GROUP BY report_date, report_type
ORDER BY report_date;
```

#### Multi-module heatmap

```sql
SELECT
    h3_cell,
    report_type,
    COUNT(*) AS report_count,
    AVG(severity) AS avg_severity
FROM (
    SELECT
        -- H3 cell computation would happen in Python using h3.latlng_to_cell()
        ST_Y(location) AS lat,
        ST_X(location) AS lon,
        report_type,
        severity
    FROM incident_reports
    WHERE status = 'verified'
) sub
GROUP BY h3_cell, report_type;
```

**Note**: H3 cell computation requires the `h3` Python library (already in
`requirements.txt`). The heatmap query fetches raw coordinates and computes H3
cells in Python, not in SQL. Alternatively, use `h3-pg` PostgreSQL extension
if available on Supabase.

### 5. Web Frontend (Minimal — Server-Side Rendered or Embedded)

**Approach decision required**: The project currently has no web frontend
framework. Options:

| Option | Pros | Cons |
|--------|------|------|
| **A. FastAPI static HTML + vanilla JS** | No new dependencies; works immediately; hackathon-friendly | Limited interactivity; hard to maintain |
| **B. Embedded Jinja2 templates** | Server-side rendering; no build step | Limited interactivity |
| **C. Separate Vite/React app** | Rich interactivity; modern tooling | New dependency; build step; CORS setup |
| **D. Flutter Web** | Reuses existing Flutter skills | Heavy for a dashboard; not ideal UX |

**Recommendation**: Option A (static HTML + vanilla JS with Leaflet.js for
maps) for hackathon/demo speed. This can be served from FastAPI's
`StaticFiles` mount. Files go in `backend/static/dashboard/`:

```
backend/static/dashboard/
├── index.html          ← dashboard layout
├── dashboard.js        ← fetch analytics + render
├── map.js              ← Leaflet map with heatmap overlay
└── styles.css          ← styling
```

Mount in `main.py`:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/dashboard-ui", StaticFiles(directory="static/dashboard", html=True))
```

The dashboard page fetches `/dashboard/summary`, `/dashboard/wards`, etc. via
`fetch()` with the `X-Admin-Key` header.

### 6. Ward Boundary Data

Ward boundary GeoJSON for Pune must be sourced and imported. Options:

- **Pune Municipal Corporation (PMC) open data portal** — official ward boundaries
- **OpenStreetMap administrative boundaries** — may not match PMC wards exactly
- **Manual digitization** — last resort

**Import script**: `logic/import_wards.py`

```python
# Read GeoJSON file → INSERT INTO wards (ward_id, ward_name, geometry)
import json
# ... load GeoJSON, iterate features, insert via asyncpg
```

---

## Verification

### Automated Tests

**New file**: `backend/tests/test_dashboard.py`

Test cases:
- City summary returns correct counts across all report types
- Ward summary aggregates correctly
- Trend endpoint returns daily time series
- Export endpoint returns valid CSV
- Dashboard endpoints require admin auth
- Materialized view refresh works

```bash
cd backend && python -m pytest tests/test_dashboard.py -v
```

### Manual Verification

1. Import ward boundaries: `cd logic && python import_wards.py`
2. `GET /dashboard/summary` → city-wide report counts
3. `GET /dashboard/wards` → ward-level breakdown
4. `GET /dashboard/trends?since=2026-01-01` → time-series data
5. `GET /dashboard/heatmap` → multi-module H3 heatmap
6. Open `http://localhost:8000/dashboard-ui/` → renders dashboard page
7. Dashboard map shows reports from all modules

---

## Done Criteria

- [ ] Alembic migration `0005` creates `wards` table + materialized view
- [ ] Ward boundary data imported for Pune
- [ ] `backend/app/modules/dashboard/` exists with analytics + management endpoints
- [ ] `/dashboard/summary`, `/dashboard/wards`, `/dashboard/trends` return data
- [ ] `/dashboard/export` exports CSV
- [ ] Dashboard web UI serves from `/dashboard-ui/`
- [ ] All existing tests pass
- [ ] New `test_dashboard.py` passes

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Materialized view refresh is slow with large datasets | Add `CONCURRENTLY` to refresh; schedule refresh rather than real-time |
| Ward boundary data not available | Fallback to OpenStreetMap admin boundaries; or skip ward grouping and use H3 only |
| Web dashboard security (XSS, CSRF) | Dashboard is admin-only; served behind `X-Admin-Key`; no user input stored |
| Leaflet adds external dependency | Bundle Leaflet locally in `static/`; or use CDN for demo |
| H3-pg extension unavailable on Supabase | Compute H3 cells in Python (already done in `generate_safety_map.py`) |
