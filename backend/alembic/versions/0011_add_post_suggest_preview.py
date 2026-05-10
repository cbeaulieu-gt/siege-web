"""Add post_suggest_preview columns to siege table.

Mirrors the autofill_preview / autofill_preview_expires_at pattern
already present on the siege table.

Revision ID: 0011
Revises: 0010_add_last_seen_changelog_at_to_member
Create Date: 2026-05-09
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add post_suggest_preview and post_suggest_preview_expires_at columns."""
    op.add_column("siege", sa.Column("post_suggest_preview", sa.JSON(), nullable=True))
    op.add_column(
        "siege",
        sa.Column(
            "post_suggest_preview_expires_at", sa.DateTime(), nullable=True
        ),
    )


def downgrade() -> None:
    """Drop post_suggest_preview and post_suggest_preview_expires_at columns."""
    op.drop_column("siege", "post_suggest_preview_expires_at")
    op.drop_column("siege", "post_suggest_preview")
