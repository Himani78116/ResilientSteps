"""Create wards table and ward_report_summary materialized view

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-15
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wards (
            id          SERIAL PRIMARY KEY,
            ward_id     TEXT NOT NULL UNIQUE,
            ward_name   TEXT NOT NULL,
            geometry    GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
            zone        TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_wards_geom ON wards USING GIST (geometry);
        """
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS ward_report_summary AS
        SELECT
            w.ward_id,
            w.ward_name,
            ir.report_type,
            ir.status,
            COUNT(*) AS report_count,
            AVG(ir.severity) AS avg_severity,
            MAX(ir.submitted_at) AS latest_report_at
        FROM wards w
        JOIN incident_reports ir
          ON ST_Contains(w.geometry, ir.location::geometry)
        GROUP BY w.ward_id, w.ward_name, ir.report_type, ir.status;
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ward_report_summary_pk
          ON ward_report_summary (ward_id, report_type, status);
        """
    )


def downgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ward_report_summary;")
    op.execute("DROP INDEX IF EXISTS idx_wards_geom;")
    op.execute("DROP TABLE IF EXISTS wards;")
