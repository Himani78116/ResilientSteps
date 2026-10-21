"""
ResilientSteps Shade Data Seed Job
==================================
Run this script to populate shade_score on road_segments from OpenStreetMap
canopy features (trees and green areas). It only UPDATES existing rows written
by generate_safety_map.py — it never inserts road segments.

Matching strategy: rows are matched on (osm_way_id, dataset_version) using the
LATEST dataset_version currently in road_segments. This keeps the job idempotent
(re-running it rewrites the same rows) and avoids re-ingesting geometry. Edges
without a usable OSM way id are skipped and reported.

Usage:
    cd logic
    python generate_shade_map.py
"""

import asyncio
import os
import socket
import sys
import time
from datetime import datetime

import geopandas as gpd
import osmnx as ox
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
)

# This host's IPv4 route to some CDNs is black-holed (dial attempts never finish)
# while IPv6 connects immediately, but DNS returns both families. Reordering the
# addresses to try IPv6 first keeps every connection on the working stack.
_original_getaddrinfo = socket.getaddrinfo


def _ipv6_first_getaddrinfo(*args, **kwargs):
    results = _original_getaddrinfo(*args, **kwargs)
    v6 = [r for r in results if r[0] == socket.AF_INET6]
    v4 = [r for r in results if r[0] == socket.AF_INET]
    return v6 + v4 if v6 and v4 else results


socket.getaddrinfo = _ipv6_first_getaddrinfo

BUFFER_DEGREES = 0.00015  # ~15 m at Pune latitudes
BATCH_SIZE = 500
DATASET_VERSION_QUERY = text(
    "SELECT dataset_version FROM road_segments ORDER BY updated_at DESC LIMIT 1"
)

CANOPY_TAGS = {
    "natural": ["tree", "wood", "scrub"],
    "landuse": ["forest", "grass"],
    "leisure": ["park", "garden"],
}

# Mirrors the scoring contract documented in docs/step_7_heat_and_shade_data.md
# and tested in backend/tests/test_shade_scoring.py.
TREE_COUNT_SATURATION = 6      # trees within the buffer for full tree score
VEG_AREA_FRACTION_CAP = 0.6    # buffer fraction under green area for full score
TREE_WEIGHT = 0.7
AREA_WEIGHT = 0.3


def score_edge_shade(tree_count: int, green_area_m2: float, buffer_area_m2: float) -> float:
    tree_component = min(1.0, tree_count / TREE_COUNT_SATURATION)
    if buffer_area_m2 <= 0:
        area_component = 0.0
    else:
        area_component = min(1.0, (green_area_m2 / buffer_area_m2) / VEG_AREA_FRACTION_CAP)
    shade = TREE_WEIGHT * tree_component + AREA_WEIGHT * area_component
    return max(0.0, min(100.0, shade * 100.0))


def load_city_config() -> dict:
    import yaml
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "city.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("city", data)
    return {
        "name": "Pune",
        "osmnx_place": "Pune, Maharashtra, India",
        "h3_resolution": 9,
    }


def _extract_osm_way_id(edge_id, row) -> int:
    osmid = row.get("osmid")
    if isinstance(osmid, list) and osmid:
        osmid = osmid[0]
    try:
        return int(osmid)
    except (TypeError, ValueError):
        pass

    if isinstance(edge_id, tuple) and len(edge_id) > 2:
        try:
            return int(edge_id[2])
        except (TypeError, ValueError):
            return 0
    return 0


def _normalize_database_url(url: str) -> str:
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    if sslmode and "ssl" not in query:
        query["ssl"] = sslmode
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


# Default endpoint is overpass-api.de; if it stalls, fall back to public mirrors.
# The payload is cached locally either way, so downstream runs are offline.
OVERPASS_MIRRORS = [
    None,
    "https://overpass.kumi.systems/api",
    "https://overpass.private.coffee/api",
    "https://overpass-api.de/api",
]

# Overpass asks for exponential backoff when its queue is full (502/504).
# Each mirror gets snapped attempts before moving to the next mirror.
OVERPASS_BACKOFF_WAITS = [0, 30, 90, 240, 420]


