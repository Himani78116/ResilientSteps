# Phase 7 — Heat & Shade Data Layer

## Goal

Attach two environmental attributes to every walkable road segment so that route
scoring can optimise for walking comfort in addition to safety:

| Signal | Source | Update cadence | Computed |
|--------|--------|----------------|----------|
| **Heat** — temperature, heat index, humidity, UV | Open-Meteo API (keyless) | Hourly | Live, at request time |
| **Shade** — tree-canopy coverage | OpenStreetMap tree and landuse tags | On OSM re-ingest | Offline, in `logic/` |

Shade is a property of the map, not of a weather point. Open-Meteo reports the
ambient temperature at a coordinate; it cannot report whether a specific street
is under canopy. Shade is therefore precomputed from OpenStreetMap and stored per
segment, in the same way `safety_score` is stored today.

After this phase a segment row has the following shape:

```
road_segments
  id, geometry, road_type, lighting, safety_score, dataset_version,   <-- existing
  shade_score, shade_source, shade_updated_at                          <-- new
```

The backend can then report the current heat index for a segment without altering
any existing safety behaviour.

## Design rationale

1. **Precompute shade, fetch heat.** Canopy coverage changes only when the OSM
   dataset changes and is therefore materialised as a column. Heat changes
   hourly and is fetched per request.
2. **Nullable shade.** A segment whose canopy is unknown stores `NULL`, not `0`.
   Unknown shade must not be interpreted as full sun. `shade_source` records
   provenance (`osm_canopy`).
3. **Parse separately from transport.** The function that downloads weather is
   distinct from the function that interprets it. The parser accepts a plain
   `dict` and returns a plain `dict`, so it is unit-testable against a saved
   fixture with no network access.
4. **Degrade, never fail.** A weather outage must not fail route scoring. The
   weather service returns `None`; the caller skips the heat term.
5. **Migration is versioned SQL.** One additive `ALTER TABLE` with a reversible
   `downgrade()`.

## Prerequisites

- Phase 1 applied: the backend uses `app/modules/walksafe/**` and `app/core/**`.
- `alembic upgrade head` applied (currently through `0005`).
- All existing tests pass: `cd backend && python -m pytest tests/ -v`.
- `docs/BASELINE.md` reviewed for the current `road_segments` columns and cache
  behaviour.
- Outbound internet access from the backend host for Open-Meteo. No API key.

## Current state

### `road_segments` table (see `docs/BASELINE.md` §2)

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL | Primary key |
| `osm_way_id` | BIGINT | |
| `geometry` | GEOMETRY(LINESTRING, 4326) | |
| `safety_score` | FLOAT | 0–100 |
| `road_type` | TEXT | Nullable |
| `lighting` | BOOLEAN | |
| `dataset_version` | TEXT | e.g. `20260815-101500` |
| `updated_at` | TIMESTAMPTZ | |

No shade, canopy, temperature, or weather column exists. The codebase uses
"heat" only in the incident sense (incident density), which is unrelated to
temperature.

### Cache columns

`backend/app/modules/walksafe/services/safety_dataset_cache.py`:

- `ROAD_SEGMENTS_QUERY` (lines 41–53) selects `id, safety_score, road_type,
  lighting, ST_AsBinary(geometry)`.
- `CachedRoadSegment` dataclass (lines 70–77) holds those five fields.
- `_load_road_segments()` (lines 409–441) maps rows into dataclasses.
- `match_route_segments()` (lines 114–174) returns a dict per route segment
  including `segment_safety_score`, `road_type`, and `lighting`.

### Scorer input

`backend/app/modules/walksafe/services/risk_engine.py`:

- Module constants at lines 11–14 (`ROAD_MATCH_DISTANCE_METERS`,
  `INCIDENT_PENALTY_SCALE`, `MAX_INCIDENT_PENALTY`).
- `score_route()` (line 21) length-weights `base_safety_score − incident_penalty`
  across matched segments. It performs no network calls.

### HTTP client pattern

For a live HTTP call from a service, use the module-level lazily created
`httpx.AsyncClient` pattern in `routing_service.py` lines 12–20. For a small
in-memory cache, use the dict-cache pattern in
`app/modules/walksafe/routers/routing.py` lines 24–69.

## Implementation

### 1. Database — migration `0006`

**File**: `backend/alembic/versions/0006_shade_score.py`

Follow the style of `0005_dashboard_support.py` (raw `op.execute` SQL, plain
`revision`/`down_revision` strings). Set `down_revision = "0005"`.

```sql
-- upgrade()
ALTER TABLE road_segments
  ADD COLUMN IF NOT EXISTS shade_score FLOAT DEFAULT 0
    CHECK (shade_score >= 0 AND shade_score <= 100);

ALTER TABLE road_segments
  ADD COLUMN IF NOT EXISTS shade_source TEXT;

ALTER TABLE road_segments
  ADD COLUMN IF NOT EXISTS shade_updated_at TIMESTAMPTZ;

-- downgrade()
ALTER TABLE road_segments DROP COLUMN IF EXISTS shade_score;
ALTER TABLE road_segments DROP COLUMN IF EXISTS shade_source;
ALTER TABLE road_segments DROP COLUMN IF EXISTS shade_updated_at;
```

