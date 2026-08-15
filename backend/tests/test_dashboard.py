import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.modules.walksafe.routers.admin import require_admin


class DashboardTests(unittest.TestCase):
    def test_dashboard_endpoints_require_admin_auth(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            res_summary = client.get("/dashboard/summary")
            res_invalid_key = client.get("/dashboard/summary", headers={"X-Admin-Key": "wrong"})

        # Missing header returns 422, invalid key returns 403
        self.assertEqual(res_summary.status_code, 422)
        self.assertEqual(res_invalid_key.status_code, 403)

    def test_city_summary(self):
        app.dependency_overrides[require_admin] = lambda: None

        mock_rows = [
            MagicMock(
                _mapping={
                    "report_type": "safety",
                    "status": "pending",
                    "severity": 3,
                    "cnt": 5,
                }
            ),
            MagicMock(
                _mapping={
                    "report_type": "infrastructure",
                    "status": "verified",
                    "severity": 4,
                    "cnt": 2,
                }
            ),
        ]

        async def mock_execute(query, params=None):
            m = MagicMock()
            m.fetchall.return_value = mock_rows
            m.fetchone.return_value = MagicMock(_mapping={"avg_hours": 1.5})
            return m

        mock_db = AsyncMock()
        mock_db.execute = mock_execute

        from app.core.database import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.get("/dashboard/summary", headers={"X-Admin-Key": "test"})

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_reports"], 7)
        self.assertEqual(data["pending_count"], 5)
        self.assertEqual(data["verified_count"], 2)
        self.assertEqual(data["by_type"]["safety"], 5)
        self.assertEqual(data["by_type"]["infrastructure"], 2)
        self.assertEqual(data["average_verification_hours"], 1.5)

    def test_ward_summaries(self):
        app.dependency_overrides[require_admin] = lambda: None

        mock_rows = [
            MagicMock(
                _mapping={
                    "ward_id": "WARD_01",
                    "ward_name": "Kasba Peth",
                    "report_type": "safety",
                    "status": "verified",
                    "report_count": 3,
                    "avg_severity": 3.5,
                    "latest_report_at": datetime.now(timezone.utc),
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
            response = client.get("/dashboard/wards", headers={"X-Admin-Key": "test"})

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        wards = response.json()
        self.assertEqual(len(wards), 1)
        self.assertEqual(wards[0]["ward_id"], "WARD_01")
        self.assertEqual(wards[0]["ward_name"], "Kasba Peth")

    def test_trends_endpoint(self):
        app.dependency_overrides[require_admin] = lambda: None

        mock_rows = [
            MagicMock(
                _mapping={
                    "date": "2026-08-15",
                    "report_type": "safety",
                    "count": 4,
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
            response = client.get("/dashboard/trends?since=2026-08-01", headers={"X-Admin-Key": "test"})

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        trends = response.json()
        self.assertEqual(len(trends), 1)
        self.assertEqual(trends[0]["date"], "2026-08-15")

    def test_export_csv_and_json(self):
        app.dependency_overrides[require_admin] = lambda: None

        mock_rows = [
            MagicMock(
                _mapping={
                    "id": "1",
                    "user_hash": "hash1",
                    "category": "pothole",
                    "description": "desc",
                    "latitude": 18.52,
                    "longitude": 73.85,
                    "status": "pending",
                    "confidence": 0.5,
                    "severity": 4,
                    "report_type": "infrastructure",
                    "submitted_at": datetime.now(timezone.utc),
                    "moderated_at": None,
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
            res_csv = client.get("/dashboard/export?format=csv", headers={"X-Admin-Key": "test"})
            res_json = client.get("/dashboard/export?format=json", headers={"X-Admin-Key": "test"})

        app.dependency_overrides.clear()
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers["content-type"])
        self.assertIn("pothole", res_csv.text)

        self.assertEqual(res_json.status_code, 200)
        self.assertIn("application/json", res_json.headers["content-type"])
        self.assertIn("pothole", res_json.text)

    def test_refresh_summary_view(self):
        app.dependency_overrides[require_admin] = lambda: None

        mock_db = AsyncMock()
        from app.core.database import get_db
        app.dependency_overrides[get_db] = lambda: mock_db

        with TestClient(app) as client:
            response = client.post("/dashboard/refresh-summary", headers={"X-Admin-Key": "test"})

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        self.assertIn("refreshed successfully", response.json()["message"])
