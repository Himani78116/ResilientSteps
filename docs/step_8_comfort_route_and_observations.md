# Phase 8 — Comfort-Aware Route Finalisation & Live Observations

## Goal

Combine the three signals produced by earlier phases into the decision the
citizen cares about — which way to walk, right now, comfortably and safely — and
allow citizens to refine those signals in real time:

1. **Compose a comfort score** per segment and per route from `safety_score`
   (Phases 1–6) + `shade_score` (Phase 7) + `heat_penalty` (Phase 7).
2. **Finalise the route response** so `/route-safe` returns the per-segment
   comfort breakdown and a route-level summary, without changing the default
   output.
3. **Extend the observation system** so a citizen can report heat and shade
   conditions ("no shade on this stretch", "shaded and cool"), and verified
   observations refine the shade and heat picture live.

After this phase the mobile navigation card can display, for example:
> *"Route: 74% comfortable — well shaded, moderate heat."*

## Design rationale

1. **Compose without mutation.** Comfort is a new field. `safety_score` and every
   existing response key remain byte-for-byte identical.
2. **Default is a no-op.** The new `prefer` parameter defaults to `balanced`,
   which reproduces the current behaviour exactly.
3. **Reuse the existing observation loop.** Verified reports already change what
   the cache serves via `dataset_version` snapshots. Comfort corrections ride the
   same loop rather than introducing a parallel pipeline.
4. **Nullable additions only.** Every new mobile field is nullable; the UI keeps
   its existing rendering path when a value is absent.
5. **One weather sample per route.** Weather is fetched at a few route-level
   points, not per segment.

## Prerequisites

- **Phase 7 complete**: `shade_score` is on segments, `weather_service.py`
  exists, `config/scoring.yaml` has the `comfort` block, and all tests pass.
- Review `app/modules/walksafe/services/risk_engine.py` lines 11–181 and
  `app/modules/walksafe/routers/routing.py` lines 103–140 — these are the files
  being edited.
- Review `docs/step_2_infrastructure_reporting.md`: it added the `report_type`
  and `severity` columns and the `report_categories` table. Phase 8 reuses that
  machinery and does not introduce a new reporting table.

## Current state

### Scoring

`score_route()` (`app/modules/walksafe/services/risk_engine.py:21`) returns:

```python
{
  "safety_score": 74.2,          # length-weighted average
  "segment_count": 12,
  "matched_segment_count": 12,
  "unmatched_segment_count": 0,
  "applied_incident_count": 2,
  "incident_affected_segment_count": 1,
  "dataset_version": "20260815-101500",
  "segments": [ { "segment_index", "start", "end", "length_m", "matched",
                  "base_safety_score", "safety_score", "road_segment_id",
                  "road_type", "lighting", "incident_*", "zone" }, ... ],
  "warning": None,
}
```

The per-segment score is `max(0, base_safety_score − incident_penalty)`; the
route score is the length-weighted average of those (lines 87–95, 156).

### Route endpoint

`GET /route-safe` (`routers/routing.py:115`) fetches one Valhalla route, calls
`score_route()`, then copies `coordinates`, `distance_km`, and `duration_minutes`
onto the dict and returns it. `POST /route/risk` (`:103`) returns the same score
dict without route metadata.

### Mobile finalisation

`mobile/lib/services/routing_service.dart:27` (`getSafestRoute`) calls
`/route-safe`, parses `segments` into `RouteSegmentSafety`
(`mobile/lib/models/route_segment_safety.dart`), and parses the route into
`ScoredRoute` (`averageSafetyScore`, `totalRisk`, ...). `NavigationController`
(`mobile/lib/controllers/navigation_controller.dart`) is already a complete
live-tracking and rerouting state machine; it is not rebuilt in this phase.

### Observations

`POST /reports` → `reporting_service.create_report()` inserts into
`incident_reports` with `report_type` (default `'safety'`) and `severity`. Admin
verify/reject flips `status` to `verified`. Only `verified` rows affect scoring,
through `get_segment_incident_aggregates()` (`reporting_service.py:146`).
Categories are seeded in `report_categories` (migration `0003`).

## Implementation