`DEFAULT 0` gives every existing row a valid "no shade recorded" value. The
column must not be added as `NOT NULL` without a default, or the migration will
fail against the existing rows.

Verify reversibility:

```bash
cd backend
alembic upgrade head      # applies 0006
alembic downgrade -1      # reverts
alembic upgrade head      # re-applies
```

### 2. Offline seed — `logic/generate_shade_map.py`

**Pattern**: `logic/generate_safety_map.py`. That script loads a cached OSMnx
walk graph, scores each edge, and upserts `road_segments` in batches. The shade
script uses the same graph and scores canopy coverage instead.

Canopy tags to fetch:

```
natural=tree
natural=wood
natural=scrub
landuse=forest
landuse=grass
leisure=park
leisure=garden
```

**Algorithm per road segment:**

1. Load the same `outputs/{city}_walk.graphml` cached graph used by the safety
   ingest.
2. Buffer each segment geometry by ~15 m (project to metres for the buffer, or
   use `buffer(0.00015)` in degrees).
3. Score canopy coverage within the buffer:

```python
# Module-level constants, mirroring ROAD_TYPE_SCORES in generate_safety_map.py.
TREE_COUNT_SATURATION = 6      # trees within the buffer for full tree score
VEG_AREA_FRACTION_CAP = 0.6    # buffer fraction under green area for full score
TREE_WEIGHT = 0.7
AREA_WEIGHT = 0.3

def score_edge_shade(tree_count: int, green_area_m2: float, buffer_area_m2: float) -> float:
    tree_component = min(1.0, tree_count / TREE_COUNT_SATURATION)
    if buffer_area_m2 <= 0:
        area_component = 0.0
    else:
        area_component = min(1.0, (green_area_m2 / buffer_area_m2) / VEG_AREA_FRACTION_CAP)
    shade = TREE_WEIGHT * tree_component + AREA_WEIGHT * area_component
    return max(0.0, min(100.0, shade * 100.0))
```

4. Write back with a batched
   `UPDATE road_segments SET shade_score = :score, shade_source = 'osm_canopy',
   shade_updated_at = NOW() WHERE id = :id`. The safety ingest inserts new rows;
   the shade seed only updates existing rows. Match on `id`, or on `osm_way_id`
   + `dataset_version`; document the choice in the script docstring.

Feature retrieval uses `ox.features_from_place(place, tags=...)` or
`features_from_bbox` to match the cached graph. Log feature counts before
writing so a zero-shade run is detectable.

`osmnx` is already used by the safety ingest; add it to `logic/requirements.txt`
if absent. No new backend dependency is required.

```bash
cd logic
python generate_shade_map.py
# Expect: "Scored <N> segments. Mean shade 41.2"
```

### 3. Cache — carry the new column

Edit `backend/app/modules/walksafe/services/safety_dataset_cache.py`:

1. Add `shade_score` to `ROAD_SEGMENTS_QUERY` (lines 41–53).
2. Add `shade_score: float | None` to `CachedRoadSegment` (line 70).
3. Populate it in `_load_road_segments()` (lines 409–441) using the same
   `float(...) if not None else None` guard as `safety_score`.
4. Add `"segment_shade_score": road_match.shade_score if road_match else None`
   to the dict built in `match_route_segments()` (around lines 158–162, beside
   `segment_safety_score`).

`shade_score` is optional. A snapshot loaded before the migration copies `None`,
and `score_route` must treat `None` as "unknown", never as `0`.

### 4. Backend — `weather_service.py`

**File**: `backend/app/modules/walksafe/services/weather_service.py`

**(a) Pure parser — no network:**

```python
def parse_weather_payload(payload: dict) -> dict:
    """Turn an Open-Meteo response dict into the flat weather dict."""
    current = payload.get("current", {}) or {}
    temperature = _as_float(current.get("temperature_2m"))
    apparent = _as_float(current.get("apparent_temperature"))
    humidity = _as_float(current.get("relative_humidity_2m"))
    uv_index = _as_float(current.get("uv_index"))
    is_day = current.get("is_day")
    heat_penalty = compute_heat_penalty(apparent, uv_index)
    return {
        "temperature_c": temperature,
        "apparent_temperature_c": apparent,
        "relative_humidity": humidity,
        "uv_index": uv_index,
        "is_day": bool(is_day) if is_day is not None else None,
        "heat_penalty": heat_penalty,
    }
```

**(b) HTTP client and cache:**

```python
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_TTL_SECONDS = 900.0   # weather changes hourly; 15 min is sufficient

CURRENT_FIELDS = "temperature_2m,apparent_temperature,relative_humidity_2m,uv_index,is_day"

class WeatherService:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client              # injected in tests
        self._cache: dict[tuple, tuple[float, dict]] = {}

    async def get_weather(self, lat: float, lon: float) -> dict | None:
        key = (round(lat, 2), round(lon, 2), _current_hour_key())
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        payload = await self._fetch(lat, lon)
        if payload is None:
            return None                    # degrade, never raise
        parsed = parse_weather_payload(payload)
        self._set_cached(key, parsed)
        return parsed
```

