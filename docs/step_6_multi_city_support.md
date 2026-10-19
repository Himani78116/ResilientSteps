# Phase 6 — Multi-City Support

## Goal

Make ResilientSteps deployable for any city by parameterizing all Pune-specific values.
A new city deployment should require only:

1. A `city.yaml` config file with the city's coordinates and name.
2. Running the data ingest pipeline to download that city's street graph.
3. Importing ward boundaries (if available).

No code changes should be necessary.

## Prerequisites

- **Phase 5 complete**: Config system exists with `city.yaml`, `scoring.yaml`,
  and deployment profiles.
- Docker Compose deployment works.
- Demo seeder works.

---

## Current State (as-is)

### Pune-specific hardcoding locations

| Location | What's Hardcoded | Value |
|----------|-----------------|-------|
| `logic/generate_safety_map.py` line 136 | OSMnx place query | `"Pune, Maharashtra, India"` |
| `logic/generate_safety_map.py` line 127 | Cached graph filename | `"pune_walk.graphml"` |
| `ARCHITECTURE.md` lines 78–80 | City center + radius | `18.5204, 73.8567, 2500m` |
| `backend/docker-compose.yml` line 9 | Valhalla tile URL | `western-zone-latest.osm.pbf` |
| `backend/app/main.py` line 54 | ngrok domain in CORS | Hardcoded specific domain |
| `logic/safety_feature_engine.py` line 136 | Timezone | `UTC+5:30` (IST) |
| `logic/punegraph.py` | Module name | `punegraph` |
| `README.md` lines 14, 34, 512–513 | "Built for Pune" | Multiple references |
| `mobile/lib/services/routing_service.dart` | Default map center | Pune coordinates (likely) |

### What would break if you changed the city

1. **OSMnx download** (`generate_safety_map.py`): The `graph_from_place()` call
   is hardcoded to `"Pune, Maharashtra, India"`.
2. **Valhalla tiles**: The Docker Compose downloads `western-zone-latest.osm.pbf`
   (all of western India). A city outside western India needs a different extract.
3. **Cached graph filename**: `pune_walk.graphml` — a different city would
   silently load the wrong graph if the file already exists.
4. **Time-of-day scoring**: Hardcoded to IST (UTC+5:30) in `safety_feature_engine.py`.
5. **Mobile default center**: The Flutter app likely centers on Pune coordinates.

---

## Changes Required

### 1. Config — Use `city.yaml` Everywhere

The `city.yaml` created in Phase 5 already contains:

```yaml
city:
  name: "Pune"
  state: "Maharashtra"
  country: "India"
  center:
    lat: 18.5204
    lon: 73.8567
  osmnx_place: "Pune, Maharashtra, India"
  h3_resolution: 9
  timezone: "Asia/Kolkata"
  valhalla_tile_url: "https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf"
```

For a new city (e.g., Bangalore):

```yaml
city:
  name: "Bangalore"
  state: "Karnataka"
  country: "India"
  center:
    lat: 12.9716
    lon: 77.5946
  osmnx_place: "Bengaluru, Karnataka, India"
  h3_resolution: 9
  timezone: "Asia/Kolkata"
  valhalla_tile_url: "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
```

### 2. Logic Pipeline — Parameterize `generate_safety_map.py`

**Current** (lines 127–137):

```python
cache_path = os.path.join(os.path.dirname(__file__), "outputs", "pune_walk.graphml")
# ...
graph = ox.graph_from_place("Pune, Maharashtra, India", network_type="walk")
```

**Target**:

```python
import yaml

config_path = os.path.join(os.path.dirname(__file__), "..", "config", "city.yaml")
with open(config_path) as f:
    city_config = yaml.safe_load(f)["city"]

city_name = city_config["name"].lower().replace(" ", "_")
cache_path = os.path.join(os.path.dirname(__file__), "outputs", f"{city_name}_walk.graphml")
osmnx_place = city_config["osmnx_place"]

if os.path.exists(cache_path):
    graph = ox.load_graphml(cache_path)
else:
    graph = ox.graph_from_place(osmnx_place, network_type="walk")
    ox.save_graphml(graph, cache_path)
```

**Additional changes**:
- Add `pyyaml` to `logic/requirements.txt`
- Pass `city_config["h3_resolution"]` to the H3 zone generation function
  instead of hardcoding `9`

### 3. Logic Pipeline — Parameterize `safety_feature_engine.py`

**Current** (lines 135–139):

```python
pune_tz = timezone(timedelta(hours=5, minutes=30))
# ...
pune_timestamp = timestamp.astimezone(pune_tz)
```

**Target**:

```python
import zoneinfo
# Accept timezone as parameter, default from config
city_tz = zoneinfo.ZoneInfo(self._timezone or "Asia/Kolkata")
local_timestamp = timestamp.astimezone(city_tz)
```

Update `SafetyFeatureEngine.__init__()` to accept an optional `timezone: str`
parameter.

### 4. Docker Compose — Parameterize Valhalla Tiles

**Current** (`docker-compose.yml` line 9):

```yaml
- tile_urls=https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf
```

**Target**:

