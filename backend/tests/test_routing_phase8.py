import sys
import unittest
from pathlib import Path

from shapely import wkb
from shapely.geometry import LineString, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.safety_dataset_cache import (
    CachedRoadSegment,
    CachedSafetyZone,
    SafetyDatasetCache,
    SafetyDatasetSnapshot,
)


class FakeRow:
    def __init__(self, mapping):
        self._mapping = mapping

    def __getitem__(self, index):
        return list(self._mapping.values())[index]


class FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = rows or []
        self._row = row

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row


class QueryAwareAsyncSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, query, params=None):
        sql = str(query)
        normalized_params = params or {}
        self.calls.append((sql, normalized_params))

        if "FROM road_segments" in sql and "ORDER BY updated_at DESC" in sql:
            return FakeResult(row=("roads-v1",))
        if "FROM safety_zones" in sql and "ORDER BY created_at DESC" in sql:
            return FakeResult(row=("zones-v1",))
        if "ST_AsBinary(geometry)" in sql and "FROM road_segments" in sql:
            return FakeResult(
                rows=[
                    FakeRow(
                        {
                            "id": 101,
                            "safety_score": 82.0,
                            "road_type": "residential",
                            "lighting": True,
                            "geometry_wkb": wkb.dumps(
                                LineString([(73.85, 18.52), (73.855, 18.525)])
                            ),
                        }
                    )
                ]
            )
        if "ST_AsBinary(geometry)" in sql and "FROM safety_zones" in sql:
            return FakeResult(
                rows=[
                    FakeRow(
                        {
                            "zone_id": "zone-1",
                            "risk_level": "cautious",
                            "risk_score": 0.35,
                            "dataset_version": "zones-v1",
                            "geometry_wkb": wkb.dumps(
                                Polygon(
                                    [
                                        (73.849, 18.519),
                                        (73.856, 18.519),
                                        (73.856, 18.526),
                                        (73.849, 18.526),
                                        (73.849, 18.519),
                                    ]
                                )
                            ),
                        }
                    )
                ]
            )
        raise AssertionError(f"Unexpected query: {sql}")


class RoutingPhase8Tests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_reuses_warm_snapshot_within_refresh_window(self):
        db = QueryAwareAsyncSession()
        cache = SafetyDatasetCache(refresh_interval_seconds=300)

        first_snapshot = await cache.get_snapshot(db)
        second_snapshot = await cache.get_snapshot(db)

        self.assertIs(first_snapshot, second_snapshot)
        self.assertEqual(len(db.calls), 4)
        self.assertEqual(sum(1 for sql, _ in db.calls if "ORDER BY updated_at DESC" in sql), 1)
        self.assertEqual(sum(1 for sql, _ in db.calls if "ORDER BY created_at DESC" in sql), 1)
        self.assertEqual(sum(1 for sql, _ in db.calls if "ST_AsBinary(geometry)" in sql), 2)

    def test_snapshot_matches_route_segments_and_zone_from_spatial_index(self):
        snapshot = SafetyDatasetSnapshot(
            road_dataset_version="roads-v1",
            zone_dataset_version="zones-v1",
            road_segments=[
                CachedRoadSegment(
                    segment_id=101,
                    safety_score=82.0,
                    road_type="residential",
                    lighting=True,
                    geometry=LineString([(73.85, 18.52), (73.855, 18.525)]),
                ),
                CachedRoadSegment(
                    segment_id=202,
                    safety_score=48.0,
                    road_type="primary",
                    lighting=False,
                    geometry=LineString([(73.90, 18.55), (73.905, 18.555)]),
                ),
            ],
            safety_zones=[
                CachedSafetyZone(
                    zone_id="zone-1",
                    risk_level="cautious",
                    risk_score=0.35,
                    dataset_version="zones-v1",
                    geometry=Polygon(
                        [
                            (73.849, 18.519),
                            (73.856, 18.519),
                            (73.856, 18.526),
                            (73.849, 18.526),
                            (73.849, 18.519),
                        ]
                    ),
                ),
                CachedSafetyZone(
                    zone_id="zone-2",
                    risk_level="risky",
                    risk_score=0.72,
                    dataset_version="zones-v1",
                    geometry=Polygon(
                        [
                            (73.899, 18.549),
                            (73.906, 18.549),
                            (73.906, 18.556),
                            (73.899, 18.556),
                            (73.899, 18.549),
                        ]
                    ),
                ),
            ],
        )

        matches = snapshot.match_route_segments(
            [(18.52, 73.85), (18.525, 73.855)],
            road_match_distance_m=20.0,
            midpoint_search_expand_degrees=0.0005,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["road_segment_id"], 101)
        self.assertEqual(matches[0]["segment_safety_score"], 82.0)
        self.assertEqual(matches[0]["zone_id"], "zone-1")
        self.assertEqual(matches[0]["zone_risk_level"], "cautious")
        self.assertIsNotNone(matches[0]["match_distance_m"])


if __name__ == "__main__":
    unittest.main()
