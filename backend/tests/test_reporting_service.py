import json
import unittest
from datetime import datetime, timezone

from app.schemas.reports import EmergencyAlertCreate, ReportCreate, TrustedContactPayload
from app.services.reporting_service import ReportingService


class _FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping


class _FakeResult:
    def __init__(self, *, row=None, rows=None):
        self._row = _FakeRow(row) if row is not None else None
        self._rows = [_FakeRow(mapping) for mapping in (rows or [])]

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class _RecordingAsyncSession:
    def __init__(self, handler):
        self._handler = handler
        self.calls = []

    async def execute(self, query, params=None):
        sql = str(query)
        normalized_params = params or {}
        self.calls.append((sql, normalized_params))
        return self._handler(sql, normalized_params)


class ReportingServiceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_report_persists_pending_incident_and_returns_created_row(self):
        submitted_at = datetime(2026, 4, 6, 10, 30, tzinfo=timezone.utc)

        def handler(sql, _params):
            if "INSERT INTO incident_reports" in sql:
                return _FakeResult(
                    row={
                        "id": "report-1",
                        "status": "pending",
                        "confidence": 0.5,
                        "submitted_at": submitted_at,
                    }
                )
            raise AssertionError(f"Unexpected query: {sql}")

        session = _RecordingAsyncSession(handler)
        created = await ReportingService().create_report(
            ReportCreate(
                user_hash="user-123",
                incident_type="Poor lighting",
                severity=3,
                lat=18.52,
                lon=73.85,
                description="Dark stretch",
                metadata={"source": "test"},
            ),
            session,
        )

        insert_sql, insert_params = session.calls[0]
        self.assertIn("INSERT INTO incident_reports", insert_sql)
        self.assertIn("'pending'", insert_sql)
        self.assertEqual(insert_params["user_hash"], "user-123")
        self.assertEqual(insert_params["category"], "Poor lighting")
        self.assertEqual(insert_params["confidence"], 0.5)
        self.assertEqual(created["id"], "report-1")
        self.assertEqual(created["status"], "pending")
        self.assertEqual(created["submitted_at"], submitted_at)

    async def test_get_recent_reports_shapes_rows_for_api_response(self):
        created_at = datetime(2026, 4, 6, 11, 0, tzinfo=timezone.utc)

        def handler(sql, params):
            if "FROM incident_reports" in sql:
                self.assertEqual(params["limit"], 5)
                return _FakeResult(
                    rows=[
                        {
                            "id": "report-2",
                            "lat": 18.52,
                            "lon": 73.85,
                            "incident_type": "Harassment",
                            "severity": 3,
                            "confidence_score": 0.9,
                            "created_at": created_at,
                            "status": "verified",
                        }
                    ]
                )
            raise AssertionError(f"Unexpected query: {sql}")

        session = _RecordingAsyncSession(handler)
        reports = await ReportingService().get_recent_reports(limit=5, db=session)

        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["id"], "report-2")
        self.assertEqual(reports[0]["incident_type"], "Harassment")
        self.assertEqual(reports[0]["confidence_score"], 0.9)
        self.assertEqual(reports[0]["status"], "verified")
        self.assertEqual(reports[0]["created_at"], created_at)

    async def test_create_emergency_alert_serializes_named_and_plain_contacts(self):
        created_at = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)

        def handler(sql, _params):
            if "INSERT INTO emergency_alerts" in sql:
                return _FakeResult(
                    row={
                        "id": "emergency-2",
                        "status": "triggered",
                        "created_at": created_at,
                        "contacts_notified": 2,
                        "metadata": {},
                    }
                )
            return _FakeResult()

        session = _RecordingAsyncSession(handler)
        created = await ReportingService().create_emergency_alert(
            EmergencyAlertCreate(
                user_hash="user-999",
                lat=18.52,
                lon=73.85,
                message="Need help",
                trusted_contacts=[
                    " sister@walksafe.local ",
                    TrustedContactPayload(name="Alice", phone="+911234567890"),
                    TrustedContactPayload(name="alice", phone="+911234567890"),
                    "",
                ],
                metadata={"source": "test"},
            ),
            session,
        )

        insert_sql, insert_params = next(
            (sql, params)
            for sql, params in session.calls
            if "INSERT INTO emergency_alerts" in sql
        )
        self.assertIn("INSERT INTO emergency_alerts", insert_sql)
        self.assertEqual(insert_params["contacts_notified"], 2)

        metadata = json.loads(insert_params["metadata"])
        self.assertEqual(metadata["source"], "test")
        self.assertEqual(
            metadata["trusted_contacts"],
            [
                "sister@walksafe.local",
                {"name": "Alice", "phone": "+911234567890"},
            ],
        )
        self.assertEqual(
            metadata["trusted_contacts_notified"],
            [
                "sister@walksafe.local",
                {"name": "Alice", "phone": "+911234567890"},
            ],
        )
        self.assertEqual(created["id"], "emergency-2")
        self.assertEqual(created["contacts_notified"], 2)
        self.assertEqual(
            created["trusted_contacts"],
            [
                "sister@walksafe.local",
                {"name": "Alice", "phone": "+911234567890"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
