"""Add matched_condition_id to position

Tracks which PostCondition a member was matched on when assigned to a post.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-18

"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "position",
        sa.Column(
            "matched_condition_id",
            sa.Integer(),
            sa.ForeignKey("post_condition.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("position", "matched_condition_id")
