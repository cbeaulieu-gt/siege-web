"""Add last_seen_changelog_at to member

Tracks the timestamp of the last changelog entry the member has viewed,
enabling the backend to determine whether a new changelog entry exists
that the member has not yet seen.  Null means the member has never seen
the changelog.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-08

"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable last_seen_changelog_at column to the member table."""
    op.add_column(
        "member",
        sa.Column("last_seen_changelog_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Remove last_seen_changelog_at column from the member table."""
    op.drop_column("member", "last_seen_changelog_at")
