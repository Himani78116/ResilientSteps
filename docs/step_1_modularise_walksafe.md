# Phase 1 — Modularise WalkSafe

## Goal

Restructure the existing WalkSafe codebase so that safety routing becomes one
self-contained module inside a broader CityOS platform. No new features are
added — this phase is purely structural. After Phase 1, a second module (e.g.,
infrastructure reporting) should be addable without touching any WalkSafe code.

## Prerequisites

- The BASELINE.md document has been read and understood.
- The Supabase database is running and `alembic upgrade head` has been applied.
- All existing tests pass: `cd backend && python -m pytest tests/ -v`

---

## Current State (as-is)

### Backend

Everything lives in flat directories. Routers, services, and schemas are not
namespaced by domain — they are just loose files:

```
backend/app/
├── main.py                         ← single FastAPI app, no module registration
├── routers/
│   ├── routing.py                  ← safety routing endpoints
│   ├── reports.py                  ← incident + emergency endpoints
│   └── admin.py                    ← moderation endpoints
├── services/
│   ├── routing_service.py          ← Valhalla client
│   ├── risk_engine.py              ← route safety scorer
│   ├── safety_dataset_cache.py     ← STRtree spatial cache
│   ├── safety_zone_service.py      ← zone GeoJSON serving
│   ├── reporting_service.py        ← report + alert persistence
│   ├── auth_middleware.py          ← JWT verification
│   └── rate_limiter.py             ← token-bucket limiter
├── schemas/
│   └── reports.py                  ← Pydantic models
└── db/
    ├── session.py                  ← async engine + session
    └── supabase_client.py          ← Supabase client
```

### Mobile

The Flutter app also has no module boundaries. All screens and services are
safety-specific but live in generic directories:

```
mobile/lib/
├── screens/          ← 11 screens, all WalkSafe-specific
├── services/         ← 14 services, all WalkSafe-specific
├── widgets/          ← 11 widgets, all WalkSafe-specific
├── models/           ← 6 models, all WalkSafe-specific
├── controllers/      ← 1 controller (navigation)
├── config/           ← app_config.dart
├── domain/           ← empty subdirs (entities/, repositories/)
├── data/             ← empty subdirs (datasources/, repositories/)
└── core/             ← empty
```

---

## Changes Required

### 1. Backend — Create Module Directory Structure

Create a `modules/` directory under `backend/app/` and move WalkSafe code into
a `walksafe/` submodule.

**Target structure:**

```
backend/app/
├── main.py                              ← modified: registers modules
├── core/                                ← NEW: shared infrastructure
│   ├── __init__.py
│   ├── auth_middleware.py               ← MOVED from services/
│   ├── rate_limiter.py                  ← MOVED from services/
│   └── database.py                      ← MOVED+RENAMED from db/session.py
├── db/                                  ← kept for backward compat; re-exports from core
│   ├── __init__.py                      ← existing
│   ├── session.py                       ← rewritten to import from core/database.py
│   └── supabase_client.py              ← existing
├── modules/                             ← NEW: module registry
│   ├── __init__.py                      ← module discovery/registration helper
│   └── walksafe/                        ← NEW: WalkSafe module
│       ├── __init__.py                  ← exports router
│       ├── routers/
│       │   ├── __init__.py
│       │   ├── routing.py              ← MOVED from app/routers/routing.py
│       │   ├── reports.py              ← MOVED from app/routers/reports.py
│       │   └── admin.py               ← MOVED from app/routers/admin.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── routing_service.py     ← MOVED from app/services/
│       │   ├── risk_engine.py         ← MOVED from app/services/
│       │   ├── safety_dataset_cache.py ← MOVED from app/services/
│       │   ├── safety_zone_service.py ← MOVED from app/services/
│       │   └── reporting_service.py   ← MOVED from app/services/
│       └── schemas/
│           ├── __init__.py
│           └── reports.py             ← MOVED from app/schemas/
└── routers/                             ← KEPT: backward-compat stubs that re-export
```

### 2. Backend — Module Registration Pattern

Modify `backend/app/main.py` to discover and register modules:

```python
# Current (main.py lines 72-74):
app.include_router(admin_router)
app.include_router(routing.router)
app.include_router(reports.router)

# Target:
from app.modules.walksafe import router as walksafe_router
app.include_router(walksafe_router, prefix="/walksafe", tags=["WalkSafe"])

# Also keep root-level aliases for backward compatibility:
app.include_router(walksafe_router)  # no prefix = same URLs as today
```

