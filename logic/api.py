from __future__ import annotations

import json
import numbers
from pathlib import Path
from typing import Any, Dict, Optional

import geopandas as gpd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import transform
from shapely.strtree import STRtree

try:
    from .generate_safety_map import (
        METRIC_CRS,
        OUTPUT_PATH,
        WGS84_CRS,
        generate_safety_dataset,
    )
except ImportError:  # pragma: no cover
    # Allows running as a direct script: `python logic/api.py`.
    from generate_safety_map import (
        METRIC_CRS,
        OUTPUT_PATH,
        WGS84_CRS,
        generate_safety_dataset,
    )


class SafetyMapIndex:
    """In-memory safety dataset + STRtree nearest-segment lookup."""

    def __init__(self, segments_gdf: gpd.GeoDataFrame) -> None:
        if segments_gdf.crs is None:
            segments = segments_gdf.set_crs(WGS84_CRS, allow_override=True)
        else:
            segments = segments_gdf.to_crs(WGS84_CRS)

        self._segments = segments.reset_index(drop=True)
        segments_metric = self._segments.to_crs(METRIC_CRS)

        self._metric_geometries = list(segments_metric.geometry)
        self._tree = STRtree(self._metric_geometries) if self._metric_geometries else None
        self._geometry_id_to_index = {
            id(geom): idx for idx, geom in enumerate(self._metric_geometries)
        }

        self._to_metric = Transformer.from_crs(WGS84_CRS, METRIC_CRS, always_xy=True)
        self._geojson = json.loads(self._segments.to_json())

    @property
    def geojson(self) -> Dict[str, Any]:
        return self._geojson

    def nearest_segment(self, *, lat: float, lon: float) -> tuple[Dict[str, Any], float]:
        if not self._tree or not self._metric_geometries:
            raise ValueError("Safety map index is empty.")

        # Step 1: Project query point to metric CRS for nearest and distance checks.
        query_point_metric = transform(self._to_metric.transform, Point(lon, lat))

        # Step 2: Use STRtree nearest lookup.
        nearest_candidate = self._tree.nearest(query_point_metric)
        segment_index = self._resolve_candidate_index(nearest_candidate)

        # Step 3: Return nearest segment details + metric distance.
        segment_row = self._segments.iloc[segment_index]
        distance_meters = float(query_point_metric.distance(self._metric_geometries[segment_index]))
        return segment_row.to_dict(), distance_meters

    def _resolve_candidate_index(self, candidate: Any) -> int:
        # STRtree can return either an integer index or a geometry object.
        if isinstance(candidate, numbers.Integral):
            return int(candidate)

        direct_match = self._geometry_id_to_index.get(id(candidate))
        if direct_match is not None:
            return direct_match

        for idx, geom in enumerate(self._metric_geometries):
            if geom.equals(candidate):
                return idx

        raise ValueError("Could not resolve nearest segment index.")


app = FastAPI(
    title="WalkSafe Safety Map API",
    description="Serves segment-level safety scores for Pune.",
    version="1.0.0",
)

# CORS for Flutter web (Chrome) local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_safety_index: Optional[SafetyMapIndex] = None


@app.on_event("startup")
def startup_event() -> None:
    global _safety_index

    dataset_path = Path(OUTPUT_PATH)
    if not dataset_path.exists():
        generate_safety_dataset(output_path=dataset_path)

    segments_gdf = gpd.read_file(dataset_path)
    _safety_index = SafetyMapIndex(segments_gdf)


def _require_index() -> SafetyMapIndex:
    if _safety_index is None:
        raise HTTPException(
            status_code=503,
            detail="Safety map index is not ready yet.",
        )
    return _safety_index


@app.get("/")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "walksafe-safety-map"}


@app.get("/safety-map")
def safety_map() -> Dict[str, Any]:
    """Returns all precomputed safety segments for the current region."""
    index = _require_index()
    return index.geojson


@app.get("/safety-score")
def safety_score(
    lat: float = Query(..., description="Latitude of query location."),
    lon: float = Query(..., description="Longitude of query location."),
) -> Dict[str, Any]:
    """Returns nearest segment safety score for a coordinate pair."""
    index = _require_index()
    segment, distance_meters = index.nearest_segment(lat=lat, lon=lon)

    return {
        "query": {"lat": lat, "lon": lon},
        "nearest_segment": {
            "segment_id": segment.get("segment_id"),
            "safety_score": segment.get("safety_score"),
            "distance": segment.get("distance"),
            "start_lat": segment.get("start_lat"),
            "start_lon": segment.get("start_lon"),
            "end_lat": segment.get("end_lat"),
            "end_lon": segment.get("end_lon"),
            "distance_to_query_meters": round(distance_meters, 2),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("logic.api:app", host="127.0.0.1", port=9123, reload=False)
