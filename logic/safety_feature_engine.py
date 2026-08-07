from __future__ import annotations

import json
import logging
import numbers
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

import httpx
from shapely import wkb, wkt
from shapely.geometry import LineString, MultiPoint, Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

DEFAULT_SUPABASE_URL = ""
DEFAULT_SUPABASE_ANON_KEY = ""
DEFAULT_INCIDENT_TABLE = "incident_reports"
DEFAULT_INCIDENT_CONFIDENCE = 0.5
DEFAULT_IGNORED_INCIDENT_STATUSES = frozenset({"dismissed", "rejected"})

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SegmentFeatureResult:
    incident_count: int
    lighting_score: float
    crowd_density: float
    time_of_day_factor: float
    base_safety_score: float
    safety_score: float
    incident_cluster_count: int = 0
    incident_weight: float = 0.0
    incident_heat_score: float = 0.0
    incident_penalty: float = 0.0
    latest_incident_at: Optional[str] = None
    incident_categories: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class IncidentCluster:
    incident_count: int
    total_weight: float
    footprint_metric: BaseGeometry
    influence_geometry_metric: BaseGeometry
    influence_radius_m: float
    latest_incident_at: Optional[str]
    categories: tuple[str, ...]


@dataclass(frozen=True)
class IncidentHeatResult:
    incident_cluster_count: int = 0
    incident_weight: float = 0.0
    incident_heat_score: float = 0.0
    incident_penalty: float = 0.0
    latest_incident_at: Optional[str] = None
    incident_categories: tuple[str, ...] = field(default_factory=tuple)


