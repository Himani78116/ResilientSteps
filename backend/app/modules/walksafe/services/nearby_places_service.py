"""Nearby public facilities sourced from OpenStreetMap via Overpass."""

from __future__ import annotations

import asyncio
import math
import time
from typing import Any

import httpx


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MAX_RADIUS_METERS = 5000
MAX_RESULTS = 30
# Fetching every category at once ("all") keeps one Overpass round-trip; the
# cap prevents a busy area from blowing up the results bottom sheet.
ALL_CATEGORY = "all"
ALL_RESULTS_PER_CATEGORY = 8
CACHE_TTL_SECONDS = 600.0
# Fast-fail Overpass so the worst case (Overpass timeout + Nominatim fallback)
# stays below the mobile client's 25 s budget (S-028).
OVERPASS_TIMEOUT_SECONDS = 8.0
NOMINATIM_TIMEOUT_SECONDS = 12.0
_CACHE_MAX_ENTRIES = 256

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
# Nominatim allows at most ~1 request per second; a fallback burst from the
# two-anchor flow would otherwise fire two parallel GETs.
_nominatim_lock = asyncio.Lock()


def _cache_key(lat: float, lon: float, category: str, radius_m: int) -> str:
    return f"{lat:.4f}:{lon:.4f}:{category}:{radius_m}"


def _cache_put(
    key: str, value: tuple[float, list[dict[str, Any]]]
) -> None:
    if key in _cache:
        _cache.pop(key)
    _cache[key] = value
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))


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


def _classify_tags(tags: dict[str, Any]) -> str | None:
    """Maps OSM tags back to a category; must mirror CATEGORY_FILTERS."""
    amenity = str(tags.get("amenity", ""))
    if amenity == "hospital" or str(tags.get("healthcare", "")) == "hospital":
        return "hospital"
    if amenity == "police":
        return "police"
    railway = str(tags.get("railway", ""))
    if railway == "subway_entrance" or (
        railway == "station" and str(tags.get("station", "")) == "subway"
    ):
        return "metro"
    if (
        str(tags.get("highway", "")) == "bus_stop"
        or amenity == "bus_station"
        or (
            str(tags.get("public_transport", "")) == "platform"
            and str(tags.get("bus", "")) == "yes"
        )
    ):
        return "bus"
    return None


def _cap_per_category(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sorts buckets per category by distance and trims each to the cap."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for place in places:
        buckets.setdefault(place["category"], []).append(place)
    result: list[dict[str, Any]] = []
    for bucket in buckets.values():
        bucket.sort(key=lambda place: place["distance_m"])
        result.extend(bucket[:ALL_RESULTS_PER_CATEGORY])
    return result


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
    response: httpx.Response
    async with _nominatim_lock:
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
            timeout=NOMINATIM_TIMEOUT_SECONDS,
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
    return places


async def _find_nominatim_places_all(
    *,
    lat: float,
    lon: float,
    radius_m: int,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    """Nominatim fallback for category=all. Queries each category in turn
    (the shared lock keeps Nominatim at ~1 req/s) and merges the buckets."""
    merged: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    failures = 0
    for category in NOMINATIM_QUERIES:
        try:
            items = await _find_nominatim_places(
                lat=lat,
                lon=lon,
                category=category,
                radius_m=radius_m,
                client=client,
            )
            buckets_at_cap = 0
            for place in items:
                bucket = counts.get(place["category"], 0)
                if bucket < ALL_RESULTS_PER_CATEGORY:
                    merged.append(place)
                    counts[place["category"]] = bucket + 1
                else:
                    buckets_at_cap += 1
                    if buckets_at_cap > MAX_RESULTS:
                        break
        except (httpx.HTTPError, ValueError):
            failures += 1
    if failures == len(NOMINATIM_QUERIES):
        raise RuntimeError("Nearby places are unavailable right now.")
    return merged


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

    if category == ALL_CATEGORY:
        filters: tuple[str, ...] = tuple(
            query for queries in CATEGORY_FILTERS.values() for query in queries
        )
    else:
        filters = CATEGORY_FILTERS[category]
    clauses = "\n".join(
        f"  {query}(around:{radius_m},{lat},{lon});" for query in filters
    )
    query = f"[out:json][timeout:10];\n(\n{clauses}\n);\nout center tags;"

    owns_client = client is None
    request_client = client or httpx.AsyncClient()
    try:
        response = await request_client.get(
            OVERPASS_URL,
            params={"data": query},
            headers={"User-Agent": "ResilientSteps/1.0"},
            timeout=OVERPASS_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Overpass returned a non-object response.")
    except (httpx.HTTPError, ValueError) as exc:
        try:
            if category == ALL_CATEGORY:
                fallback = await _find_nominatim_places_all(
                    lat=lat,
                    lon=lon,
                    radius_m=radius_m,
                    client=request_client,
                )
            else:
                fallback = await _find_nominatim_places(
                    lat=lat,
                    lon=lon,
                    category=category,
                    radius_m=radius_m,
                    client=request_client,
                )
            fallback = fallback[:MAX_RESULTS]
            _cache_put(key, (time.monotonic(), fallback))
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
        place_category = (
            category if category != ALL_CATEGORY else _classify_tags(tags)
        )
        if place_category is None:
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
                "name": _name(tags, place_category),
                "category": place_category,
                "latitude": place_lat,
                "longitude": place_lon,
                "address": _address(tags),
                "distance_m": round(distance),
            }
        )

    places.sort(key=lambda place: place["distance_m"])
    result = (
        _cap_per_category(places) if category == ALL_CATEGORY else places[:MAX_RESULTS]
    )
    _cache_put(key, (time.monotonic(), result))
    return result
