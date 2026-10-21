"""Seed heat and shade observation categories

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT INTO report_categories (module, code, label) VALUES
          ('safety', 'no_shade',          'No shade / heavy sun'),
          ('safety', 'shade_obstruction', 'Shade blocked (overgrown / construction)'),
          ('safety', 'heat_stress',       'Heat stress / too hot to walk'),
          ('safety', 'cool_spot',         'Cool shaded spot / water available')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM report_categories
        WHERE code IN (
            'no_shade',
            'shade_obstruction',
            'heat_stress',
            'cool_spot'
        );
        """
    )
