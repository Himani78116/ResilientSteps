"""Nearby public facilities sourced from OpenStreetMap via Overpass."""

from __future__ import annotations

import math
import time
from typing import Any

import httpx


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MAX_RADIUS_METERS = 5000
MAX_RESULTS = 30
CACHE_TTL_SECONDS = 600.0

CATEGORY_FILTERS: dict[str, tuple[str, ...]] = {
    "hospital": (
        'nwr["amenity"="hospital"]',
        'nwr["healthcare"="hospital"]',
    ),
    "police": ('nwr["amenity"="police"]',),
    "metro": (
        'nwr["railway"="station"]["station"="subway"]',
        'nwr["railway"="subway_entrance"]',
    ),
    "bus": (
        'nwr["highway"="bus_stop"]',
        'nwr["amenity"="bus_station"]',
        'nwr["public_transport"="platform"]["bus"="yes"]',
    ),
}

NOMINATIM_QUERIES: dict[str, str] = {
    "hospital": "hospital",
    "police": "police station",
    "metro": "metro station",
    "bus": "bus stop",
}

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def _cache_key(lat: float, lon: float, category: str, radius_m: int) -> str:
    return f"{lat:.4f}:{lon:.4f}:{category}:{radius_m}"


def _distance_meters(lat: float, lon: float, target_lat: float, target_lon: float) -> float:
    radius = 6_371_000
    lat1, lat2 = math.radians(lat), math.radians(target_lat)
    delta_lat = math.radians(target_lat - lat)
    delta_lon = math.radians(target_lon - lon)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    if isinstance(element.get("lat"), (int, float)) and isinstance(
        element.get("lon"), (int, float)
    ):
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and isinstance(center.get("lat"), (int, float)) and isinstance(
        center.get("lon"), (int, float)
    ):
        return float(center["lat"]), float(center["lon"])
    return None


def _name(tags: dict[str, Any], category: str) -> str:
    value = str(tags.get("name", "")).strip()
    if value:
        return value
    return {
        "hospital": "Unnamed hospital",
        "police": "Unnamed police station",
        "metro": "Unnamed metro station",
        "bus": "Unnamed bus stop",
    }[category]


def _address(tags: dict[str, Any]) -> str | None:
    parts = [
        str(tags[key]).strip()
        for key in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city")
        if tags.get(key)
    ]
    return ", ".join(parts) if parts else None


def _viewbox(lat: float, lon: float, radius_m: int) -> str:
    lat_delta = radius_m / 111_000
    lon_delta = radius_m / (111_000 * max(math.cos(math.radians(lat)), 0.1))
    return ",".join(
        (
            str(lon - lon_delta),
            str(lat + lat_delta),
            str(lon + lon_delta),
            str(lat - lat_delta),
        )
    )


def _place_from_nominatim(
    item: dict[str, Any],
    *,
    category: str,
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    try:
        place_lat = float(item["lat"])
        place_lon = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    display_name = str(item.get("display_name", "")).strip()
    name = display_name.split(",", 1)[0].strip() or _name({}, category)
    return {
        "id": f"nominatim/{item.get('place_id', '')}",
        "name": name,
        "category": category,
        "latitude": place_lat,
        "longitude": place_lon,
        "address": display_name or None,
        "distance_m": round(_distance_meters(lat, lon, place_lat, place_lon)),
    }


async def _find_nominatim_places(
    *,
    lat: float,
    lon: float,
    category: str,
    radius_m: int,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    response = await client.get(
        NOMINATIM_URL,
        params={
            "q": NOMINATIM_QUERIES[category],
            "format": "jsonv2",
            "limit": str(MAX_RESULTS),
            "addressdetails": "1",
            "viewbox": _viewbox(lat, lon, radius_m),
            "bounded": "1",
        },
        headers={
            "User-Agent": "ResilientSteps/1.0",
            "Accept-Language": "en",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Nominatim returned a non-list response.")
    places = [
        place
        for item in payload
        if isinstance(item, dict)
        for place in [
            _place_from_nominatim(
                item,
                category=category,
                lat=lat,
                lon=lon,
            )
        ]
        if place is not None
    ]
    places.sort(key=lambda place: place["distance_m"])
    return places[:MAX_RESULTS]


async def find_nearby_places(
    *,
    lat: float,
    lon: float,
    category: str,
    radius_m: int,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    key = _cache_key(lat, lon, category, radius_m)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    clauses = "\n".join(
        f"  {query}(around:{radius_m},{lat},{lon});"
        for query in CATEGORY_FILTERS[category]
    )
    query = f"[out:json][timeout:10];\n(\n{clauses}\n);\nout center tags;"

    owns_client = client is None
    request_client = client or httpx.AsyncClient()
    try:
        response = await request_client.get(
            OVERPASS_URL,
            params={"data": query},
            headers={"User-Agent": "ResilientSteps/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Overpass returned a non-object response.")
    except (httpx.HTTPError, ValueError) as exc:
        try:
            fallback = await _find_nominatim_places(
                lat=lat,
                lon=lon,
                category=category,
                radius_m=radius_m,
                client=request_client,
            )
            _cache[key] = (time.monotonic(), fallback)
            return fallback
        except (httpx.HTTPError, ValueError) as fallback_exc:
            raise RuntimeError("Nearby places are unavailable right now.") from fallback_exc
    finally:
        if owns_client:
            await request_client.aclose()

    places: list[dict[str, Any]] = []
    seen: set[tuple[float, float]] = set()
    for element in payload.get("elements", []):
        if not isinstance(element, dict):
            continue
        coordinates = _coordinates(element)
        tags = element.get("tags")
        if coordinates is None or not isinstance(tags, dict):
            continue
        place_lat, place_lon = coordinates
        identity = (place_lat, place_lon)
        if identity in seen:
            continue
        seen.add(identity)
        distance = _distance_meters(lat, lon, place_lat, place_lon)
        places.append(
            {
                "id": f"{element.get('type', 'element')}/{element.get('id', '')}",
                "name": _name(tags, category),
                "category": category,
                "latitude": place_lat,
                "longitude": place_lon,
                "address": _address(tags),
                "distance_m": round(distance),
            }
        )

    places.sort(key=lambda place: place["distance_m"])
    result = places[:MAX_RESULTS]
    _cache[key] = (time.monotonic(), result)
    return result