### 1. Scoring — compose `comfort_score` in `risk_engine.py` (additive only)

Add module-level constants beside the existing ones (lines 11–14). Load them from
`config/scoring.yaml` if Phase 7 wired that; otherwise keep them here with a TODO.

```python
SAFETY_WEIGHT = 0.70
SHADE_WEIGHT = 0.20
HEAT_WEIGHT = 0.10

def _comfort_score(safety: float | None, shade: float | None, heat_penalty: float) -> float | None:
    if safety is None:
        return None                     # no safety data => no comfort claim
    shade_value = shade if shade is not None else safety   # unknown shade ~ neutral
    comfort = (
        SAFETY_WEIGHT * safety
        + SHADE_WEIGHT * shade_value
        - HEAT_WEIGHT * heat_penalty
    )
    return max(0.0, min(100.0, comfort))
```

`heat_penalty` is subtracted rather than added because it is a penalty (0–40)
from Phase 7, exactly as `incident_penalty` is subtracted in the safety formula.

**Weather sampling.** Do not call Open-Meteo per segment. Fetch once per route at
a small deduplicated set of sample points (route centroid plus endpoints):

```python
sample_points = _weather_sample_points(coordinates)   # 1–3 points
weather_by_point = [await weather_service.get_weather(lat, lon) for lat, lon in sample_points]
route_heat_penalty = max((w["heat_penalty"] for w in weather_by_point if w), default=0.0)
```

Assign that single `heat_penalty` to every segment. A route spans a few hundred
metres, over which heat does not meaningfully vary. If weather returns `None`,
`heat_penalty = 0` and the route is scored on safety and shade only.

In the per-segment loop (lines 68–143), add to each emitted segment dict:

```python
"shade_score": (round(float(shade), 1) if shade is not None else None),
"heat_penalty": round(heat_penalty, 1),
"comfort_score": (round(comfort, 1) if comfort is not None else None),
```

Accumulate `weighted_comfort_total` the same way `weighted_score_total` is
accumulated. Add route-level values to the return dict:

```python
"comfort_score": <length-weighted average or None>,
"comfort_level": _comfort_level(comfort_score),   # "comfortable"|"moderate"|"harsh"
"safety_score": <unchanged>,
"weather": weather_by_point[0] if weather_by_point else None,
```

The existing `"safety_score"` value and every existing key must remain identical.
Phase 8 only adds keys.

### 2. Endpoint — optional `prefer` parameter

In `routers/routing.py:route_safe` (line 115) add:

```python
prefer: str = "balanced",   # balanced | safety | shade | heat
```

- `balanced` (default): return the route as today, plus the new comfort fields.
- `safety` / `shade` / `heat`: reweight for reporting only — recompute
  `comfort_score` with that signal emphasised and report the emphasised value.
  A true alternative-route search (Valhalla `"alternates": N`) is a later phase
  and is not added here unless time allows.

Validate `prefer` against an allow-list and return HTTP 400 for any other value.

### 3. Observations — heat and shade categories and their effect

**Migration `0007`** (or folded into `0006` if Phase 7 has not shipped): seed new
rows into `report_categories`:

```sql
INSERT INTO report_categories (module, code, label) VALUES
  ('safety', 'no_shade',         'No shade / heavy sun'),
  ('safety', 'shade_obstruction', 'Shade blocked (overgrown / construction)'),
  ('safety', 'heat_stress',      'Heat stress / too hot to walk'),
  ('safety', 'cool_spot',        'Cool shaded spot / water available')
ON CONFLICT (code) DO NOTHING;
```

Extend the category-weight `CASE` in `get_segment_incident_aggregates()`
(`reporting_service.py:211–218`) so verified heat and shade observations receive
a sensible weight, kept separate from safety incident weight.

Comfort observations must not enter the safety penalty. Instead, add a second
aggregation method returning a per-segment shade correction:

```python
async def get_segment_shade_corrections(*, road_segment_ids, dataset_version, db) -> dict[int, float]
```

- `no_shade` / `shade_obstruction` verified → negative correction (−10 each,
  capped at −25).