This ensures **zero breaking changes** to the existing API surface. The
`/route`, `/reports`, `/admin/reports` endpoints continue to work. New modules
added later will have their own prefix (e.g., `/infra`, `/waste`).

### 3. Backend — Shared Core Extraction

The following services are **not WalkSafe-specific** and should live in
`app/core/` so future modules can reuse them:

| File | Current Location | New Location | Reason |
|------|-----------------|-------------|--------|
| `auth_middleware.py` | `app/services/` | `app/core/` | All modules need JWT auth |
| `rate_limiter.py` | `app/services/` | `app/core/` | All modules need rate limiting |
| `session.py` | `app/db/` | `app/core/database.py` | All modules need DB access |

**Import updates required**: Every file that imports from `app.services.auth_middleware`
must be updated to import from `app.core.auth_middleware`. Use re-exports in the
old locations for backward compatibility.

Files that import auth:
- `app/routers/routing.py` (lines 9): `from app.services.auth_middleware import optional_auth`
- `app/routers/reports.py` (line 7): `from app.services.auth_middleware import require_auth`

Files that import rate limiter:
- `app/routers/routing.py` (line 10): `from app.services.rate_limiter import route_rate_limiter`
- `app/routers/reports.py` (line 8): `from app.services.rate_limiter import emergency_rate_limiter, report_rate_limiter`

Files that import session:
- `app/routers/routing.py` (line 8): `from app.db.session import get_db`
- `app/routers/reports.py` (line 10): `from app.db.session import get_db`
- `app/routers/admin.py` (line 29): `from app.db.session import get_db`
- `app/main.py` (line 12): `from app.db.session import AsyncSessionLocal`

### 4. Backend — Update Test Imports

All 8 test files in `backend/tests/` import from `app.routers.*` and
`app.services.*`. After moving files, these imports must be updated **or** the
old locations must re-export. The recommended approach is **re-export stubs** to
avoid breaking tests while the migration is in progress:

```python
# backend/app/services/auth_middleware.py (stub)
from app.core.auth_middleware import *  # re-export everything
```

### 5. Mobile — Module Boundaries (Minimal)

The mobile app does not need heavy restructuring in Phase 1. Create a
`modules/` directory as a namespace marker and move the empty `domain/` and
`data/` directories into it. Rename the existing directories:

```
mobile/lib/
├── modules/
│   └── walksafe/
│       ├── screens/       ← current screens/ (rename only)
│       ├── widgets/       ← current widgets/ (rename only)
│       └── services/      ← current services/ (rename only)
├── models/                ← keep shared
├── controllers/           ← keep shared
├── config/                ← keep shared
└── core/                  ← keep shared (currently empty)
```

**Alternatively**: If this is too disruptive for the Flutter build, you may
defer mobile restructuring to Phase 2 and only restructure the backend in
Phase 1. The key architectural win is on the backend.

### 6. Database — No Changes

No schema changes in Phase 1. The tables remain exactly as they are. No new
Alembic migration is needed.

---

## Verification

### Automated Tests

```bash
# All existing tests must pass with zero changes to assertions:
cd backend
python -m pytest tests/ -v

# Flutter analysis must pass:
cd mobile
flutter analyze lib/
```

### Manual Verification

1. Start the backend: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Confirm `/` returns `{"message": "WalkSafe API is running", "status": "online"}`
3. Confirm `/route-safe?start_lat=18.52&start_lon=73.85&end_lat=18.53&end_lon=73.86` returns a route with safety scores (requires Valhalla running)
4. Confirm `/safety-zones` returns a GeoJSON FeatureCollection
5. Confirm `/admin/reports?status=pending` works with the correct `X-Admin-Key`

---

## Done Criteria

- [ ] `backend/app/core/` exists with `auth_middleware.py`, `rate_limiter.py`, `database.py`
- [ ] `backend/app/modules/walksafe/` exists with all WalkSafe routers, services, schemas
- [ ] `backend/app/main.py` registers the WalkSafe module via `include_router`
- [ ] All existing API endpoints return identical responses to pre-refactor
- [ ] All 8 existing test files pass without modification to test logic
- [ ] `flutter analyze lib/` passes if mobile restructuring is included
- [ ] No new database migration required

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Import breakage across 8 test files | Use re-export stubs in old locations |
| Mobile restructuring breaks Flutter build | Defer mobile restructuring to Phase 2 if needed |
| Circular imports between modules and core | Core must never import from modules; modules import from core |
| `safety_dataset_cache` singleton shared across modules | Keep in `walksafe/services/`; if a future module needs it, extract to core then |
