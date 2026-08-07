import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.reporting_service import ReportingService
from app.services.risk_engine import score_route
from app.services.safety_dataset_cache import (
    CachedRoadSegment,
    CachedSafetyZone,
    SafetyDatasetSnapshot,
)


class FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeAsyncSession:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def execute(self, query, params):
        self.calls.append((str(query), params))
        return FakeResult(self.rows)


class RoutingPhase4Tests(unittest.IsolatedAsyncioTestCase):
    async def test_reporting_service_aggregates_incidents_per_road_segment(self):
        db = FakeAsyncSession(
            [
                FakeRow(
                    {
                        "road_segment_id": 101,
                        "incident_count": 2,
                        "incident_weight": 1.275,
                        "latest_incident_at": datetime(
                            2026,
                            4,
                            2,
                            8,
                            30,
                            tzinfo=timezone.utc,
                        ),
                        "incident_categories": ["Harassment", "Poor lighting"],
                    }
                )
            ]
        )

        aggregates = await ReportingService().get_segment_incident_aggregates(
            road_segment_ids=[101, 102],
            dataset_version="20260403-174632",
            db=db,
        )

        query, params = db.calls[0]
        self.assertIn("FROM incident_reports report", query)
        self.assertIn("FROM road_segments", query)
        self.assertIn(
            "LOWER(COALESCE(report.status, 'pending')) = 'verified'",
            query,
        )
        self.assertNotIn("WHEN 'confirmed' THEN 1.0", query)
        self.assertNotIn("WHEN 'resolved' THEN 0.4", query)
        self.assertEqual(params["dataset_version"], "20260403-174632")
        self.assertEqual(params["road_segment_ids"], [101, 102])
        self.assertEqual(aggregates[101]["incident_count"], 2)
        self.assertEqual(aggregates[101]["incident_weight"], 1.275)
        self.assertEqual(
            aggregates[101]["incident_categories"],
            ["Harassment", "Poor lighting"],
        )
        self.assertEqual(
            aggregates[101]["latest_incident_at"],
            "2026-04-02T08:30:00+00:00",
        )

    async def test_score_route_applies_incident_penalties_to_segment_scores(self):
        db = object()
        snapshot = SafetyDatasetSnapshot(
            road_dataset_version="20260403-174632",
            zone_dataset_version="20260403-174632",
            road_segments=[
                CachedRoadSegment(
                    segment_id=101,
                    safety_score=70.0,
                    road_type="residential",
                    lighting=True,
                    geometry=LineString([(73.85, 18.52), (73.855, 18.525)]),
                ),
                CachedRoadSegment(
                    segment_id=102,
                    safety_score=80.0,
                    road_type="tertiary",
                    lighting=False,
                    geometry=LineString([(73.855, 18.525), (73.86, 18.53)]),
                ),
            ],
            safety_zones=[
                CachedSafetyZone(
                    zone_id="zone-1",
                    risk_level="cautious",
                    risk_score=0.35,
                    dataset_version="20260403-174632",
                    geometry=Polygon(
                        [
                            (73.854, 18.524),
                            (73.861, 18.524),
                            (73.861, 18.531),
                            (73.854, 18.531),
                            (73.854, 18.524),
                        ]
                    ),
                )
            ],
        )

        with patch(
            "app.services.risk_engine.safety_dataset_cache.get_snapshot",
            new=AsyncMock(return_value=snapshot),
        ), patch(
            "app.services.risk_engine.reporting_service.get_segment_incident_aggregates",
            new=AsyncMock(
                return_value={
                    101: {
                        "incident_count": 2,
                        "incident_weight": 1.25,
                        "incident_categories": ["Harassment"],
                        "latest_incident_at": "2026-04-02T08:30:00+00:00",
                    }
                }
            ),
        ):
            scored = await score_route(
                [(18.52, 73.85), (18.525, 73.855), (18.53, 73.86)],
                db,
            )

        self.assertEqual(scored["dataset_version"], "20260403-174632")
        self.assertEqual(scored["applied_incident_count"], 2)
        self.assertEqual(scored["incident_affected_segment_count"], 1)
        self.assertEqual(scored["safety_score"], 67.5)
        self.assertEqual(scored["segments"][0]["base_safety_score"], 70.0)
        self.assertEqual(scored["segments"][0]["safety_score"], 55.0)
        self.assertEqual(scored["segments"][0]["incident_penalty"], 15.0)
        self.assertEqual(scored["segments"][0]["incident_count"], 2)
        self.assertEqual(
            scored["segments"][0]["latest_incident_at"],
            "2026-04-02T08:30:00+00:00",
        )
        self.assertEqual(scored["segments"][1]["safety_score"], 80.0)
        self.assertEqual(scored["segments"][1]["zone"]["zone_id"], "zone-1")


if __name__ == "__main__":
    unittest.main()
