import unittest
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.walksafe.services import routing_service


class _FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "trip": {
                "legs": [{"shape": "u`rvgA~scqcCsDyA"}],
                "summary": {"length": 1.0, "time": 60.0},
            }
        }


class _FakeClient:
    def __init__(self):
        self.post = AsyncMock(return_value=_FakeResponse())
        self.is_closed = False


class ValhallaPayloadTests(unittest.IsolatedAsyncioTestCase):
    """Regression guard for S-016: the 7.7 km inflation was caused by an
    aggressive pedestrian payload that escaped CI because get_safe_route is
    mocked everywhere else."""

    async def test_pedestrian_payload_is_neutral_with_snap_radius(self):
        fake_client = _FakeClient()
        with patch.object(
            routing_service, "_get_http_client", return_value=fake_client
        ):
            await routing_service.get_safe_route(18.5640, 73.8120, 18.5652, 73.8200)

        fake_client.post.assert_awaited_once()
        url = fake_client.post.await_args.args[0]
        self.assertTrue(url.endswith("/route"))

        payload = fake_client.post.await_args.kwargs["json"]

        locations = payload["locations"]
        self.assertEqual(locations[0]["lat"], 18.5640)
        self.assertEqual(locations[0]["lon"], 73.8120)
        self.assertEqual(locations[1]["lat"], 18.5652)
        self.assertEqual(locations[1]["lon"], 73.8200)
        for location in locations:
            self.assertEqual(location["radius"], 400)

        self.assertEqual(payload["costing"], "pedestrian")
        pedestrian = payload["costing_options"]["pedestrian"]
        self.assertEqual(pedestrian["use_roads"], 0.0)
        self.assertEqual(pedestrian["use_lit"], 0.2)
        self.assertEqual(pedestrian["walkway_factor"], 1.0)
        self.assertEqual(pedestrian["sidewalk_factor"], 1.0)
        self.assertEqual(pedestrian["walking_speed"], 5.0)

        self.assertEqual(payload["directions_options"], {"units": "kilometers"})


if __name__ == "__main__":
    unittest.main()
