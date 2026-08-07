import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth_middleware import require_auth


class WalkSafeModuleEndpointTests(unittest.TestCase):
    def setUp(self):
        from app.modules.walksafe.routers.routing import _zones_cache
        _zones_cache.clear()

    def test_walksafe_prefixed_route_risk(self):
        mocked_payload = {
            "safety_score": 80.0,
            "segment_count": 1,
            "matched_segment_count": 1,
            "unmatched_segment_count": 0,
            "applied_incident_count": 0,
            "incident_affected_segment_count": 0,
            "dataset_version": "roads-v1",
            "segments": [],
            "warning": None,
        }

        with patch(
            "app.modules.walksafe.routers.routing.score_route",
            new=AsyncMock(return_value=mocked_payload),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/walksafe/route/risk",
                    json={
                        "coordinates": [
                            {"lat": 18.52, "lon": 73.85},
                            {"lat": 18.53, "lon": 73.86},
                        ]
                    },
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["safety_score"], 80.0)

    def test_walksafe_prefixed_safety_zones(self):
        mocked_payload = {
            "type": "FeatureCollection",
            "features": [],
            "dataset_version": "zones-v1",
        }

        with patch(
            "app.modules.walksafe.routers.routing.load_safety_zones",
            new=AsyncMock(return_value=mocked_payload),
        ):
            with TestClient(app) as client:
                response = client.get("/walksafe/safety-zones")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["type"], "FeatureCollection")

    def test_walksafe_prefixed_reports(self):
        app.dependency_overrides[require_auth] = lambda: "user-1"
        try:
            with patch(
                "app.modules.walksafe.routers.reports.reporting_service.create_report",
                new=AsyncMock(return_value={"id": "report-99", "status": "received"}),
            ):
                with TestClient(app) as client:
                    response = client.post(
                        "/walksafe/reports",
                        json={
                            "user_hash": "user-1",
                            "incident_type": "Poor lighting",
                            "severity": 3,
                            "lat": 18.52,
                            "lon": 73.85,
                        },
                    )
        finally:
            app.dependency_overrides.pop(require_auth, None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "report-99")


if __name__ == "__main__":
    unittest.main()
