# Phase 3 — Waste Management Reporting

## Goal

Add a waste management module that lets citizens report sanitation issues —
overflowing bins, illegal dumping, construction debris, garbage burning, and
dead animals. This module follows the exact same structural pattern established
in Phase 2 (infrastructure reporting), reusing the shared `incident_reports`
table with `report_type='waste'`.

## Prerequisites

- **Phase 2 complete**: `incident_reports` has `report_type` and `severity`
  columns. `report_categories` table exists with seed data.
- The `app/modules/infrastructure/` module exists as a pattern reference.
- All tests pass.

---

## Current State (as-is)

After Phase 2:
- `incident_reports` table has `report_type` column (values: `'safety'`, `'infrastructure'`).
- `report_categories` table has safety and infrastructure categories.
- Admin moderation supports `report_type` filtering.
- The module pattern (`modules/<name>/routers/`, `services/`, `schemas/`) is established.

---

## Changes Required

### 1. Database — Alembic Migration (`0004`)

**File**: `backend/alembic/versions/0004_waste_categories.py`

Seed waste management categories into the existing `report_categories` table:

```sql
INSERT INTO report_categories (module, code, label, description) VALUES
  ('waste', 'overflowing_bin', 'Overflowing Bin',
   'Public waste bin overflowing onto street or footpath'),
  ('waste', 'illegal_dumping', 'Illegal Dumping',
   'Waste dumped in unauthorized location'),
  ('waste', 'construction_debris', 'Construction Debris',
   'Building materials or rubble left on road/footpath'),
  ('waste', 'garbage_burning', 'Garbage Burning',
   'Open burning of waste'),
  ('waste', 'dead_animal', 'Dead Animal',
   'Animal carcass on road or public area')
ON CONFLICT (code) DO NOTHING;
```

No schema changes needed — the `report_type` column added in Phase 2 already
supports arbitrary values.

### 2. Backend — Waste Module

**New directory**: `backend/app/modules/waste/`

```
backend/app/modules/waste/
├── __init__.py                    ← exports router
├── routers/
│   ├── __init__.py
│   └── reports.py                 ← waste report endpoints
├── services/
│   ├── __init__.py
│   └── waste_reporting_service.py ← thin wrapper around shared reporting
└── schemas/
    ├── __init__.py
    └── reports.py                 ← WasteReportCreate schema
```

#### Endpoints

| Method | Path | Auth | Rate Limit | Description |
|--------|------|------|------------|-------------|
| `POST` | `/waste/reports` | `require_auth` | 5/hr | Submit waste report |
| `GET` | `/waste/reports/recent` | None | None | List recent verified waste reports |
| `GET` | `/waste/categories` | None | None | List waste categories from DB |

#### Schema

```python
class WasteReportCreate(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    category: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    severity: int = Field(default=3, ge=1, le=5)
    metadata: dict = Field(default_factory=dict)
```

This is structurally identical to `InfraReportCreate`. If desired, extract a
shared `CivicReportCreate` base class into `app/core/schemas.py`.

#### Service Layer

The `waste_reporting_service.py` delegates to the shared `reporting_service`:

```python
async def create_waste_report(report, db):
    report.report_type = 'waste'
    return await reporting_service.create_report(report, db)

async def get_waste_categories(db):
    # SELECT code, label, description FROM report_categories WHERE module = 'waste'
    ...
```

### 3. Backend — Register Module in `main.py`

```python
from app.modules.waste import router as waste_router
app.include_router(waste_router, prefix="/waste", tags=["Waste Management"])
```

### 4. Backend — Shared Refactoring Opportunity

At this point, three modules (walksafe, infrastructure, waste) share nearly
identical report submission, category listing, and recent-reports retrieval
patterns. Consider extracting a **generic civic reporting service** into
`app/core/`:

```
app/core/
├── civic_report_service.py    ← generic create/list/categorize
└── civic_report_schemas.py    ← CivicReportCreate base model
```

Each module's service becomes a thin wrapper that sets `report_type` and
validates categories against its own module scope.

### 5. Mobile — Waste Reporting Screen

**New files** (following same pattern as Phase 2):

```
mobile/lib/modules/waste/
├── screens/
│   └── waste_report_screen.dart
├── services/
│   └── waste_reporting_api_service.dart
└── widgets/
    └── waste_category_picker.dart
```

**Navigation**: Add "Waste" entry to module switcher alongside Safety and
Infrastructure.

### 6. Impact on Existing Systems

**ResilientSteps safety scoring**: No impact. The risk engine queries
`incident_reports WHERE status='verified'` and uses category-based weights.
Waste categories (overflowing_bin, etc.) don't match any existing weight
category and default to `0.65`. If waste reports should NOT affect pedestrian
safety scores at all, add `AND report_type = 'safety'` to the incident
aggregation query in `reporting_service.py` line 181:

```sql
-- Current:
AND LOWER(COALESCE(report.status, 'pending')) = 'verified'

-- Recommended:
AND LOWER(COALESCE(report.status, 'pending')) = 'verified'
AND report.report_type = 'safety'
```

This is a **critical change** — without it, a verified "Overflowing Bin" report
near a road segment would penalize pedestrian safety scores.

---

## Verification

### Automated Tests

**New file**: `backend/tests/test_waste_reports.py`

Test cases:
- Submit waste report → `report_type='waste'` in DB
- List waste categories → returns 5 categories
- List recent waste reports → returns only `report_type='waste'`
- Admin filter by `report_type=waste` → correct results
- Existing safety and infrastructure reports unaffected
- Safety scoring does NOT include waste reports in incident penalties

```bash
cd backend
python -m pytest tests/test_waste_reports.py -v
python -m pytest tests/ -v  # all tests
```

### Manual Verification

1. `GET /waste/categories` → 5 categories
2. `POST /waste/reports` with `category=overflowing_bin` → success
3. `GET /admin/reports?status=pending&report_type=waste` → only waste reports
4. Verify a waste report → appears in `GET /waste/reports/recent`
5. Waste reports do NOT appear in `GET /reports/recent` (ResilientSteps safety reports)
6. Safety routing scores are unaffected by waste reports

---

## Done Criteria

- [ ] Alembic migration `0004` seeds waste categories
- [ ] `backend/app/modules/waste/` exists with routers, services, schemas
- [ ] `POST /waste/reports` creates waste reports
- [ ] `GET /waste/categories` returns waste categories
- [ ] Safety scoring excludes waste reports (report_type filter added)
- [ ] All existing tests pass
- [ ] New `test_waste_reports.py` passes
- [ ] Mobile waste reporting screen exists (or deferred to Phase 4)

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Waste reports contaminate safety scores | Add `report_type='safety'` filter to `reporting_service.py` incident queries |
| Code duplication across three modules | Extract shared `civic_report_service` into `app/core/` |
| Category code mismatches between DB and mobile | Mobile fetches categories from `/waste/categories` API rather than hardcoding |
| Rate limiter is per-IP across all modules | If needed, namespace rate limiters per module (e.g., `waste_report_limiter`) |
