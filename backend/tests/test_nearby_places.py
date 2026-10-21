import unittest
from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.modules.walksafe.services import nearby_places_service


class NearbyPlacesTests(unittest.TestCase):
    def setUp(self):
        nearby_places_service._cache.clear()

    def test_rejects_unknown_category(self):
        with TestClient(app) as client:
            response = client.get(
                "/nearby-places?lat=18.52&lon=73.85&category=airport"
            )
        self.assertEqual(response.status_code, 400)

    def test_rejects_large_radius(self):
        with TestClient(app) as client:
            response = client.get(
                "/nearby-places?lat=18.52&lon=73.85&category=hospital&radius_m=5001"
            )
        self.assertEqual(response.status_code, 422)

    async def _response(self, *args, **kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("POST", "https://overpass-api.de/api/interpreter"),
            json={
                "elements": [
                    {
                        "type": "node",
                        "id": 123,
                        "lat": 18.521,
                        "lon": 73.851,
                        "tags": {
                            "name": "Test Hospital",
                            "addr:street": "Test Road",
                        },
                    }
                ]
            },
        )

    def test_normalizes_and_sorts_overpass_results(self):
        client = AsyncMock()
        client.get.side_effect = self._response

        async def run():
            return await nearby_places_service.find_nearby_places(
                lat=18.52,
                lon=73.85,
                category="hospital",
                radius_m=3000,
                client=client,
            )

        import asyncio

        places = asyncio.run(run())
        self.assertEqual(places[0]["name"], "Test Hospital")
        self.assertEqual(places[0]["id"], "node/123")
        self.assertEqual(places[0]["address"], "Test Road")
        self.assertGreater(places[0]["distance_m"], 0)

    def test_falls_back_to_nominatim_when_overpass_fails(self):
        client = AsyncMock()
        client.get.side_effect = [
            httpx.HTTPStatusError(
                "Overpass unavailable",
                request=httpx.Request("GET", "https://overpass-api.de"),
                response=httpx.Response(502),
            ),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://nominatim.openstreetmap.org"),
                json=[
                    {
                        "place_id": 5,
                        "lat": "18.438",
                        "lon": "73.810",
                        "display_name": "City Police Station, Pune",
                    }
                ],
            ),
        ]

        import asyncio

        places = asyncio.run(
            nearby_places_service.find_nearby_places(
                lat=18.4379,
                lon=73.8099,
                category="police",
                radius_m=3000,
                client=client,
            )
        )
        self.assertEqual(places[0]["name"], "City Police Station")
        self.assertEqual(places[0]["category"], "police")
