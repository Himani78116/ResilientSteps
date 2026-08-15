import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add backend app directory to path for imports if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

LOGGER = logging.getLogger("import_wards")
logging.basicConfig(level=logging.INFO)

# Default sample Pune municipal wards (polygon bounding boxes for major Pune areas)
SAMPLE_PUNE_WARDS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"ward_id": "WARD_01", "ward_name": "Kasba Peth", "zone": "Zone 1"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[
                    [[73.8500, 18.5150], [73.8650, 18.5150], [73.8650, 18.5250], [73.8500, 18.5250], [73.8500, 18.5150]]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"ward_id": "WARD_02", "ward_name": "Shivajinagar", "zone": "Zone 1"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[
                    [[73.8350, 18.5250], [73.8500, 18.5250], [73.8500, 18.5400], [73.8350, 18.5400], [73.8350, 18.5250]]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"ward_id": "WARD_03", "ward_name": "Kothrud", "zone": "Zone 2"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[
                    [[73.7900, 18.4900], [73.8300, 18.4900], [73.8300, 18.5200], [73.7900, 18.5200], [73.7900, 18.4900]]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"ward_id": "WARD_04", "ward_name": "Aundh-Baner", "zone": "Zone 3"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[
                    [[73.7800, 18.5400], [73.8250, 18.5400], [73.8250, 18.5800], [73.7800, 18.5800], [73.7800, 18.5400]]
                ]]
            }
        },
        {
            "type": "Feature",
            "properties": {"ward_id": "WARD_05", "ward_name": "Hadapsar", "zone": "Zone 4"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[
                    [[73.9000, 18.4800], [73.9500, 18.4800], [73.9500, 18.5300], [73.9000, 18.5300], [73.9000, 18.4800]]
                ]]
            }
        }
    ]
}


async def import_wards_from_geojson(geojson_data: dict, db_url: str | None = None):
    """
    Import ward GeoJSON features into Postgres `wards` table.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    if not db_url:
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://cityos:cityos_secret@localhost:5432/cityos"
        )

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        LOGGER.info("Connected to database for ward import.")
        features = geojson_data.get("features", [])
        imported_count = 0

        for feature in features:
            props = feature.get("properties", {})
            ward_id = props.get("ward_id") or props.get("id") or f"WARD_{imported_count+1:02d}"
            ward_name = props.get("ward_name") or props.get("name") or f"Ward {ward_id}"
            zone = props.get("zone") or props.get("zone_name")

            geom_json = json.dumps(feature.get("geometry", {}))

            query = text(
                """
                INSERT INTO wards (ward_id, ward_name, zone, geometry)
                VALUES (
                    :ward_id,
                    :ward_name,
                    :zone,
                    ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom_json), 4326))
                )
                ON CONFLICT (ward_id) DO UPDATE SET
                    ward_name = EXCLUDED.ward_name,
                    zone = EXCLUDED.zone,
                    geometry = EXCLUDED.geometry;
                """
            )
            await conn.execute(query, {
                "ward_id": ward_id,
                "ward_name": ward_name,
                "zone": zone,
                "geom_json": geom_json,
            })
            imported_count += 1

        LOGGER.info("Imported/updated %d wards.", imported_count)

        # Refresh materialized view if exists
        try:
            await conn.execute(text("REFRESH MATERIALIZED VIEW ward_report_summary;"))
            LOGGER.info("Refreshed ward_report_summary materialized view.")
        except Exception as exc:
            LOGGER.warning("Could not refresh materialized view: %s", exc)

    await engine.dispose()


if __name__ == "__main__":
    geojson_path = sys.argv[1] if len(sys.argv) > 1 else None
    if geojson_path and os.path.exists(geojson_path):
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        LOGGER.info("No GeoJSON file provided or file not found; using default Pune ward boundaries.")
        data = SAMPLE_PUNE_WARDS

    asyncio.run(import_wards_from_geojson(data))
