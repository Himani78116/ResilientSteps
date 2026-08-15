"""Seed waste management categories into report_categories

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-15
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO report_categories (module, code, label, description) VALUES
          ('waste', 'overflowing_bin', 'Overflowing Bin', 'Public waste bin overflowing onto street or footpath'),
          ('waste', 'illegal_dumping', 'Illegal Dumping', 'Waste dumped in unauthorized location'),
          ('waste', 'construction_debris', 'Construction Debris', 'Building materials or rubble left on road/footpath'),
          ('waste', 'garbage_burning', 'Garbage Burning', 'Open burning of waste'),
          ('waste', 'dead_animal', 'Dead Animal', 'Animal carcass on road or public area')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade():
    op.execute("DELETE FROM report_categories WHERE module = 'waste';")
