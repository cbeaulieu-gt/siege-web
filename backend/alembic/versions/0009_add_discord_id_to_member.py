"""Add discord_id to member

Stores the Discord snowflake ID for each clan member, enabling reliable
identity matching against guild members from the bot's /api/members endpoint.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-26

"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "member",
        sa.Column("discord_id", sa.String(), nullable=True),
    )
    op.create_unique_constraint("uq_member_discord_id", "member", ["discord_id"])


def downgrade() -> None:
    op.drop_constraint("uq_member_discord_id", "member", type_="unique")
    op.drop_column("member", "discord_id")
