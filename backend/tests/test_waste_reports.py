import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.core.auth_middleware import require_auth


def _make_mock_db(codes):
    """AsyncMock DB whose execute() returns category rows for `codes`.

    Installed as the get_db override so tests never open a live Supabase
    connection (asyncpg connections leak an unawaited cancellation task when
    the test event loop closes — see learning/SOLUTIONS.md S-012).
    """
    mock_rows = [
        MagicMock(
            _mapping={
                "code": code,
                "label": code.replace("_", " ").title(),
                "description": f"{code.replace('_', ' ').title()} category",
                "module": "waste",
            }
        )
        for code in codes
    ]
    mock_result = MagicMock()
    mock_result.fetchall.return_value = mock_rows

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    return mock_db


class WasteReportingTests(unittest.TestCase):
    def setUp(self):
        from app.core.database import get_db
        app.dependency_overrides[get_db] = lambda: _make_mock_db(
            [
                "overflowing_bin",
                "illegal_dumping",
                "construction_debris",
                "garbage_burning",
                "dead_animal",
            ]
        )

    def test_get_waste_categories(self):
        with TestClient(app) as client:
            response = client.get("/waste/categories")

        self.assertEqual(response.status_code, 200)
        categories = response.json()
        codes = [c["code"] for c in categories]
        self.assertEqual(
            codes,
            [
                "overflowing_bin",
                "illegal_dumping",
                "construction_debris",
                "garbage_burning",
                "dead_animal",
            ],
        )
        self.assertEqual(categories[0]["label"], "Overflowing Bin")

    def test_post_waste_report_success(self):
        from app.core.rate_limiter import report_rate_limiter
        app.dependency_overrides[require_auth] = lambda: "user_test_hash"
        app.dependency_overrides[report_rate_limiter] = lambda: None

        mock_created = {
            "id": "202",
            "status": "pending",
            "confidence": 0.5,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "report_type": "waste",
            "severity": 3,
        }
        with patch(
            "app.modules.waste.services.waste_reporting_service.reporting_service.create_report",
            new=AsyncMock(return_value=mock_created),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/waste/reports",
                    json={
                        "lat": 18.52,
                        "lon": 73.85,
                        "category": "overflowing_bin",
                        "description": "Overflowing bin on street corner",
                        "severity": 3,
                    },
                )

        app.dependency_overrides.clear()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["id"], "202")
        self.assertEqual(body["report_type"], "waste")
        self.assertEqual(body["severity"], 3)

    def test_post_waste_report_invalid_category(self):
        app.dependency_overrides[require_auth] = lambda: "user_test_hash"

        with TestClient(app) as client:
            response = client.post(
                "/waste/reports",
                json={
                    "lat": 18.52,
                    "lon": 73.85,
                    "category": "invalid_waste_category",
                    "severity": 3,
                },
            )

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid waste category", response.json()["detail"])

    def test_post_waste_report_unauthenticated(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.post(
                "/waste/reports",
                json={
                    "lat": 18.52,
                    "lon": 73.85,
                    "category": "overflowing_bin",
                },
            )
        self.assertEqual(response.status_code, 401)

    def test_get_recent_waste_reports(self):
        mock_reports = [
            {
                "id": "2",
                "lat": 18.52,
                "lon": 73.85,
                "incident_type": "overflowing_bin",
                "severity": 3,
                "confidence_score": 0.5,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "verified",
            }
        ]

        with patch(
            "app.modules.waste.services.waste_reporting_service.reporting_service.get_recent_reports",
            new=AsyncMock(return_value=mock_reports),
        ):
            with TestClient(app) as client:
                response = client.get("/waste/reports/recent")

        self.assertEqual(response.status_code, 200)
        reports = response.json()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["incident_type"], "overflowing_bin")

    def test_admin_reports_with_waste_report_type_filter(self):
        from app.modules.walksafe.routers.admin import require_admin
        app.dependency_overrides[require_admin] = lambda: None

        mock_rows = [
            MagicMock(
                _mapping={
                    "id": 2,
                    "user_hash": "hash2",
                    "category": "overflowing_bin",
                    "description": "desc",
                    "latitude": 18.52,
                    "longitude": 73.85,
                    "status": "pending",
                    "confidence": 0.5,
                    "submitted_at": datetime.now(timezone.utc),
                    "moderated_at": None,
                    "report_type": "waste",
                    "severity": 3,
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
                "/admin/reports?status=pending&report_type=waste",
                headers={"X-Admin-Key": "test"},
            )

        app.dependency_overrides.clear()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["report_type_filter"], "waste")
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["reports"][0]["report_type"], "waste")
