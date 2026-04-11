"""Add description to post_priority_config"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("post_priority_config", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("post_priority_config", "description")
