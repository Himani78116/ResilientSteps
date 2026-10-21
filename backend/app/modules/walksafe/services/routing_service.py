import os

import httpx
import polyline
from dotenv import load_dotenv

load_dotenv()

VALHALLA_BASE_URL = os.environ.get("VALHALLA_BASE_URL", "http://localhost:8002")
VALHALLA_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=5.0)

# Module-level client — reuses TCP connections across requests.
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=VALHALLA_TIMEOUT)
    return _http_client


async def get_safe_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> dict:
    """
    Fetch a pedestrian route from Valhalla.
    Returns decoded polyline coordinates and route metadata.

    The costing is kept near-neutral (roads are fine, no strong lit/walkway
    preference): aggressive penalties such as use_lit=1.0 or use_roads=0.2
    made Valhalla take long walkway-heavy detours in Pune, which reported
    ~7.7 km for trips that are ~1 km as the crow flies.

    Each location carries an explicit `radius` so a pin placed inside a
    large campus (no routable edge within it) cannot snap to an edge many
    km away — Valhalla returns an error instead, and the caller surfaces
    "no route found" rather than a wildly inflated trip.
    """
    payload = {
        "locations": [
            {"lat": start_lat, "lon": start_lon, "radius": 400},
            {"lat": end_lat, "lon": end_lon, "radius": 400},
        ],
        "costing": "pedestrian",
        "costing_options": {
            "pedestrian": {
                "use_lit": 0.2,
                "use_roads": 0.0,
                "walkway_factor": 1.0,
                "sidewalk_factor": 1.0,
                "walking_speed": 5.0,
            }
        },
        "directions_options": {"units": "kilometers"},
    }

    client = _get_http_client()
    try:
        response = await client.post(
            f"{VALHALLA_BASE_URL}/route",
            json=payload,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            "Cannot connect to Valhalla routing engine. "
            "Make sure Docker is running and Valhalla started with: "
            "docker compose -f backend/docker-compose.yml up valhalla"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Valhalla returned an error: {exc.response.text}"
        ) from exc

    data = response.json()
    encoded = data["trip"]["legs"][0]["shape"]
    coordinates = polyline.decode(encoded, precision=6)
    summary = data["trip"]["summary"]

    return {
        "coordinates": coordinates,
        "distance_km": summary["length"],
        "duration_minutes": summary["time"] / 60,
        "safety_score": None,
    }
