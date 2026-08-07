import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from logic.safety_feature_engine import SafetyFeatureEngine, load_incidents_from_supabase


class FakeResponse:
    def __init__(self, rows):
        self._rows = rows

    def raise_for_status(self):
        return None

    def json(self):
        return self._rows


class FakeClient:
    def __init__(self, responses, timeout):
        self._responses = list(responses)
        self.timeout = timeout
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, headers=None, params=None):
        self.calls.append((url, headers, params))
        if self._responses:
            rows = self._responses.pop(0)
        else:
            rows = []
        return FakeResponse(rows)


class SafetyFeatureEnginePhase5Tests(unittest.TestCase):
    def test_load_incidents_from_supabase_parses_legacy_location_schema(self):
        responses = [
            [
                {
                    "category": "Poor lighting",
                    "confidence": 80,
                    "submitted_at": "2026-04-02T18:15:00+00:00",
                    "status": "pending",
                    "location": {
                        "type": "Point",
                        "coordinates": [73.8567, 18.5204],
                    },
                }
            ],
            [
                {
                    "category": "Harassment",
                    "confidence": 0.9,
                    "submitted_at": "2026-04-01T21:00:00+00:00",
                    "status": "verified",
                    "location": "SRID=4326;POINT(73.851 18.521)",
                }
            ],
            [
                {
                    "category": "Suspicious Activity",
                    "confidence": 0.7,
                    "submitted_at": "2026-04-01T20:00:00+00:00",
                    "status": "dismissed",
                    "location": '{"type":"Point","coordinates":[73.852,18.522]}',
                }
            ],
            [],
        ]
        created_clients = []

        def client_factory(*, timeout):
            client = FakeClient(responses, timeout)
            created_clients.append(client)
            return client

        with patch("logic.safety_feature_engine.httpx.Client", side_effect=client_factory):
            incidents = load_incidents_from_supabase(
                supabase_url="https://example.supabase.co",
                supabase_anon_key="test-key",
                page_size=1,
            )

        self.assertEqual(len(created_clients), 1)
        self.assertEqual(len(created_clients[0].calls), 4)
        self.assertEqual(len(incidents), 2)
        self.assertEqual(incidents[0]["category"], "Poor lighting")
        self.assertEqual(incidents[0]["confidence"], 0.8)
        self.assertEqual(incidents[0]["lat"], 18.5204)
        self.assertEqual(incidents[0]["lon"], 73.8567)
        self.assertEqual(incidents[1]["category"], "Harassment")
        self.assertEqual(incidents[1]["status"], "verified")
        self.assertEqual(incidents[1]["lat"], 18.521)
        self.assertEqual(incidents[1]["lon"], 73.851)

    def test_score_segment_applies_cluster_penalty_to_nearby_segments(self):
        engine = SafetyFeatureEngine(
            incident_points_metric=[Point(0, 0), Point(20, 0)],
            incident_metadata=[
                {
                    "category": "Harassment",
                    "confidence": 1.0,
                    "status": "verified",
                    "submitted_at": "2026-04-03T07:15:00+00:00",
                },
                {
                    "category": "Harassment",
                    "confidence": 1.0,
                    "status": "verified",
                    "submitted_at": "2026-04-03T07:30:00+00:00",
                },
            ],
            incident_search_radius_m=30.0,
            incident_cluster_radius_m=30.0,
            incident_influence_radius_m=120.0,
            intersection_points_metric=[],
        )
        control = SafetyFeatureEngine(incident_points_metric=[], intersection_points_metric=[])
        segment = LineString([(90, 0), (110, 0)])
        at_time = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)

        result = engine.score_segment(
            segment_geometry_metric=segment,
            road_type="residential",
            at_time=at_time,
        )
        control_result = control.score_segment(
            segment_geometry_metric=segment,
            road_type="residential",
            at_time=at_time,
        )

        self.assertEqual(result.incident_count, 0)
        self.assertEqual(result.incident_cluster_count, 1)
        self.assertGreater(result.incident_weight, 0.0)
        self.assertGreater(result.incident_penalty, 0.0)
        self.assertEqual(result.base_safety_score, control_result.base_safety_score)
        self.assertLess(result.safety_score, control_result.safety_score)
        self.assertEqual(result.latest_incident_at, "2026-04-03T07:30:00+00:00")
        self.assertEqual(result.incident_categories, ("Harassment",))

    def test_score_segments_returns_heatmap_rows_with_live_metadata(self):
        engine = SafetyFeatureEngine(
            incident_points_metric=[Point(5, 5)],
            incident_metadata=[
                {
                    "category": "Poor lighting",
                    "confidence": 0.75,
                    "status": "pending",
                    "submitted_at": "2026-04-02T20:30:00+00:00",
                }
            ],
            incident_search_radius_m=20.0,
            incident_cluster_radius_m=20.0,
            incident_influence_radius_m=80.0,
        )

        heatmap_rows = engine.score_segments(
            segment_records=[
                {
                    "segment_id": "segment-17",
                    "segment_geometry_metric": LineString([(0, 0), (10, 10)]),
                    "road_type": "footway",
                }
            ],
            at_time=datetime(2026, 4, 3, 21, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(heatmap_rows), 1)
        row = heatmap_rows[0]
        self.assertEqual(row["segment_id"], "segment-17")
        self.assertIn("base_safety_score", row)
        self.assertIn("safety_score", row)
        self.assertIn("incident_heat_score", row)
        self.assertIn("incident_penalty", row)
        self.assertEqual(row["incident_categories"], ["Poor lighting"])
        self.assertGreaterEqual(row["incident_count"], 1)
        self.assertGreater(row["base_safety_score"], row["safety_score"])


if __name__ == "__main__":
    unittest.main()
