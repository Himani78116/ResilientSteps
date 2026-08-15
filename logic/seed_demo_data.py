"""
CityOS Demo Data Seeder
========================
Seeds the database with realistic mock data across all 3 report types
(Safety, Infrastructure, Waste Management) for competition demos and testing.

Usage:
    python logic/seed_demo_data.py

Environment:
    DATABASE_URL (or backend/.env)
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Load env variables from backend/.env if present
env_path = Path(__file__).resolve().parent.parent / "backend" / ".env"
if env_path.exists():
    load_dotenv(env_path)

DB_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://cityos:cityos_secret@localhost:5432/cityos")

# Center coordinates for Pune
PUNE_LAT = 18.5204
PUNE_LON = 73.8567

MOCK_USERS = [f"demo_user_{i:02d}_hash" for i in range(1, 11)]

CATEGORIES = {
    "safety": ["stalking", "harassment", "suspicious_activity", "unsafe_infrastructure", "poor_lighting"],
    "infrastructure": ["pothole", "streetlight", "footpath", "fallen_tree", "traffic_signal", "water_leak", "waterlogging", "obstruction"],
    "waste": ["overflowing_bin", "illegal_dumping", "construction_debris", "garbage_burning", "dead_animal"],
}

STATUSES = ["verified"] * 6 + ["pending"] * 3 + ["rejected"] * 1  # 60% verified, 30% pending, 10% rejected


async def seed_demo_data(
    num_safety: int = 100,
    num_infra: int = 50,
    num_waste: int = 50,
):
    print(f"Connecting to DB at: {DB_URL}")
    engine = create_async_engine(DB_URL)

    async with engine.begin() as conn:
        print("Ensuring categories table exists & is populated...")
        # Execute seed check
        await conn.execute(
            text(
                """
                INSERT INTO report_categories (module, code, label) VALUES
                  ('safety', 'stalking', 'Stalking'),
                  ('safety', 'harassment', 'Harassment'),
                  ('safety', 'suspicious_activity', 'Suspicious Activity'),
                  ('safety', 'unsafe_infrastructure', 'Unsafe infrastructure'),
                  ('safety', 'poor_lighting', 'Poor lighting'),
                  ('infrastructure', 'pothole', 'Pothole'),
                  ('infrastructure', 'streetlight', 'Broken Streetlight'),
                  ('infrastructure', 'footpath', 'Damaged Footpath'),
                  ('infrastructure', 'fallen_tree', 'Fallen Tree'),
                  ('infrastructure', 'traffic_signal', 'Broken Traffic Signal'),
                  ('infrastructure', 'water_leak', 'Water Leak'),
                  ('infrastructure', 'waterlogging', 'Waterlogging / Flooding'),
                  ('infrastructure', 'obstruction', 'Road Obstruction'),
                  ('waste', 'overflowing_bin', 'Overflowing Bin'),
                  ('waste', 'illegal_dumping', 'Illegal Dumping'),
                  ('waste', 'construction_debris', 'Construction Debris'),
                  ('waste', 'garbage_burning', 'Garbage Burning'),
                  ('waste', 'dead_animal', 'Dead Animal')
                ON CONFLICT (code) DO NOTHING;
                """
            )
        )

        now = datetime.now(timezone.utc)
        records = []

        def _generate_reports(rtype: str, count: int):
            cats = CATEGORIES[rtype]
            for _ in range(count):
                user_hash = random.choice(MOCK_USERS)
                category = random.choice(cats)
                status = random.choice(STATUSES)
                severity = random.randint(1, 5)
                confidence = round(random.uniform(0.5, 0.95), 2)

                # Offset location by max ~0.025 degrees (~2.5km radius)
                lat = PUNE_LAT + random.uniform(-0.025, 0.025)
                lon = PUNE_LON + random.uniform(-0.025, 0.025)

                days_ago = random.randint(0, 90)
                submitted_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))
                moderated_at = (submitted_at + timedelta(hours=random.randint(1, 12))) if status != "pending" else None

                desc = f"Demo report for {category} ({rtype}) in Pune area."
                records.append({
                    "user_hash": user_hash,
                    "category": category,
                    "description": desc,
                    "lat": lat,
                    "lon": lon,
                    "status": status,
                    "confidence": confidence,
                    "report_type": rtype,
                    "severity": severity,
                    "submitted_at": submitted_at,
                    "moderated_at": moderated_at,
                })

        _generate_reports("safety", num_safety)
        _generate_reports("infrastructure", num_infra)
        _generate_reports("waste", num_waste)

        print(f"Seeding {len(records)} total incident reports...")

        query = text(
            """
            INSERT INTO incident_reports (
                user_hash,
                category,
                description,
                location,
                status,
                confidence,
                report_type,
                severity,
                submitted_at,
                moderated_at
            )
            VALUES (
                :user_hash,
                :category,
                :description,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                :status,
                :confidence,
                :report_type,
                :severity,
                :submitted_at,
                :moderated_at
            )
            """
        )

        for rec in records:
            await conn.execute(query, rec)

        print("Reports successfully seeded into database.")

        # Try to refresh materialized view if table exists
        try:
            await conn.execute(text("REFRESH MATERIALIZED VIEW ward_report_summary;"))
            print("Refreshed ward_report_summary materialized view.")
        except Exception as exc:
            print(f"Materialized view refresh skipped: {exc}")

    await engine.dispose()
    print("Demo seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
