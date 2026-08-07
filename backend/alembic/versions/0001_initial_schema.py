"""Initial schema - road_segments, safety_zones, incident_reports

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS road_segments (
            id              BIGSERIAL PRIMARY KEY,
            osm_way_id      BIGINT NOT NULL,
            geometry        GEOMETRY(LINESTRING, 4326) NOT NULL,
            safety_score    FLOAT NOT NULL CHECK (safety_score >= 0 AND safety_score <= 100),
            road_type       TEXT,
            lighting        BOOLEAN DEFAULT FALSE,
            dataset_version TEXT NOT NULL,
            updated_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS safety_zones (
            id              BIGSERIAL PRIMARY KEY,
            zone_id         TEXT NOT NULL UNIQUE,
            geometry        GEOMETRY(POLYGON, 4326) NOT NULL,
            risk_level      TEXT NOT NULL CHECK (risk_level IN ('safe', 'cautious', 'risky')),
            risk_score      FLOAT NOT NULL,
            dataset_version TEXT NOT NULL,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'incident_reports'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'incident_reports'
                  AND column_name = 'location'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'incident_reports_legacy_backup'
            ) THEN
                ALTER TABLE incident_reports RENAME TO incident_reports_legacy_backup;
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS incident_reports (
            id              BIGSERIAL PRIMARY KEY,
            user_hash       TEXT NOT NULL,
            category        TEXT NOT NULL,
            description     TEXT,
            location        GEOMETRY(POINT, 4326) NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'verified', 'rejected')),
            confidence      FLOAT DEFAULT 0.5,
            submitted_at    TIMESTAMPTZ DEFAULT NOW(),
            moderated_at    TIMESTAMPTZ,
            moderated_by    TEXT
        );
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'incident_reports_legacy_backup'
            ) THEN
                INSERT INTO incident_reports (
                    user_hash,
                    category,
                    description,
                    location,
                    status,
                    confidence,
                    submitted_at
                )
                SELECT
                    'legacy-import',
                    COALESCE(incident_type, 'unknown'),
                    description,
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                    'pending',
                    0.5,
                    COALESCE(created_at AT TIME ZONE 'UTC', NOW())
                FROM incident_reports_legacy_backup
                WHERE latitude IS NOT NULL
                  AND longitude IS NOT NULL;
            END IF;
        END $$;
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_road_segments_geom ON road_segments USING GIST (geometry);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_safety_zones_geom ON safety_zones USING GIST (geometry);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_geom ON incident_reports USING GIST (location);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incident_reports (status);"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS incident_reports;")
    op.execute("DROP TABLE IF EXISTS safety_zones;")
    op.execute("DROP TABLE IF EXISTS road_segments;")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'incident_reports_legacy_backup'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'incident_reports'
            ) THEN
                ALTER TABLE incident_reports_legacy_backup RENAME TO incident_reports;
            END IF;
        END $$;
        """
    )
