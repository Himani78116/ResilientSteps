import json
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.reports import EmergencyAlertCreate
from app.services.auth_middleware import require_auth
from app.services.reporting_service import ReportingService


class _FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping


class _FakeResult:
    def __init__(self, mapping):
        self._mapping = mapping

    def fetchone(self):
        return _FakeRow(self._mapping)


class _FakeAsyncSession:
    def __init__(self):
        self.calls = []

    async def execute(self, query, params=None):
        query_text = str(query)
        self.calls.append((query_text, params))
        if "INSERT INTO emergency_alerts" in query_text:
            return _FakeResult(
                {
                    "id": "emergency-1",
                    "status": "triggered",
                    "created_at": datetime(2026, 4, 3, tzinfo=timezone.utc),
                    "contacts_notified": 2,
                    "metadata": {},
                }
            )
        return _FakeResult({})


class EmergencyEndpointTests(unittest.TestCase):
    def test_report_emergency_alias_returns_notification_summary(self):
        app.dependency_overrides[require_auth] = lambda: "user-1"
        try:
            with patch(
                "app.routers.reports.reporting_service.create_emergency_alert",
                new=AsyncMock(
                    return_value={
                        "id": "emergency-1",
                        "status": "triggered",
                        "created_at": "2026-04-03T12:00:00Z",
                        "message": "Emergency trigger from mobile app",
                        "contacts_notified": 2,
                        "trusted_contacts": [
                            "sister@walksafe.local",
                            "roommate@walksafe.local",
                        ],
                    }
                ),
            ):
                with TestClient(app) as client:
                    response = client.post(
                        "/reports/emergency",
                        json={
                            "user_hash": "user-1",
                            "lat": 18.52,
                            "lon": 73.85,
                            "message": "Help needed",
                            "trusted_contacts": [
                                "sister@walksafe.local",
                                "roommate@walksafe.local",
                            ],
                            "contacts_notified": 2,
                            "metadata": {},
                        },
                    )
        finally:
            app.dependency_overrides.pop(require_auth, None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": "emergency-1",
                "status": "triggered",
                "created_at": "2026-04-03T12:00:00Z",
                "message": "Emergency trigger from mobile app",
                "contacts_notified": 2,
                "trusted_contacts": [
                    "sister@walksafe.local",
                    "roommate@walksafe.local",
                ],
            },
        )


class ReportingServiceEmergencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_emergency_alert_normalizes_contacts(self):
        session = _FakeAsyncSession()

        created = await ReportingService().create_emergency_alert(
            EmergencyAlertCreate(
                user_hash="user-999",
                lat=18.52,
                lon=73.85,
                message="Need help",
                trusted_contacts=[
                    " sister@walksafe.local ",
                    "roommate@walksafe.local",
                    "SISTER@walksafe.local",
                    "",
                ],
                contacts_notified=99,
                metadata={"source": "test"},
            ),
            session,
        )

        self.assertEqual(created["id"], "emergency-1")
        self.assertEqual(created["status"], "triggered")
        self.assertEqual(created["message"], "Need help")
        self.assertEqual(
            created["trusted_contacts"],
            ["sister@walksafe.local", "roommate@walksafe.local"],
        )

        insert_params = next(
            params
            for query, params in session.calls
            if "INSERT INTO emergency_alerts" in query
        )
        self.assertEqual(insert_params["contacts_notified"], 2)
        metadata = json.loads(insert_params["metadata"])
        self.assertEqual(metadata["source"], "test")
        self.assertEqual(
            metadata["trusted_contacts"],
            ["sister@walksafe.local", "roommate@walksafe.local"],
        )
        self.assertEqual(
            metadata["trusted_contacts_notified"],
            ["sister@walksafe.local", "roommate@walksafe.local"],
        )


if __name__ == "__main__":
    unittest.main()
