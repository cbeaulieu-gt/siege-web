"""Add description to post_priority_config"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("post_priority_config", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("post_priority_config", "description")
