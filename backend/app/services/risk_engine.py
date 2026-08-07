"""
Risk Engine - reads route safety from cached PostGIS-backed datasets.
Never generates, randomises, or invents safety scores.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.reporting_service import reporting_service
from app.services.safety_dataset_cache import safety_dataset_cache

ROAD_MATCH_DISTANCE_METERS = 20.0
MIDPOINT_SEARCH_EXPAND_DEGREES = 0.0005
INCIDENT_PENALTY_SCALE = 12.0
MAX_INCIDENT_PENALTY = 25.0


def _calculate_incident_penalty(incident_weight: float) -> float:
    return min(MAX_INCIDENT_PENALTY, incident_weight * INCIDENT_PENALTY_SCALE)


async def score_route(
    coordinates: list[tuple[float, float]],
    db: AsyncSession,
) -> dict:
    """
    Given a list of (lat, lon) waypoints, return the route's safety score.
    Score is derived from road_segments matched to the route geometry and
    adjusted by nearby incident reports.
    Returns None score (not zero) if no matching route safety data exists.
    """
    if not coordinates or len(coordinates) < 2:
        return {
            "safety_score": None,
            "segment_count": 0,
            "matched_segment_count": 0,
            "unmatched_segment_count": 0,
            "applied_incident_count": 0,
            "incident_affected_segment_count": 0,
            "dataset_version": None,
            "segments": [],
            "warning": "Route has no coordinates",
        }

    snapshot = await safety_dataset_cache.get_snapshot(db)
    rows = snapshot.match_route_segments(
        coordinates,
        road_match_distance_m=ROAD_MATCH_DISTANCE_METERS,
        midpoint_search_expand_degrees=MIDPOINT_SEARCH_EXPAND_DEGREES,
    )

    total_route_length = sum(float(row["route_length_m"]) for row in rows)
    road_segment_ids = sorted(
        {
            int(row["road_segment_id"])
            for row in rows
            if row["road_segment_id"] is not None
        }
    )
    incident_aggregates = await reporting_service.get_segment_incident_aggregates(
        road_segment_ids=road_segment_ids,
        dataset_version=snapshot.road_dataset_version,
        db=db,
    )
    segments = []
    matched_length = 0.0
    weighted_score_total = 0.0

    for row in rows:
        segment = row
        segment_length = float(segment["route_length_m"])
        base_safety_score = segment["segment_safety_score"]
        matched = base_safety_score is not None
        road_segment_id = (
            int(segment["road_segment_id"])
            if segment["road_segment_id"] is not None
            else None
        )
        incident_info = (
            incident_aggregates.get(road_segment_id, {})
            if road_segment_id is not None
            else {}
        )
        incident_weight = float(incident_info.get("incident_weight", 0.0))
        incident_penalty = (
            _calculate_incident_penalty(incident_weight) if matched else 0.0
        )
        adjusted_safety_score = (
            max(0.0, float(base_safety_score) - incident_penalty)
            if matched
            else None
        )

        if matched:
            matched_length += segment_length
            weighted_score_total += adjusted_safety_score * segment_length

        zone = None
        if segment["zone_id"] is not None:
            zone = {
                "zone_id": segment["zone_id"],
                "risk_level": segment["zone_risk_level"],
                "risk_score": (
                    round(float(segment["zone_risk_score"]), 3)
                    if segment["zone_risk_score"] is not None
                    else None
                ),
            }

        segments.append(
            {
                "segment_index": int(segment["segment_index"]),
                "start": {
                    "lat": float(segment["start_lat"]),
                    "lon": float(segment["start_lon"]),
                },
                "end": {
                    "lat": float(segment["end_lat"]),
                    "lon": float(segment["end_lon"]),
                },
                "length_m": round(segment_length, 2),
                "matched": matched,
                "base_safety_score": (
                    round(float(base_safety_score), 1) if matched else None
                ),
                "safety_score": (
                    round(adjusted_safety_score, 1) if matched else None
                ),
                "road_segment_id": road_segment_id,
                "road_type": segment["road_type"],
                "lighting": segment["lighting"],
                "match_distance_m": (
                    round(float(segment["match_distance_m"]), 3)
                    if segment["match_distance_m"] is not None
                    else None
                ),
                "incident_count": int(incident_info.get("incident_count", 0)),
                "incident_weight": round(incident_weight, 3),
                "incident_penalty": round(incident_penalty, 1),
                "incident_categories": incident_info.get("incident_categories", []),
                "latest_incident_at": incident_info.get("latest_incident_at"),
                "zone": zone,
            }
        )

    if matched_length == 0:
        warning = (
            "No safety data found for this route. "
            "The ingest job may not have been run yet."
        )
        safety_score = None
    elif matched_length < total_route_length:
        warning = (
            "Safety data was matched for only part of this route. "
            "Unmatched route segments are returned with null safety scores."
        )
        safety_score = round(weighted_score_total / matched_length, 1)
    else:
        warning = None
        safety_score = round(weighted_score_total / matched_length, 1)

    matched_segment_count = sum(1 for segment in segments if segment["matched"])
    applied_incident_count = sum(
        int(incident.get("incident_count", 0))
        for incident in incident_aggregates.values()
    )

    return {
        "safety_score": safety_score,
        "segment_count": len(segments),
        "matched_segment_count": matched_segment_count,
        "unmatched_segment_count": len(segments) - matched_segment_count,
        "applied_incident_count": applied_incident_count,
        "incident_affected_segment_count": sum(
            1
            for incident in incident_aggregates.values()
            if int(incident.get("incident_count", 0)) > 0
        ),
        "dataset_version": snapshot.road_dataset_version,
        "segments": segments,
        "warning": warning,
    }