class SafetyFeatureEngine:
    """Computes segment-level safety features and final 0-100 safety score."""

    def __init__(
        self,
        *,
        incident_points_metric: Optional[List[Point]] = None,
        incident_metadata: Optional[List[Dict[str, Any]]] = None,
        intersection_points_metric: Optional[List[Point]] = None,
        incident_search_radius_m: float = 75.0,
        incident_cluster_radius_m: float = 120.0,
        incident_influence_radius_m: float = 140.0,
        incident_heat_penalty_multiplier: float = 8.0,
        max_incident_heat_penalty: float = 18.0,
        intersection_radius_m: float = 120.0,
    ) -> None:
        self._incident_points = incident_points_metric or []
        self._incident_metadata = self._normalize_incident_metadata(
            incident_metadata,
            len(self._incident_points),
        )
        self._intersection_points = intersection_points_metric or []
        self._incident_search_radius_m = incident_search_radius_m
        self._incident_cluster_radius_m = incident_cluster_radius_m
        self._incident_influence_radius_m = incident_influence_radius_m
        self._incident_heat_penalty_multiplier = incident_heat_penalty_multiplier
        self._max_incident_heat_penalty = max_incident_heat_penalty
        self._intersection_radius_m = intersection_radius_m

        self._incident_tree = STRtree(self._incident_points) if self._incident_points else None
        self._intersection_tree = (
            STRtree(self._intersection_points) if self._intersection_points else None
        )
        self._incident_clusters = self._build_incident_clusters()
        self._incident_cluster_geometries = [
            cluster.influence_geometry_metric for cluster in self._incident_clusters
        ]
        self._incident_cluster_tree = (
            STRtree(self._incident_cluster_geometries)
            if self._incident_cluster_geometries
            else None
        )

    def score_segment(
        self,
        *,
        segment_geometry_metric: LineString,
        road_type: Any,
        at_time: Optional[datetime] = None,
    ) -> SegmentFeatureResult:
        """Returns all engineered features and the final safety score."""
        # Step 1: Count nearby incidents from the Supabase incident table.
        incident_count = self._count_nearby_points(
            tree=self._incident_tree,
            points=self._incident_points,
            target_geometry=segment_geometry_metric,
            radius_meters=self._incident_search_radius_m,
        )

        # Step 2: Estimate lighting score from road type category.
        lighting_score = self._estimate_lighting_score(road_type)

        # Step 3: Estimate crowd density from road type + nearby intersections.
        intersection_count = self._count_nearby_points(
            tree=self._intersection_tree,
            points=self._intersection_points,
            target_geometry=segment_geometry_metric,
            radius_meters=self._intersection_radius_m,
        )
        crowd_density = self._estimate_crowd_density(road_type, intersection_count)

        # Step 4: Estimate time-of-day safety factor.
        timestamp = at_time or datetime.now(timezone.utc)
        pune_tz = timezone(timedelta(hours=5, minutes=30))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        pune_timestamp = timestamp.astimezone(pune_tz)
        time_of_day_factor = self._time_of_day_factor(pune_timestamp.hour)

        # Step 5: Propagate nearby incident hotspot risk into the segment score.
        incident_heat = self._calculate_incident_heat(segment_geometry_metric)

        # Step 6: Combine factors into a final 0-100 segment safety score.
        base_safety_score = self._compute_base_safety_score(
            incident_count=incident_count,
            lighting_score=lighting_score,
            crowd_density=crowd_density,
            time_of_day_factor=time_of_day_factor,
        )
        safety_score = round(
            _clamp(base_safety_score - incident_heat.incident_penalty, 0, 100),
            2,
        )

        return SegmentFeatureResult(
            incident_count=incident_count,
            lighting_score=lighting_score,
            crowd_density=crowd_density,
            time_of_day_factor=time_of_day_factor,
            base_safety_score=base_safety_score,
            safety_score=safety_score,
            incident_cluster_count=incident_heat.incident_cluster_count,
            incident_weight=incident_heat.incident_weight,
            incident_heat_score=incident_heat.incident_heat_score,
            incident_penalty=incident_heat.incident_penalty,
            latest_incident_at=incident_heat.latest_incident_at,
            incident_categories=incident_heat.incident_categories,
        )

    def score_segments(
        self,
        *,
        segment_records: Iterable[Dict[str, Any]],
        at_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Builds segment-level heatmap rows from dynamic incident activity."""
        heatmap_rows: List[Dict[str, Any]] = []

        for record in segment_records:
            geometry = record.get("segment_geometry_metric")
            if geometry is None:
                geometry = record.get("geometry_metric")
            if not isinstance(geometry, LineString):
                raise ValueError(
                    "Each segment_record must include a LineString under "
                    "'segment_geometry_metric' or 'geometry_metric'."
                )

            result = self.score_segment(
                segment_geometry_metric=geometry,
                road_type=record.get("road_type"),
                at_time=at_time,
            )
            heatmap_rows.append(
                {
                    **record,
                    "incident_count": result.incident_count,
                    "incident_cluster_count": result.incident_cluster_count,
                    "incident_weight": result.incident_weight,
                    "incident_heat_score": result.incident_heat_score,
                    "incident_penalty": result.incident_penalty,
                    "incident_categories": list(result.incident_categories),
                    "latest_incident_at": result.latest_incident_at,
                    "lighting_score": result.lighting_score,
                    "crowd_density": result.crowd_density,
                    "time_of_day_factor": result.time_of_day_factor,
                    "base_safety_score": result.base_safety_score,
                    "safety_score": result.safety_score,
                }
            )

        return heatmap_rows

    def _count_nearby_points(
        self,
        *,
        tree: Optional[STRtree],
        points: List[Point],
        target_geometry: LineString,
        radius_meters: float,
    ) -> int:
        if tree is None or not points:
            return 0

        search_area = target_geometry.buffer(radius_meters)
        candidates = tree.query(search_area)
        count = 0

        for candidate in candidates:
            candidate_point = self._resolve_candidate_geometry(candidate, points)
            if candidate_point is None:
                continue
            if target_geometry.distance(candidate_point) <= radius_meters:
                count += 1

        return count

    def _resolve_candidate_geometry(
        self,
        candidate: Any,
        points: List[Point],
    ) -> Optional[Point]:
        # Shapely STRtree may return geometry objects or integer indices.
        if isinstance(candidate, numbers.Integral):
            idx = int(candidate)
            if 0 <= idx < len(points):
                return points[idx]
            return None

        if isinstance(candidate, Point):
            return candidate

        return None

    def _estimate_lighting_score(self, road_type: Any) -> float:
        road = _normalize_road_type(road_type)
        score_by_road = {
            "motorway": 90,
            "trunk": 88,
            "primary": 82,
            "secondary": 75,
            "tertiary": 68,
            "residential": 58,
            "living_street": 62,
            "service": 52,
            "pedestrian": 57,
            "footway": 48,
            "path": 42,
            "steps": 35,
            "track": 38,
        }
        return _clamp(score_by_road.get(road, 55), 0, 100)

    def _estimate_crowd_density(self, road_type: Any, intersection_count: int) -> float:
        road = _normalize_road_type(road_type)
        base_by_road = {
            "motorway": 20,
            "trunk": 30,
            "primary": 58,
            "secondary": 64,
            "tertiary": 60,
            "residential": 50,
            "living_street": 56,
            "service": 40,
            "pedestrian": 72,
            "footway": 54,
            "path": 35,
            "steps": 30,
            "track": 25,
        }
        base_density = base_by_road.get(road, 50)
        intersection_boost = min(30, intersection_count * 6)
        return _clamp(base_density + intersection_boost, 0, 100)

    def _time_of_day_factor(self, hour: int) -> float:
        if 7 <= hour <= 18:
            return 1.0
        if 5 <= hour <= 6 or 19 <= hour <= 20:
            return 0.7
        if 21 <= hour <= 22:
            return 0.5
        return 0.3

    def _calculate_incident_heat(
        self,
        target_geometry: LineString,
    ) -> IncidentHeatResult:
        if self._incident_cluster_tree is None or not self._incident_clusters:
            return IncidentHeatResult()

        total_weight = 0.0
        contributing_clusters = 0
        latest_incident_at: Optional[str] = None
        categories: set[str] = set()

        for candidate in self._incident_cluster_tree.query(target_geometry):
            cluster = self._resolve_incident_cluster(candidate)
            if cluster is None:
                continue

            distance_m = target_geometry.distance(cluster.footprint_metric)
            if distance_m > cluster.influence_radius_m:
                continue

            decay = 1.0 - (distance_m / cluster.influence_radius_m)
            if decay <= 0:
                continue

            total_weight += cluster.total_weight * decay
            contributing_clusters += 1
            categories.update(cluster.categories)

            cluster_latest = _parse_incident_timestamp(cluster.latest_incident_at)
            current_latest = _parse_incident_timestamp(latest_incident_at)
            if cluster_latest is not None and (
                current_latest is None or cluster_latest > current_latest
            ):
                latest_incident_at = cluster_latest.isoformat()

        if contributing_clusters == 0 or total_weight <= 0:
            return IncidentHeatResult()

        incident_penalty = min(
            self._max_incident_heat_penalty,
            total_weight * self._incident_heat_penalty_multiplier,
        )
        incident_heat_score = min(100.0, total_weight * 25.0)

        return IncidentHeatResult(
            incident_cluster_count=contributing_clusters,
            incident_weight=round(total_weight, 3),
            incident_heat_score=round(incident_heat_score, 2),
            incident_penalty=round(incident_penalty, 2),
            latest_incident_at=latest_incident_at,
            incident_categories=tuple(sorted(categories)),
        )

    def _build_incident_clusters(self) -> List[IncidentCluster]:
        if not self._incident_points:
            return []

        remaining = set(range(len(self._incident_points)))
        clusters: List[IncidentCluster] = []

        while remaining:
            seed_idx = remaining.pop()
            component = [seed_idx]
            queue = [seed_idx]

            while queue:
                current_idx = queue.pop()
                current_point = self._incident_points[current_idx]
                neighbours = [
                    candidate_idx
                    for candidate_idx in list(remaining)
                    if current_point.distance(self._incident_points[candidate_idx])
                    <= self._incident_cluster_radius_m
                ]
                for neighbour_idx in neighbours:
                    remaining.remove(neighbour_idx)
                    component.append(neighbour_idx)
                    queue.append(neighbour_idx)

            clusters.append(self._create_incident_cluster(component))

        return clusters

    def _create_incident_cluster(
        self,
        member_indices: Sequence[int],
    ) -> IncidentCluster:
        member_points = [self._incident_points[idx] for idx in member_indices]
        member_metadata = [self._incident_metadata[idx] for idx in member_indices]

        if len(member_points) == 1:
            footprint: BaseGeometry = member_points[0]
            cluster_spread_m = 0.0
        else:
            footprint = MultiPoint(member_points)
            centroid = footprint.centroid
            cluster_spread_m = max(centroid.distance(point) for point in member_points)

        total_weight = sum(self._incident_record_weight(metadata) for metadata in member_metadata)
        extra_radius = min(90.0, cluster_spread_m * 0.5) + min(
            80.0,
            max(0, len(member_points) - 1) * 12.0,
        )
        influence_radius_m = self._incident_influence_radius_m + extra_radius

        categories = tuple(
            sorted(
                {
                    str(metadata.get("category")).strip()
                    for metadata in member_metadata
                    if metadata.get("category")
                }
            )
        )

        latest_incident_at: Optional[str] = None
        for metadata in member_metadata:
            submitted_at = metadata.get("submitted_at")
            candidate_timestamp = _parse_incident_timestamp(submitted_at)
            current_timestamp = _parse_incident_timestamp(latest_incident_at)
            if candidate_timestamp is not None and (
                current_timestamp is None or candidate_timestamp > current_timestamp
            ):
                latest_incident_at = candidate_timestamp.isoformat()

        return IncidentCluster(
            incident_count=len(member_points),
            total_weight=total_weight,
            footprint_metric=footprint,
            influence_geometry_metric=footprint.buffer(influence_radius_m),
            influence_radius_m=influence_radius_m,
            latest_incident_at=latest_incident_at,
            categories=categories,
        )

    def _resolve_incident_cluster(self, candidate: Any) -> Optional[IncidentCluster]:
        if isinstance(candidate, numbers.Integral):
            idx = int(candidate)
            if 0 <= idx < len(self._incident_clusters):
                return self._incident_clusters[idx]
            return None

        if not isinstance(candidate, BaseGeometry):
            return None

        for idx, geometry in enumerate(self._incident_cluster_geometries):
            if candidate.equals(geometry):
                return self._incident_clusters[idx]

        return None

    def _incident_record_weight(self, metadata: Dict[str, Any]) -> float:
        confidence = _normalize_confidence(metadata.get("confidence"))
        status_weight = _incident_status_weight(metadata.get("status"))
        category_weight = _incident_category_weight(metadata.get("category"))
        recency_weight = _incident_recency_weight(metadata.get("submitted_at"))
        return confidence * status_weight * category_weight * recency_weight

    def _normalize_incident_metadata(
        self,
        metadata: Optional[List[Dict[str, Any]]],
        point_count: int,
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        metadata = metadata or []

        if metadata and len(metadata) != point_count:
            LOGGER.warning(
                "Incident metadata count (%s) does not match incident point count (%s); "
                "missing values will use defaults.",
                len(metadata),
                point_count,
            )

        for idx in range(point_count):
            row = metadata[idx] if idx < len(metadata) else {}
            normalized.append(
                {
                    "category": row.get("category") or row.get("incident_type"),
                    "confidence": row.get("confidence"),
                    "status": row.get("status"),
                    "submitted_at": row.get("submitted_at")
                    or row.get("created_at")
                    or row.get("timestamp"),
                }
            )

        return normalized

    def _compute_base_safety_score(
        self,
        *,
        incident_count: int,
        lighting_score: float,
        crowd_density: float,
        time_of_day_factor: float,
    ) -> float:
        # Weighted risk components (higher = more unsafe).
        incident_risk = min(1.0, incident_count / 5.0)
        lighting_risk = 1.0 - (lighting_score / 100.0)
        crowd_risk = 1.0 - (crowd_density / 100.0)
        time_risk = 1.0 - time_of_day_factor

        total_risk = (
            (0.45 * incident_risk)
            + (0.25 * lighting_risk)
            + (0.20 * crowd_risk)
            + (0.10 * time_risk)
        )
        safety_score = (1.0 - total_risk) * 100.0
        return round(_clamp(safety_score, 0, 100), 2)


def load_incidents_from_supabase(
    *,
    supabase_url: Optional[str] = None,
    supabase_anon_key: Optional[str] = None,
    table_name: str = DEFAULT_INCIDENT_TABLE,
    page_size: int = 1000,
    timeout_seconds: float = 15.0,
) -> List[Dict[str, Any]]:
    """Reads incident rows from Supabase REST API and returns lat/lon records."""
    base_url = (supabase_url or os.getenv("SUPABASE_URL") or DEFAULT_SUPABASE_URL).strip()
    anon_key = (
        supabase_anon_key
        or os.getenv("SUPABASE_ANON_KEY")
        or DEFAULT_SUPABASE_ANON_KEY
    ).strip()

    if not base_url or not anon_key:
        LOGGER.warning("Supabase credentials not configured, using empty incident set.")
        return []

    endpoint = f"{base_url.rstrip('/')}/rest/v1/{table_name}"
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
    }

    incidents: List[Dict[str, Any]] = []
    offset = 0

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            while True:
                response = client.get(
                    endpoint,
                    headers=headers,
                    params={"select": "*", "limit": page_size, "offset": offset},
                )
                response.raise_for_status()
                rows = response.json()
                if not isinstance(rows, list):
                    break

                for row in rows:
                    lat, lon = _extract_lat_lon(row)
                    if lat is None or lon is None:
                        continue
                    status = row.get("status")
                    if _should_ignore_incident_status(status):
                        continue
                    incidents.append(
                        {
                            "lat": lat,
                            "lon": lon,
                            "category": row.get("category") or row.get("incident_type"),
                            "confidence": _normalize_confidence(row.get("confidence")),
                            "status": status,
                            "submitted_at": row.get("submitted_at")
                            or row.get("created_at")
                            or row.get("createdAtIso")
                            or row.get("timestamp"),
                        }
                    )

                if len(rows) < page_size:
                    break
                offset += page_size
    except Exception as exc:  # pragma: no cover - network failures are non-fatal
        LOGGER.warning("Failed to load incidents from Supabase: %s", exc)
        return []

    return incidents


def _extract_lat_lon(row: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    lat_keys = ("latitude", "lat", "start_lat")
    lon_keys = ("longitude", "lon", "lng", "start_lon")

    lat = _first_numeric(row, lat_keys)
    lon = _first_numeric(row, lon_keys)
    if lat is not None and lon is not None:
        return lat, lon

    location = row.get("location") or row.get("geometry") or row.get("geom")
    lat, lon = _extract_lat_lon_from_location(location)
    return lat, lon


def _extract_lat_lon_from_location(
    location: Any,
) -> tuple[Optional[float], Optional[float]]:
    if location is None:
        return None, None

    if isinstance(location, dict):
        lat = _first_numeric(location, ("latitude", "lat", "y"))
        lon = _first_numeric(location, ("longitude", "lon", "lng", "x"))
        if lat is not None and lon is not None:
            return lat, lon

        location_type = str(location.get("type", "")).lower()
        if location_type == "point":
            try:
                geometry = shape(location)
            except Exception:
                geometry = None
            if isinstance(geometry, Point):
                return geometry.y, geometry.x
        return None, None

    if isinstance(location, str):
        stripped = location.strip()
        if not stripped:
            return None, None

        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return _extract_lat_lon_from_location(json.loads(stripped))
            except json.JSONDecodeError:
                pass

        geometry = _load_geometry_value(stripped)
        if isinstance(geometry, Point):
            return geometry.y, geometry.x

        if "," in stripped:
            lat_str, lon_str = [part.strip() for part in stripped.split(",", 1)]
            try:
                return float(lat_str), float(lon_str)
            except ValueError:
                return None, None

    return None, None


def _load_geometry_value(value: str) -> Optional[BaseGeometry]:
    normalized = value.strip()
    if not normalized:
        return None

    if normalized.upper().startswith("SRID="):
        _, _, normalized = normalized.partition(";")

    try:
        geometry = wkt.loads(normalized)
        if isinstance(geometry, BaseGeometry):
            return geometry
    except Exception:
        pass

    try:
        geometry = wkb.loads(bytes.fromhex(normalized))
        if isinstance(geometry, BaseGeometry):
            return geometry
    except Exception:
        pass

    return None


def _first_numeric(row: Dict[str, Any], keys: Iterable[str]) -> Optional[float]:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalize_road_type(road_type: Any) -> str:
    if isinstance(road_type, (list, tuple, set)) and road_type:
        return str(next(iter(road_type))).lower()
    if road_type is None:
        return "unknown"
    return str(road_type).lower()


def _normalize_confidence(value: Any) -> float:
    if value is None:
        return DEFAULT_INCIDENT_CONFIDENCE

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return DEFAULT_INCIDENT_CONFIDENCE

    if confidence > 1.0:
        confidence = confidence / 100.0
    return _clamp(confidence, 0.0, 1.0)


def _incident_status_weight(status: Any) -> float:
    normalized = str(status or "pending").strip().lower()
    if normalized in {"verified", "confirmed"}:
        return 1.0
    if normalized == "resolved":
        return 0.4
    return 0.65


def _incident_category_weight(category: Any) -> float:
    normalized = str(category or "").strip().lower()
    weights = {
        "stalking": 1.0,
        "harassment": 0.9,
        "suspicious activity": 0.8,
        "unsafe infrastructure": 0.7,
        "poor lighting": 0.6,
    }
    return weights.get(normalized, 0.65)


def _incident_recency_weight(submitted_at: Any) -> float:
    timestamp = _parse_incident_timestamp(submitted_at)
    if timestamp is None:
        return 0.55

    age_days = (datetime.now(timezone.utc) - timestamp).total_seconds() / 86400.0
    if age_days <= 7:
        return 1.0
    if age_days <= 30:
        return 0.8
    if age_days <= 90:
        return 0.55
    return 0.3


def _parse_incident_timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _should_ignore_incident_status(status: Any) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in DEFAULT_IGNORED_INCIDENT_STATUSES


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
