"""Open-Meteo weather fetching and heat-penalty scoring.

Used by Phase 8 route scoring. Phase 7 only requires the service to parse,
fetch and cache — nothing calls it yet.

Open-Meteo is keyless: no API key or account is needed. The forecast endpoint
simply accepts latitude/longitude query parameters.

Heat is fetched live per request (hourly cadence); failures degrade to None so
route scoring can skip the heat term.
"""

import logging
import time

import httpx

LOGGER = logging.getLogger(__name__)

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_TTL_SECONDS = 900.0
CURRENT_FIELDS = "temperature_2m,apparent_temperature,relative_humidity_2m,uv_index,is_day"

WEATHER_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)

MAX_HEAT_PENALTY = 40.0

HEAT_TIERS = [   # (apparent_temp_c_min, penalty) — descending
    (42.0, 30.0),   # extreme heat — strongly discourage walking
    (38.0, 20.0),
    (32.0, 12.0),
    (28.0, 5.0),
]
UV_TIER_THRESHOLD = 8.0
UV_PENALTY = 5.0

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=WEATHER_TIMEOUT)
    return _http_client


def _as_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_heat_penalty(apparent_c: float | None, uv_index: float | None) -> float:
    penalty = 0.0
    if apparent_c is not None:
        for threshold, tier_penalty in HEAT_TIERS:   # descending
            if apparent_c >= threshold:
                penalty = tier_penalty
                break
    if uv_index is not None and uv_index >= UV_TIER_THRESHOLD:
        penalty += UV_PENALTY
    return min(MAX_HEAT_PENALTY, penalty)


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


def _current_hour_key() -> int:
    return int(time.time() // 3600)


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

    def _get_cached(self, key: tuple) -> dict | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        stored_at, parsed = entry
        if time.monotonic() - stored_at >= WEATHER_CACHE_TTL_SECONDS:
            return None
        return parsed

    def _set_cached(self, key: tuple, parsed: dict) -> None:
        self._cache[key] = (time.monotonic(), parsed)

    async def _fetch(self, lat: float, lon: float) -> dict | None:
        client = self._client if self._client is not None else _get_http_client()
        try:
            response = await client.get(
                OPEN_METEO_BASE_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": CURRENT_FIELDS,
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            LOGGER.warning("Open-Meteo request failed; heat term will be skipped.", exc_info=True)
            return None


weather_service = WeatherService()
