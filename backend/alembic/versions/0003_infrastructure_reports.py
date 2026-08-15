"""Add report_type and severity to incident_reports, add report_categories table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-15
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add report_type column
    op.execute(
        """
        ALTER TABLE incident_reports
        ADD COLUMN IF NOT EXISTS report_type TEXT NOT NULL DEFAULT 'safety';
        """
    )

    # 2. Add severity column
    op.execute(
        """
        ALTER TABLE incident_reports
        ADD COLUMN IF NOT EXISTS severity INTEGER NOT NULL DEFAULT 3
        CHECK (severity >= 1 AND severity <= 5);
        """
    )

    # 3. Create report_categories reference table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS report_categories (
            id          SERIAL PRIMARY KEY,
            module      TEXT NOT NULL,
            code        TEXT NOT NULL UNIQUE,
            label       TEXT NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )

    # 4. Seed safety categories
    op.execute(
        """
        INSERT INTO report_categories (module, code, label) VALUES
          ('safety', 'stalking', 'Stalking'),
          ('safety', 'harassment', 'Harassment'),
          ('safety', 'suspicious_activity', 'Suspicious Activity'),
          ('safety', 'unsafe_infrastructure', 'Unsafe infrastructure'),
          ('safety', 'poor_lighting', 'Poor lighting')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # 5. Seed infrastructure categories
    op.execute(
        """
        INSERT INTO report_categories (module, code, label) VALUES
          ('infrastructure', 'pothole', 'Pothole'),
          ('infrastructure', 'streetlight', 'Broken Streetlight'),
          ('infrastructure', 'footpath', 'Damaged Footpath'),
          ('infrastructure', 'fallen_tree', 'Fallen Tree'),
          ('infrastructure', 'traffic_signal', 'Broken Traffic Signal'),
          ('infrastructure', 'water_leak', 'Water Leak'),
          ('infrastructure', 'waterlogging', 'Waterlogging / Flooding'),
          ('infrastructure', 'obstruction', 'Road Obstruction')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # 6. Create index on report_type
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_incidents_report_type
        ON incident_reports (report_type);
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_incidents_report_type;")
    op.execute("DROP TABLE IF EXISTS report_categories;")
    op.execute("ALTER TABLE incident_reports DROP COLUMN IF EXISTS severity;")
    op.execute("ALTER TABLE incident_reports DROP COLUMN IF EXISTS report_type;")
