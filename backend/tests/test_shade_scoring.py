import sys
import unittest
from pathlib import Path

from shapely import wkb
from shapely.geometry import LineString, Polygon

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT.parent / "logic"))

from app.modules.walksafe.services.safety_dataset_cache import (
    CachedRoadSegment,
    CachedSafetyZone,
    SafetyDatasetCache,
    SafetyDatasetSnapshot,
)
from generate_shade_map import (
    AREA_WEIGHT,
    TREE_WEIGHT,
    VEG_AREA_FRACTION_CAP,
    score_edge_shade,
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


class ShadeAwareAsyncSession:
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
                            "shade_score": 55.0,
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


class ShadeScoringTests(unittest.TestCase):
    def test_no_trees_and_no_green_scores_zero(self):
        self.assertEqual(score_edge_shade(0, 0.0, 100.0), 0.0)
        self.assertEqual(score_edge_shade(0, 0.0, 0.0), 0.0)

    def test_dense_trees_reach_the_tree_component_ceiling(self):
        score = score_edge_shade(6, 0.0, 100.0)
        self.assertGreaterEqual(score, TREE_WEIGHT * 100 - 0.001)

    def test_all_green_no_trees_scores_the_area_ceiling(self):
        score = score_edge_shade(0, 100.0, 100.0)
        self.assertAlmostEqual(score, AREA_WEIGHT * 100.0)

    def test_results_are_clamped_to_0_100(self):
        self.assertGreaterEqual(score_edge_shade(1000, 1e9, 1.0), 0.0)
        self.assertLessEqual(score_edge_shade(1000, 1e9, 1.0), 100.0)
        self.assertGreaterEqual(score_edge_shade(0, -5.0, 0.0), 0.0)

    def test_weights_combine(self):
        tree_component = min(1.0, 3 / 6)
        area_component = min(1.0, (50.0 / 100.0) / VEG_AREA_FRACTION_CAP)
        expected = (TREE_WEIGHT * tree_component + AREA_WEIGHT * area_component) * 100.0
        score = score_edge_shade(3, 50.0, 100.0)
        self.assertAlmostEqual(score, expected, places=6)


class ShadeCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_shade_score_surfaces_in_route_match(self):
        db = ShadeAwareAsyncSession()
        cache = SafetyDatasetCache(refresh_interval_seconds=300)

        snapshot = await cache.get_snapshot(db)

        self.assertEqual(len(snapshot._road_segments), 1)
        segment = snapshot._road_segments[0]
        self.assertIsInstance(segment, CachedRoadSegment)
        self.assertEqual(segment.shade_score, 55.0)

        matched = snapshot.match_route_segments(
            [(18.522, 73.852), (18.523, 73.853)],
            road_match_distance_m=20.0,
            midpoint_search_expand_degrees=0.001,
        )
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["segment_shade_score"], 55.0)
        self.assertEqual(matched[0]["segment_safety_score"], 82.0)

    def test_snapshot_treats_unknown_shade_as_none_not_zero(self):
        snapshot = SafetyDatasetSnapshot(
            road_dataset_version="roads-v1",
            zone_dataset_version=None,
            road_segments=[
                CachedRoadSegment(
                    segment_id=101,
                    safety_score=82.0,
                    road_type="residential",
                    lighting=True,
                    shade_score=None,
                    geometry=LineString([(73.85, 18.52), (73.855, 18.525)]),
                ),
            ],
            safety_zones=[],
        )
        matched = snapshot.match_route_segments(
            [(18.522, 73.852), (18.523, 73.853)],
            road_match_distance_m=20.0,
            midpoint_search_expand_degrees=0.001,
        )
        self.assertIsNone(matched[0]["segment_shade_score"])


if __name__ == "__main__":
    unittest.main()
