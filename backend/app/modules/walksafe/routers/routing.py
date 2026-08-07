import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth_middleware import optional_auth
from app.core.rate_limiter import route_rate_limiter
from app.modules.walksafe.services.risk_engine import score_route
from app.modules.walksafe.services.routing_service import get_safe_route
from app.modules.walksafe.services.safety_zone_service import (
    get_safety_zones as load_safety_zones,
)

router = APIRouter()

# NOTE: This is an in-process cache. It does not survive server restarts
# and is not shared across multiple backend instances.
# For multi-instance deployment, replace with Redis.
# The dict is safe here because these handlers run on the app's asyncio event
# loop. If threaded workers are introduced later, guard access with a lock.
_zones_cache: dict[str, dict[str, Any]] = {}
_ZONES_CACHE_TTL_SECONDS: float = 600.0
_ZONES_CACHE_MAX_SIZE: int = 128


def _zones_cache_key(
    min_lat: float | None,
    max_lat: float | None,
    min_lon: float | None,
    max_lon: float | None,
) -> str:
    def _format(value: float | None) -> str:
        return "none" if value is None else f"{value:.4f}"

    return ",".join(
        (
            _format(min_lat),
            _format(max_lat),
            _format(min_lon),
            _format(max_lon),
        )
    )


def _get_cached_zones(bbox_key: str) -> Optional[dict]:
    cached_entry = _zones_cache.get(bbox_key)
    if cached_entry is None:
        return None

    if (time.time() - float(cached_entry["cached_at"])) >= _ZONES_CACHE_TTL_SECONDS:
        _zones_cache.pop(bbox_key, None)
        return None

    return cached_entry["data"]


def _set_cached_zones(bbox_key: str, data: dict) -> None:
    # Evict oldest entries if cache exceeds max size.
    while len(_zones_cache) >= _ZONES_CACHE_MAX_SIZE:
        oldest_key = min(_zones_cache, key=lambda k: _zones_cache[k]["cached_at"])
        del _zones_cache[oldest_key]

    _zones_cache[bbox_key] = {
        "cached_at": time.time(),
        "data": data,
    }


class Coordinate(BaseModel):
    lat: float
    lon: float


class RouteCoordinates(BaseModel):
    coordinates: List[Coordinate]


@router.get("/route", response_model=Dict[str, List[Dict[str, float]]])
async def get_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    _user: str | None = Depends(optional_auth),
    _rate: None = Depends(route_rate_limiter),
):
    try:
        route = await get_safe_route(start_lat, start_lon, end_lat, end_lon)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "safest": [
            {"lat": float(lat), "lon": float(lon)}
            for lat, lon in route["coordinates"]
        ]
    }


@router.post("/route/risk")
@router.post("/route/segments/safety")
async def route_risk(
    body: RouteCoordinates,
    db: AsyncSession = Depends(get_db),
    _user: str | None = Depends(optional_auth),
    _rate: None = Depends(route_rate_limiter),
):
    coordinates = [(c.lat, c.lon) for c in body.coordinates]
    return await score_route(coordinates, db)


@router.get("/route-safe")
async def route_safe(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    db: AsyncSession = Depends(get_db),
    _user: str | None = Depends(optional_auth),
    _rate: None = Depends(route_rate_limiter),
):
    try:
        route = await get_safe_route(start_lat, start_lon, end_lat, end_lon)
    except RuntimeError as exc:
        message = str(exc)
        if "Cannot connect to Valhalla routing engine" in message:
            raise HTTPException(status_code=503, detail=message) from exc
        raise HTTPException(
            status_code=502,
            detail="No route or safety data found for this route area.",
        ) from exc

    score = await score_route(route["coordinates"], db)
    score["coordinates"] = route["coordinates"]
    score["distance_km"] = route["distance_km"]
    score["duration_minutes"] = route["duration_minutes"]
    return score


@router.get("/safety-zones")
async def safety_zones(
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    bbox_key = _zones_cache_key(min_lat, max_lat, min_lon, max_lon)
    cached = _get_cached_zones(bbox_key)
    if cached is not None:
        return cached

    result = await load_safety_zones(
        db,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
    )
    _set_cached_zones(bbox_key, result)
    return result