```yaml
- tile_urls=${VALHALLA_TILE_URL:-https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf}
```

The `VALHALLA_TILE_URL` env var is set from `city.yaml` by the startup script
or by the config loader.

### 5. Backend — City-Aware CORS

**Current** (`main.py` lines 48–59): Hardcoded origins list including a specific
ngrok domain.

**Target**: Read CORS origins from the deployment profile config:

```python
from app.core.config import load_config
config = load_config()
cors_origins = config["profile"].get("cors", {}).get("origins", ["*"])
```

### 6. Backend — City Info Endpoint

**New endpoint** in a shared module or core:

```python
@app.get("/city")
async def get_city_info():
    config = load_config()
    return {
        "city": config["city"]["name"],
        "center": config["city"]["center"],
        "timezone": config["city"]["timezone"],
    }
```

The mobile app can fetch this at startup to auto-center the map.

### 7. Mobile — Dynamic City Center

**Current**: The Flutter map likely initializes at hardcoded Pune coordinates.

**Target**: Fetch `/city` endpoint at startup and use the returned center
coordinates. Fallback to a default if the endpoint is unreachable.

```dart
// In app initialization:
final cityInfo = await apiClient.get('/city');
final center = LatLng(cityInfo['center']['lat'], cityInfo['center']['lon']);
```

### 8. Multi-City Database Strategy

**Option A — Separate databases per city** (recommended for pilot):
- Each city gets its own Supabase project or PostgreSQL database.
- The `DATABASE_URL` in `.env` points to the correct city's database.
- Simple, no schema changes needed.

**Option B — Single database with city_id column**:
- Add `city_id TEXT` column to `road_segments`, `safety_zones`, `incident_reports`.
- All queries filter by `city_id`.
- More complex, but enables a single dashboard across cities.

**Recommendation**: Start with Option A. If multi-city dashboard is needed,
migrate to Option B with an Alembic migration that adds `city_id` columns.

### 9. New City Onboarding Script

**New file**: `scripts/onboard_city.sh`

```bash
#!/bin/bash
# Usage: ./scripts/onboard_city.sh <city_config.yaml>
# Example: ./scripts/onboard_city.sh config/cities/bangalore.yaml

CONFIG_FILE=$1
CITY_NAME=$(python -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['city']['name'])")

echo "Onboarding city: $CITY_NAME"

# 1. Copy city config
cp $CONFIG_FILE config/city.yaml

# 2. Update Valhalla tiles
TILE_URL=$(python -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['city']['valhalla_tile_url'])")
export VALHALLA_TILE_URL=$TILE_URL

# 3. Rebuild Valhalla tiles
docker compose up valhalla -d
echo "Waiting for Valhalla to build tiles (this may take 10-20 minutes)..."
until curl -s http://localhost:8002/status > /dev/null 2>&1; do sleep 10; done

# 4. Run data ingest
cd logic && python generate_safety_map.py && cd ..

# 5. Import ward boundaries (if available)
WARD_FILE="config/wards/${CITY_NAME,,}_wards.geojson"
if [ -f "$WARD_FILE" ]; then
    cd logic && python import_wards.py "$WARD_FILE" && cd ..
fi

echo "City $CITY_NAME onboarded successfully."
```

---

## Verification

### Automated Tests

**New file**: `backend/tests/test_multi_city.py`

Test cases:
- Config loader reads city.yaml correctly
- City endpoint returns config values
- Different city configs produce different OSMnx place queries
- Timezone parameterization works in safety_feature_engine
- Scoring weights read from scoring.yaml match constants

```bash
cd backend && python -m pytest tests/test_multi_city.py -v
```

### Manual Verification (requires time)

1. Create a test `city.yaml` for a small city (e.g., a suburb of Pune)
2. Run `generate_safety_map.py` → verify it downloads the correct graph
3. Run the backend → verify `/city` returns the new city config
4. Verify H3 zones are generated for the new area
5. Verify the mobile app centers on the new city's coordinates

---

## Done Criteria

- [ ] `generate_safety_map.py` reads city name and place from `city.yaml`
- [ ] `safety_feature_engine.py` accepts timezone parameter
- [ ] Docker Compose uses `VALHALLA_TILE_URL` from env/config
- [ ] CORS origins come from profile config, not hardcoded
- [ ] `/city` endpoint returns city metadata
- [ ] Mobile app uses dynamic city center from API
- [ ] `scripts/onboard_city.sh` exists and works
- [ ] All existing tests pass with Pune config (no behavioral change)
- [ ] A second city config can be created without any code changes

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| OSMnx download for large cities takes hours | Use bounded `graph_from_bbox` as fallback; document expected times |
| Valhalla tile rebuild for different region takes 20+ min | Parallelize with data ingest; use pre-built tiles if available |
| Different cities have different OSM data quality | Document minimum OSM tag coverage needed for scoring to work |
| Mobile APK needs rebuild for each city | Config comes from API, not compile-time; only `API_BASE_URL` needs to change |
| Ward boundaries unavailable for new cities | Ward features are optional; dashboard works without them (H3-only mode) |
| Cache files for old city persist | Namespace cache files by city name (e.g., `bangalore_walk.graphml`) |
