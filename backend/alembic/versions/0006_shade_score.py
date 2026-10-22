"""Add shade columns to road_segments

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE road_segments
          ADD COLUMN IF NOT EXISTS shade_score FLOAT DEFAULT 0
            CHECK (shade_score >= 0 AND shade_score <= 100);
        """
    )

    op.execute(
        """
        ALTER TABLE road_segments
          ADD COLUMN IF NOT EXISTS shade_source TEXT;
        """
    )

    op.execute(
        """
        ALTER TABLE road_segments
          ADD COLUMN IF NOT EXISTS shade_updated_at TIMESTAMPTZ;
        """
    )


def downgrade():
    op.execute("ALTER TABLE road_segments DROP COLUMN IF EXISTS shade_updated_at;")
    op.execute("ALTER TABLE road_segments DROP COLUMN IF EXISTS shade_source;")
    op.execute("ALTER TABLE road_segments DROP COLUMN IF EXISTS shade_score;")
