"""Add emergency_alerts table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS emergency_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_hash TEXT NOT NULL,
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            location GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
            ) STORED,
            status TEXT NOT NULL DEFAULT 'triggered',
            message TEXT,
            contacts_notified INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMP WITH TIME ZONE,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_emergency_alerts_location
        ON emergency_alerts USING GIST(location)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_emergency_alerts_created_at
        ON emergency_alerts (created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS emergency_alerts;")