Rules:

- A weather failure must never break route scoring. Return `None` and let the
  caller skip the heat term.
- The cache key is rounded `(lat, lon, hour)`, so repeated route requests within
  an hour incur no additional cost.
- Reuse the lazily created client pattern from `routing_service.py` lines 12–20.

**Heat penalty curve** (module-level constants):

```python
HEAT_TIERS = [   # (apparent_temp_c_min, penalty)
    (42.0, 30.0),   # extreme heat — strongly discourage walking
    (38.0, 20.0),
    (32.0, 12.0),
    (28.0, 5.0),
]
UV_TIER_THRESHOLD = 8.0
UV_PENALTY = 5.0

def compute_heat_penalty(apparent_c, uv_index) -> float:
    penalty = 0.0
    if apparent_c is not None:
        for threshold, tier_penalty in HEAT_TIERS:   # descending
            if apparent_c >= threshold:
                penalty = tier_penalty
                break
    if uv_index is not None and uv_index >= UV_TIER_THRESHOLD:
        penalty += UV_PENALTY
    return min(40.0, penalty)
```

Open-Meteo `apparent_temperature` is the heat index (it already accounts for
humidity and wind). Use it directly; do not re-derive it.

### 5. Configuration — weights and endpoint

**File**: `config/scoring.yaml` (create the `comfort` block if absent; follow the
style of `config/city.yaml`, loaded by `app/core/config.py`).

```yaml
comfort:
  safety_weight: 0.70
  shade_weight: 0.20
  heat_weight: 0.10
  heat_penalty_enabled: true
weather:
  provider: open-meteo        # informational; no key required
  cache_ttl_seconds: 900
```

Phase 8 consumes these values when composing the score. Phase 7 only requires the
file to exist.

### 6. Tests

Keep the fake-session style from `test_routing_phase8.py` lines 18–91. Add
`backend/tests/conftest.py` only if shared fixtures are needed.

**`backend/tests/test_weather_service.py`**

- `parse_weather_payload()` against a saved Open-Meteo JSON fixture returns the
  expected flat dict.
- `compute_heat_penalty()` boundary table: 27→0, 28→5, 32→12, 38→20, 42→30,
  45→30; UV 8 adds exactly `UV_PENALTY`; unknown values return 0.
- `WeatherService.get_weather()` with an injected fake client returns parsed data
  and calls the fake once for two calls within the same hour (cache hit).
- A network error from the fake client returns `None` and does not raise.

**`backend/tests/test_shade_scoring.py`**

- `score_edge_shade(tree_count, area, buffer)` for: no trees and no green → 0;
  dense trees → ≥ 70; all-green with no trees → the `AREA_WEIGHT` ceiling;
  results clamped to 0–100.
- A cache test extending `test_routing_phase8.py`: a `CachedRoadSegment` with
  `shade_score=55` surfaces as `segment_shade_score` in
  `match_route_segments()` output.

These tests must pass without a database or internet connection.

## Verification

### Automated

```bash
cd backend
python -m pytest tests/test_weather_service.py tests/test_shade_scoring.py -v
python -m pytest tests/ -v            # all existing tests still green
```

### Manual

```bash
# Migration reversibility
cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head

# Shade seed produces real values (requires a populated road_segments table)
cd logic && python generate_shade_map.py
# then, in psql/Supabase SQL editor:
#   SELECT COUNT(*), AVG(shade_score) FROM road_segments WHERE shade_score > 0;
```

Open-Meteo check (no code required):

```
https://api.open-meteo.com/v1/forecast?latitude=18.5204&longitude=73.8567&current=temperature_2m,apparent_temperature,relative_humidity_2m,uv_index,is_day
```

## Done criteria

- [ ] `0006_shade_score.py` exists and applies and reverts cleanly
- [ ] `logic/generate_shade_map.py` writes non-zero `shade_score` for shaded streets
- [ ] `ROAD_SEGMENTS_QUERY`, `CachedRoadSegment`, `_load_road_segments`, and
      `match_route_segments` carry `shade_score`
- [ ] `weather_service.py` parses Open-Meteo and caches per `(lat, lon, hour)`
- [ ] `config/scoring.yaml` has a `comfort` block
- [ ] `test_weather_service.py` and `test_shade_scoring.py` pass offline
- [ ] All previously passing tests still pass (safety behaviour unchanged)

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Open-Meteo rate limits or outage | Cache per hour; on failure return `None` and skip heat; never fail the route |
| Migration fails on existing rows | `shade_score DEFAULT 0`; `ADD COLUMN IF NOT EXISTS` |
| Shade ingest silently scores everything 0 | Log feature counts and mean shade; assert a non-zero mean in a manual check |
| OSM canopy missing in some areas | `shade_source` records provenance; `NULL` is treated as "unknown", not "sunny" |
| Network call inside tests | `WeatherService(client=...)` injection; parser tested against a saved fixture |
| Confusion with the existing "incident heat" concept | Use `heat_penalty` only in the weather context; never reuse `incident_heat_score` |
