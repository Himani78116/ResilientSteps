import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth_middleware import require_auth
from app.modules.infrastructure.services.infra_reporting_service import (
    infra_reporting_service,
)
from app.modules.walksafe.services.reporting_service import reporting_service


class InfrastructureReportingTests(unittest.TestCase):
    def test_get_infra_categories(self):
        with TestClient(app) as client:
            response = client.get("/infra/categories")

        self.assertEqual(response.status_code, 200)
        categories = response.json()
        self.assertTrue(len(categories) >= 8)
        codes = [c["code"] for c in categories]
        self.assertIn("pothole", codes)
        self.assertIn("streetlight", codes)
        self.assertIn("footpath", codes)

    def test_post_infra_report_success(self):
        from app.core.rate_limiter import report_rate_limiter
        app.dependency_overrides[require_auth] = lambda: "user_test_hash"
        app.dependency_overrides[report_rate_limiter] = lambda: None
        mock_created = {
            "id": "101",
            "status": "pending",
            "confidence": 0.5,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "report_type": "infrastructure",
            "severity": 4,
        }

        with patch(
            "app.modules.infrastructure.services.infra_reporting_service.reporting_service.create_report",
            new=AsyncMock(return_value=mock_created),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/infra/reports",
                    json={
                        "lat": 18.52,
                        "lon": 73.85,
                        "category": "pothole",
                        "description": "Large pothole on main street",
                        "severity": 4,
                    },
                )

        app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], "101")
        self.assertEqual(body["report_type"], "infrastructure")
        self.assertEqual(body["severity"], 4)

    def test_post_infra_report_invalid_category(self):
        app.dependency_overrides[require_auth] = lambda: "user_test_hash"

        with TestClient(app) as client:
            response = client.post(
                "/infra/reports",
                json={
                    "lat": 18.52,
                    "lon": 73.85,
                    "category": "invalid_category_xyz",
                    "severity": 3,
                },
            )

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid infrastructure category", response.json()["detail"])

    def test_post_infra_report_unauthenticated(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.post(
                "/infra/reports",
                json={
                    "lat": 18.52,
                    "lon": 73.85,
                    "category": "pothole",
                },
            )
        self.assertEqual(response.status_code, 401)

    def test_get_recent_infra_reports(self):
        mock_reports = [
            {
                "id": "1",
                "lat": 18.52,
                "lon": 73.85,
                "incident_type": "pothole",
                "severity": 4,
                "confidence_score": 0.5,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "verified",
            }
        ]

        with patch(
            "app.modules.infrastructure.services.infra_reporting_service.reporting_service.get_recent_reports",
            new=AsyncMock(return_value=mock_reports),
        ):
            with TestClient(app) as client:
                response = client.get("/infra/reports/recent")

        self.assertEqual(response.status_code, 200)
        reports = response.json()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident_type"], "pothole")

    def test_admin_reports_with_report_type_filter(self):
        from app.modules.walksafe.routers.admin import require_admin
        app.dependency_overrides[require_admin] = lambda: None

        mock_rows = [
            MagicMock(
                _mapping={
                    "id": 1,
                    "user_hash": "hash1",
                    "category": "pothole",
                    "description": "desc",
                    "latitude": 18.52,
                    "longitude": 73.85,
                    "status": "pending",
                    "confidence": 0.5,
                    "submitted_at": datetime.now(timezone.utc),
                    "moderated_at": None,
                    "report_type": "infrastructure",
                    "severity": 4,
                }
            )
        ]

        async def mock_execute(query, params=None):
            m = MagicMock()
            m.fetchall.return_value = mock_rows
            return m

        mock_db = AsyncMock()
        mock_db.execute = mock_execute

        from app.core.database import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get(
                "/admin/reports?status=pending&report_type=infrastructure",
                headers={"X-Admin-Key": "test"},
            )

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["report_type_filter"], "infrastructure")
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["reports"][0]["report_type"], "infrastructure")