def _fetch_canopy_features(osmnx_place: str):
    last_error = None
    for endpoint in OVERPASS_MIRRORS:
        for wait in OVERPASS_BACKOFF_WAITS:
            try:
                label = endpoint or "default (overpass-api.de)"
                if wait:
                    print(f"  Retrying {label} after {wait}s backoff...")
                    time.sleep(wait)
                print(f"Querying Overpass endpoint: {label} ...")
                if endpoint:
                    ox.settings.overpass_endpoint = endpoint
                return ox.features_from_place(osmnx_place, tags=CANOPY_TAGS)
            except Exception as exc:
                last_error = exc
                print(f"  Endpoint failed ({type(exc).__name__}): {exc}")
    raise last_error


def _load_canopy_layers(city_name: str, osmnx_place: str):
    outputs_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    trees_cache = os.path.join(outputs_dir, f"{city_name}_canopy_trees.geojson")
    green_cache = os.path.join(outputs_dir, f"{city_name}_canopy_green.geojson")

    if os.path.exists(trees_cache) and os.path.exists(green_cache):
        print("Loading cached canopy features...")
        trees = gpd.read_file(trees_cache)
        green = gpd.read_file(green_cache)
        print(f"Canopy features: {len(trees)} tree points, {len(green)} green polygons.")
        return trees, green

    print(f"Fetching canopy features for '{osmnx_place}'...")
    features = _fetch_canopy_features(osmnx_place)
    features = features[features.geometry.notna()]

    trees = features[features.geometry.geom_type.isin(["Point"])]
    green = features[features.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    print(f"Canopy features: {len(trees)} tree points, {len(green)} green polygons.")
    if trees.empty and green.empty:
        print("WARNING: no canopy features found — every segment will score 0.")

    trees.to_file(trees_cache, driver="GeoJSON")
    green.to_file(green_cache, driver="GeoJSON")
    print(f"Canopy features cached for future runs ({trees_cache}).")
    return trees, green


def _compute_shade_per_segment(edges, trees, green) -> gpd.GeoDataFrame:
    # The OSMnx edge GeoDataFrame carries a MultiIndex (u, v, key); every
    # downstream join/assign below is positional on 0..n-1, so rebuild the
    # buffer geometry index explicitly or pandas rejects the insertion.
    buffers = edges.geometry.buffer(BUFFER_DEGREES).reset_index(drop=True)
    segments = gpd.GeoDataFrame(
        {"seg_index": range(len(edges))}, geometry=buffers, crs=edges.crs
    )

    tree_counts = pd.Series(0.0, index=range(len(edges)))
    if not trees.empty:
        hits = gpd.sjoin(segments, trees[["geometry"]], predicate="intersects")
        tree_counts = hits.groupby("seg_index").size().reindex(
            range(len(edges)), fill_value=0
        ).astype(float)

    green_areas = pd.Series(0.0, index=range(len(edges)))
    buffer_areas = pd.Series(0.0, index=range(len(edges)))

    if not green.empty:
        utm_crs = segments.estimate_utm_crs()
        segments_utm = segments.to_crs(utm_crs)
        green_utm = green.to_crs(utm_crs)
        green_utm = green_utm.rename(columns={"geometry": "green_geom"}).set_geometry("green_geom")

        buffer_areas = segments_utm.geometry.area
        buffer_areas.index = range(len(edges))

        hits = gpd.sjoin(
            segments_utm[["seg_index", "geometry"]],
            green_utm[["green_geom"]],
            predicate="intersects",
        )
        if not hits.empty:
            # Geopandas joins drop the right frame's geometry column and
            # leave `index_right` instead — re-attach the polygon per row.
            right_polygons = hits["index_right"].map(green_utm["green_geom"])
            intersections = hits["geometry"].intersection(right_polygons)
            hits["intersection_area_m2"] = intersections.area
            green_areas = hits.groupby("seg_index")["intersection_area_m2"].sum().reindex(
                range(len(edges)), fill_value=0.0
            )

    shade_scores = []
    for idx in range(len(edges)):
        shade_scores.append(
            score_edge_shade(
                int(tree_counts.iloc[idx]),
                float(green_areas.iloc[idx]),
                float(buffer_areas.iloc[idx]),
            )
        )

    result = edges[["osmid"]].copy() if "osmid" in edges.columns else edges[[]].copy()
    result["shade_score"] = shade_scores
    return result


async def _resolve_database_url() -> str | None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found.")
        print("Make sure backend/.env exists with a valid DATABASE_URL.")
        return None
    return _normalize_database_url(database_url)


async def run_ingest():
    database_url = await _resolve_database_url()
    if not database_url:
        sys.exit(1)

    city_cfg = load_city_config()
    city_name = city_cfg.get("name", "pune").lower().replace(" ", "_")
    osmnx_place = city_cfg.get("osmnx_place", "Pune, Maharashtra, India")

    print("=" * 60)
    print(f"ResilientSteps Shade Data Seed Job — {city_cfg.get('name', 'Pune')}")
    print("=" * 60)

    cache_path = os.path.join(os.path.dirname(__file__), "outputs", f"{city_name}_walk.graphml")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    if os.path.exists(cache_path):
        print(f"Loading cached street graph ({city_name}_walk.graphml)...")
        graph = ox.load_graphml(cache_path)
    else:
        print(f"Downloading {city_cfg.get('name', 'Pune')} street graph from OpenStreetMap...")
        print("Run generate_safety_map.py first — it caches the same graph.")
        graph = ox.graph_from_place(osmnx_place, network_type="walk")
        ox.save_graphml(graph, cache_path)
    edges = ox.graph_to_gdfs(graph, nodes=False)

    trees, green = _load_canopy_layers(city_name, osmnx_place)

    start = time.time()
    print(f"Scoring {len(edges):,} edges against canopy layers...", flush=True)
    scored = _compute_shade_per_segment(edges, trees, green)
    print(f"Scoring done in {time.time() - start:.0f}s.", flush=True)

    engine = create_async_engine(database_url, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        latest = (await session.execute(DATASET_VERSION_QUERY)).fetchone()
        if latest is None:
            print("ERROR: road_segments is empty.")
            print("Run generate_safety_map.py first — the shade seed only updates existing rows.")
            await engine.dispose()
            sys.exit(1)
        dataset_version = latest[0]

    print(f"Updating shade for dataset_version {dataset_version}...")
    # The batched UPDATEs filter on (osm_way_id, dataset_version), but the
    # table only ships with a PK on `id` and a GiST index on geometry.
    # Without this index every batch degrades into a full scan of ~450k
    # rows — one-time cost, makes the whole job minutes instead of an hour.
    await session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_road_segments_way_version "
            "ON road_segments (osm_way_id, dataset_version)"
        )
    )
    await session.commit()
    updates = []
    updated = 0
    skipped = 0

    for edge_id, row in scored.iterrows():
        osm_way_id = _extract_osm_way_id(edge_id, row)
        if osm_way_id == 0:
            skipped += 1
            continue
        updates.append(
            {
                "osm_way_id": int(osm_way_id),
                "shade_score": float(row["shade_score"]),
                "dataset_version": dataset_version,
            }
        )

        if len(updates) >= BATCH_SIZE:
            await _write_batch(session, updates)
            updated += len(updates)
            updates = []
            await session.commit()
            if updated % (BATCH_SIZE * 25) == 0:
                print(
                    f"  {updated:,} segment scores written "
                    f"({time.time() - start:.0f}s elapsed)...",
                    flush=True,
                )

    if updates:
        await _write_batch(session, updates)
        updated += len(updates)

    await session.commit()
    print(f"Done writing {updated:,} rows, committing...", flush=True)

    mean_shade = (
        scored["shade_score"].mean() if len(scored) else 0.0
    )
    elapsed = time.time() - start
    print(
        f"Scored {updated} segments. Mean shade {mean_shade:.1f} "
        f"(skipped {skipped} edges without an OSM way id)."
    )
    print(f"Done. Time: {elapsed:.1f}s")
    await engine.dispose()


async def _write_batch(session: AsyncSession, batch: list):
    await session.execute(
        text(
            """
            UPDATE road_segments
            SET shade_score = :shade_score,
                shade_source = 'osm_canopy',
                shade_updated_at = NOW()
            WHERE osm_way_id = :osm_way_id
              AND dataset_version = :dataset_version
            """
        ),
        batch,
    )


if __name__ == "__main__":
    asyncio.run(run_ingest())
