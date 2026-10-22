"""
ResilientSteps Safety Data Ingest Job
================================
Run this script to populate the database with real safety scores from OpenStreetMap.
This replaces ALL synthetic/random data. Run it once on setup, then periodically.

Usage:
    cd logic
    python generate_safety_map.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import h3
import osmnx as ox
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found.")
    print("Make sure backend/.env exists with a valid DATABASE_URL.")
    sys.exit(1)


def _normalize_database_url(url: str) -> str:
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


DATABASE_URL = _normalize_database_url(DATABASE_URL)


ROAD_TYPE_SCORES = {
    "footway": 90,
    "pedestrian": 90,
    "path": 75,
    "residential": 70,
    "living_street": 80,
    "cycleway": 72,
    "service": 60,
    "unclassified": 55,
    "tertiary": 50,
    "secondary": 40,
    "primary": 30,
    "trunk": 20,
    "motorway": 5,
}
DEFAULT_ROAD_SCORE = 50
LIGHTING_BONUS = 10
SIDEWALK_BONUS = 5
SPEED_PENALTY_PER_10KMH = 3
INCIDENT_PENALTY = 5


def score_edge(edge_data: dict) -> float:
    highway = edge_data.get("highway", "unclassified")
    if isinstance(highway, list):
        highway = highway[0]

    base = ROAD_TYPE_SCORES.get(highway, DEFAULT_ROAD_SCORE)

    lit = edge_data.get("lit", "no")
    lighting = LIGHTING_BONUS if lit == "yes" else 0

    sidewalk = edge_data.get("sidewalk", "none")
    sw_bonus = SIDEWALK_BONUS if sidewalk not in ("none", "no", None) else 0

    maxspeed_raw = edge_data.get("maxspeed", "30")
    try:
        speed = int(str(maxspeed_raw).replace(" mph", "").replace(" km/h", "").strip())
    except (ValueError, AttributeError):
        speed = 30
    speed_penalty = max(0, (speed - 30) // 10) * SPEED_PENALTY_PER_10KMH

    score = base + lighting + sw_bonus - speed_penalty
    return max(0.0, min(100.0, float(score)))


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


async def run_ingest(
    dataset_version: str | None = None,
    reuse_existing_roads: bool = False,
):
    city_cfg = load_city_config()
    city_name = city_cfg.get("name", "pune").lower().replace(" ", "_")
    osmnx_place = city_cfg.get("osmnx_place", "Pune, Maharashtra, India")
    h3_res = city_cfg.get("h3_resolution", 9)

    print("=" * 60)
    print(f"ResilientSteps Safety Data Ingest Job — {city_cfg.get('name', 'Pune')}")
    print("=" * 60)

    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    if reuse_existing_roads:
        if not dataset_version:
            async with Session() as session:
                res = await session.execute(
                    text(
                        "SELECT dataset_version FROM road_segments ORDER BY updated_at DESC LIMIT 1"
                    )
                )
                row = res.fetchone()
                if not row:
                    print("No road segments found in database to generate zones from.")
                    await engine.dispose()
                    return
                dataset_version = row[0]

        async with Session() as session:
            res = await session.execute(
                text("SELECT count(*) FROM road_segments WHERE dataset_version = :v"),
                {"v": dataset_version},
            )
            count = res.scalar() or 0
        print(
            f"Reusing {count} existing road segments for dataset version: {dataset_version}"
        )
        start = time.time()
        print("Generating safety zone polygons...")
        await generate_safety_zones(dataset_version, engine)
        elapsed = time.time() - start
        print(f"Done. Dataset version: {dataset_version} | Time: {elapsed:.1f}s")
        await engine.dispose()
        return

    if not dataset_version:
        dataset_version = datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"Dataset version: {dataset_version}")

    cache_path = os.path.join(
        os.path.dirname(__file__), "outputs", f"{city_name}_walk.graphml"
    )
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    if os.path.exists(cache_path):
        print(f"Loading cached street graph ({city_name}_walk.graphml)...")
        graph = ox.load_graphml(cache_path)
    else:
        print(
            f"Downloading {city_cfg.get('name', 'Pune')} street graph from OpenStreetMap ('{osmnx_place}')..."
        )
        print("This may take 5-10 minutes on first run...")
        graph = ox.graph_from_place(osmnx_place, network_type="walk")
        ox.save_graphml(graph, cache_path)
        print("Graph cached for future runs.")
    edges = ox.graph_to_gdfs(graph, nodes=False)
    total = len(edges)
    print(f"Scoring {total} street segments...")

    batch = []
    written = 0
    start = time.time()

    async with Session() as session:
        for idx, (edge_id, row) in enumerate(edges.iterrows()):
            if idx % 1000 == 0 and idx > 0:
                print(f"  Progress: {idx}/{total} segments scored...")

            safety_score = score_edge(row.to_dict())
            geom_wkt = row.geometry.wkt

            batch.append(
                {
                    "osm_way_id": _extract_osm_way_id(edge_id, row),
                    "geometry_wkt": geom_wkt,
                    "safety_score": safety_score,
                    "road_type": str(row.get("highway", "unknown")),
                    "lighting": str(row.get("lit", "no")) == "yes",
                    "dataset_version": dataset_version,
                }
            )

            if len(batch) >= 2000:
                await _write_batch(session, batch)
                await session.commit()
                written += len(batch)
                batch = []

        if batch:
            await _write_batch(session, batch)
            await session.commit()
            written += len(batch)

    print(f"Written {written} segments to database.")

    print("Generating safety zone polygons...")
    await generate_safety_zones(dataset_version, engine)

    elapsed = time.time() - start
    print(f"Done. Dataset version: {dataset_version} | Time: {elapsed:.1f}s")
    await engine.dispose()


async def _write_batch(session: AsyncSession, batch: list):
    if not batch:
        return
    await session.execute(
        text(
            """
            INSERT INTO road_segments
                (osm_way_id, geometry, safety_score, road_type, lighting, dataset_version)
            VALUES
                (:osm_way_id,
                 ST_GeomFromText(:geometry_wkt, 4326),
                 :safety_score,
                 :road_type,
                 :lighting,
                 :dataset_version)
            """
        ),
        batch,
    )


async def generate_safety_zones(dataset_version: str, engine):
    """
    Cluster road segments into H3 hexagon zones and store as polygons.
    H3 resolution 9 ~= 150m per hexagon - appropriate for pedestrian scale.
    """
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        result = await session.execute(
            text(
                """
                SELECT
                    ST_Y(ST_Centroid(geometry)) AS lat,
                    ST_X(ST_Centroid(geometry)) AS lon,
                    safety_score
                FROM road_segments
                WHERE dataset_version = :v
                """
            ),
            {"v": dataset_version},
        )
        rows = result.fetchall()

    if not rows:
        print("No segments found - skipping zone generation.")
        return

    cell_scores = {}
    cell_counts = {}

    h3_res = load_city_config().get("h3_resolution", 9)
    for lat, lon, score in rows:
        cell = h3.latlng_to_cell(lat, lon, h3_res)
        cell_scores[cell] = cell_scores.get(cell, 0.0) + float(score)
        cell_counts[cell] = cell_counts.get(cell, 0) + 1

    zones_batch = []
    for cell, total_score in cell_scores.items():
        count = cell_counts[cell]
        if count < 2:
            continue

        avg_score = total_score / count

        if avg_score >= 70:
            risk_level = "safe"
        elif avg_score >= 40:
            risk_level = "cautious"
        else:
            risk_level = "risky"

        risk_score = 1.0 - (avg_score / 100.0)

        boundary = h3.cell_to_boundary(cell)
        coords_str = ", ".join(f"{lng} {lat}" for lat, lng in boundary)
        first_lat, first_lng = boundary[0]
        first = f"{first_lng} {first_lat}"
        polygon_wkt = f"POLYGON(({coords_str}, {first}))"

        zones_batch.append(
            {
                "zone_id": cell,
                "wkt": polygon_wkt,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "dataset_version": dataset_version,
            }
        )

    async with Session() as session:
        batch_size = 500
        for i in range(0, len(zones_batch), batch_size):
            chunk = zones_batch[i : i + batch_size]
            await session.execute(
                text(
                    """
                    INSERT INTO safety_zones
                        (zone_id, geometry, risk_level, risk_score, dataset_version)
                    VALUES
                        (:zone_id,
                         ST_GeomFromText(:wkt, 4326),
                         :risk_level,
                         :risk_score,
                         :dataset_version)
                    ON CONFLICT (zone_id) DO UPDATE SET
                        geometry = EXCLUDED.geometry,
                        risk_level = EXCLUDED.risk_level,
                        risk_score = EXCLUDED.risk_score,
                        dataset_version = EXCLUDED.dataset_version,
                        created_at = NOW()
                    """
                ),
                chunk,
            )

        await session.commit()

    print(f"Written {len(zones_batch)} safety zone polygons.")



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="WalkSafe Safety Data Ingest Job")
    parser.add_argument(
        "--zones-only",
        "--reuse-roads",
        action="store_true",
        dest="reuse_roads",
        help="Skip road segment scoring and regenerate safety zones from existing road segments.",
    )
    parser.add_argument(
        "--dataset-version",
        type=str,
        default=None,
        help="Specify an existing dataset version to generate zones for.",
    )
    args = parser.parse_args()
    asyncio.run(
        run_ingest(
            dataset_version=args.dataset_version,
            reuse_existing_roads=args.reuse_roads,
        )
    )
