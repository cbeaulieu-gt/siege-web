"""Add post_priority_config table"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_priority_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("post_number", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
        sa.UniqueConstraint("post_number"),
    )


def downgrade() -> None:
    op.drop_table("post_priority_config")