- `cool_spot` verified → small positive correction (+5, capped at +10).
- Clamp the final per-segment shade to 0–100 after applying the correction.

This mirrors the incident-penalty design (`min(cap, weight × scale)`), keeping it
consistent and testable.

**Live refresh.** Verified observations already change what the cache serves,
because `SafetyDatasetCache` re-checks `dataset_version` every
`SAFETY_DATASET_REFRESH_SECONDS`. Shade corrections stay in the request-time
query (like incidents) so no re-ingest is required.

### 4. Mobile — carry the new fields end to end

- **`route_segment_safety.dart`**: add nullable fields `shadeScore`,
  `heatPenalty`, and `comfortScore`, and include them in the constructor.
- **`scored_route.dart`**: add `comfortScore` and `comfortLevel`.
- **`routing_service.dart`**: in `_parseRouteSegments` (around lines 209–280)
  read `segment['shade_score']`, `segment['heat_penalty']`, and
  `segment['comfort_score']` using the existing `_asDouble` helper (which returns
  `null` safely). In `getSafestRoute` read the route-level `comfort_score` and
  `comfort_level`.
- **`navigation_card.dart` / `route_summary_panel.dart`**: display the comfort
  badge and the dominant reason (shade versus heat). Keep it additive: when
  `comfortScore` is `null`, render exactly what is shown today.

### 5. Tests

**`backend/tests/test_comfort_scoring.py`**

- `_comfort_score()`: safety=80, shade=60, heat=0 → `0.7*80 + 0.2*60 = 68`;
  heat=20 → `68 − 2 = 66`; safety `None` → `None`.
- `/route-safe` for a fixture route returns `comfort_score` and an identical
  `safety_score` to a recorded baseline (the Phase 7 characterisation test catches
  regressions).
- `prefer=shade` changes `comfort_score` in the expected direction;
  `prefer=banana` → 400.
- `get_segment_shade_corrections()`: two `no_shade` reports → −10 each, capped;
  `cool_spot` → +5, capped; final shade clamped to 0–100.
- Weather failure (`None`) → the route still returns with `heat_penalty=0`.

**`mobile/test/route_segment_safety_test.dart`**

- Parsing the new fields from a sample `/route-safe` JSON, including the `null`
  case, yields the expected model values.

## Verification

### Automated

```bash
cd backend && python -m pytest tests/ -v
cd mobile && flutter analyze lib/ && flutter test
```

### Manual

```bash
# Comfort fields present
curl "http://localhost:8000/route-safe?start_lat=18.52&start_lon=73.85&end_lat=18.53&end_lon=73.86"
# → safety_score unchanged; new comfort_score / shade_score / heat_penalty present

curl "...&prefer=shade"     # comfort shifts toward shade
curl "...&prefer=banana"    # 400

# Observation loop: submit a no_shade report, verify as admin, re-request the route,
# confirm the segment's shade_score dropped and comfort_score moved.
```

## Done criteria

- [ ] `score_route()` returns `comfort_score`, `comfort_level`, `weather`, and
      per-segment `shade_score` / `heat_penalty` / `comfort_score`
- [ ] `safety_score` and all pre-existing keys are unchanged
- [ ] `/route-safe?prefer=...` accepts `balanced|safety|shade|heat`, 400 otherwise
- [ ] `report_categories` contains the four new heat and shade categories
- [ ] `get_segment_shade_corrections()` applies verified observations to shade
- [ ] Mobile models and services parse the new fields; UI degrades when null
- [ ] All existing backend and mobile tests pass

## Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| New weights silently change the safety route | `safety_score` is untouched; comfort is a separate additive field |
| Per-segment weather calls exceed the route latency budget | Call weather once per route (1–3 sample points); cache per hour |
| Comfort observations pollute the safety incident penalty | Separate `get_segment_shade_corrections()`; never added to `incident_weight` |
| Mobile crashes on missing comfort fields | All new model fields nullable; `_asDouble` returns `null`; UI keeps the old path |
| Scope creep into true alternative-route search | `prefer` only reweights the reported score this phase; alternates are a later phase |
| Cache never picks up shade corrections | Keep corrections request-time (like incidents), not baked into `shade_score` |
