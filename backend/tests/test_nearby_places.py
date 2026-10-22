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

    def test_overpass_fails_fast_and_nominatim_gets_the_longer_budget(self):
        client = AsyncMock()
        client.get.side_effect = [
            httpx.HTTPError("Overpass queued forever"),
            httpx.Response(
                200,
                request=httpx.Request("GET", "https://nominatim.openstreetmap.org"),
                json=[
                    {
                        "place_id": 9,
                        "lat": "18.521",
                        "lon": "73.851",
                        "display_name": "Alpha Hospital, Pune",
                    }
                ],
            ),
        ]

        import asyncio

        places = asyncio.run(
            nearby_places_service.find_nearby_places(
                lat=18.52,
                lon=73.85,
                category="hospital",
                radius_m=3000,
                client=client,
            )
        )
        self.assertEqual(places[0]["name"], "Alpha Hospital")
        self.assertEqual(client.get.await_count, 2)
        overpass_timeout = client.get.await_args_list[0].kwargs.get("timeout")
        nominatim_timeout = client.get.await_args_list[-1].kwargs.get("timeout")
        self.assertEqual(
            overpass_timeout, nearby_places_service.OVERPASS_TIMEOUT_SECONDS
        )
        self.assertEqual(
            nominatim_timeout, nearby_places_service.NOMINATIM_TIMEOUT_SECONDS
        )
        # Worst case (Overpass fast-fail + Nominatim budget) must stay below
        # the mobile client cap so the app never times out first.
        self.assertLess(
            nearby_places_service.OVERPASS_TIMEOUT_SECONDS
            + nearby_places_service.NOMINATIM_TIMEOUT_SECONDS,
            25.0,
        )

    def test_nominatim_fallback_is_serialized(self):
        import asyncio

        self.assertIsInstance(
            nearby_places_service._nominatim_lock, asyncio.Lock
        )

    def test_cache_put_evicts_oldest_entries(self):
        import asyncio

        limit = nearby_places_service._CACHE_MAX_ENTRIES
        for index in range(limit + 25):
            nearby_places_service._cache_put(f"key{index}", (0.0, []))
        self.assertEqual(len(nearby_places_service._cache), limit)
        self.assertNotIn("key0", nearby_places_service._cache)
        self.assertIn(
            f"key{limit + 24}", nearby_places_service._cache
        )
        nearby_places_service._cache.clear()

    @staticmethod
    def _element(place_id, lat, lon, tags):
        return {
            "type": "node",
            "id": place_id,
            "lat": lat,
            "lon": lon,
            "tags": tags,
        }

    def test_all_category_classifies_and_caps_results(self):
        import asyncio

        elements = [
            # 10 hospitals (more than the per-category cap of 8)
            *(
                self._element(
                    100 + index,
                    18.52 + index * 0.0001,
                    73.85 + index * 0.0001,
                    {
                        "amenity": "hospital",
                        "name": f"Hospital {index}",
                    },
                )
                for index in range(10)
            ),
            self._element(
                200,
                18.53,
                73.86,
                {"amenity": "police", "name": "Test Police"},
            ),
            self._element(
                201,
                18.54,
                73.87,
                {"railway": "subway_entrance", "name": "Metro A"},
            ),
            self._element(
                202,
                18.55,
                73.88,
                {"highway": "bus_stop", "name": "Bus Stop B"},
            ),
        ]
        client = AsyncMock()

        async def response(*_args, **_kwargs):
            return httpx.Response(
                200,
                request=httpx.Request(
                    "GET", "https://overpass-api.de/api/interpreter"
                ),
                json={"elements": elements},
            )

        client.get.side_effect = response

        async def run():
            return await nearby_places_service.find_nearby_places(
                lat=18.521,
                lon=73.851,
                category="all",
                radius_m=3000,
                client=client,
            )

        places = asyncio.run(run())
        by_category: dict[str, int] = {}
        names: set[str] = set()
        for place in places:
            by_category[place["category"]] = (
                by_category.get(place["category"], 0) + 1
            )
            names.add(place["name"])
        self.assertEqual(
            by_category,
            {
                "hospital": nearby_places_service.ALL_RESULTS_PER_CATEGORY,
                "police": 1,
                "metro": 1,
                "bus": 1,
            },
        )
        # The two farthest hospitals are trimmed by the cap.
        self.assertNotIn("Hospital 0", names)
        self.assertNotIn("Hospital 1", names)
        # The combined query mentions every category filter.
        sent_query = client.get.await_args_list[0].kwargs["params"]["data"]
        for query_fragment in (
            'nwr["amenity"="hospital"]',
            'nwr["amenity"="police"]',
            'nwr["railway"="subway_entrance"]',
            'nwr["highway"="bus_stop"]',
        ):
            self.assertIn(query_fragment, sent_query)

    def test_all_category_nominatim_fallback_survives_partial_failures(self):
        import asyncio

        def nominatim_response(place_id, name):
            return httpx.Response(
                200,
                request=httpx.Request(
                    "GET", "https://nominatim.openstreetmap.org"
                ),
                json=[
                    {
                        "place_id": place_id,
                        "lat": "18.521",
                        "lon": "73.851",
                        "display_name": f"{name}, Pune",
                    }
                ],
            )

        client = AsyncMock()
        client.get.side_effect = [
            httpx.HTTPError("Overpass down"),
            # hospital: success
            nominatim_response(1, "Alpha Hospital"),
            # police: fails
            httpx.HTTPError("Nominatim throttled"),
            # metro: success
            nominatim_response(2, "Metro A"),
            # bus: fails
            httpx.HTTPError("Nominatim throttled"),
        ]

        async def run():
            return await nearby_places_service.find_nearby_places(
                lat=18.521,
                lon=73.851,
                category="all",
                radius_m=3000,
                client=client,
            )

        places = asyncio.run(run())
        self.assertEqual(len(places), 2)
        self.assertEqual(
            sorted(place["name"] for place in places),
            ["Alpha Hospital", "Metro A"],
        )

