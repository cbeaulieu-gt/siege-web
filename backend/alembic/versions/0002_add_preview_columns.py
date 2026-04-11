"""add autofill and attack day preview columns to siege

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-17

"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("siege", sa.Column("autofill_preview", sa.JSON(), nullable=True))
    op.add_column("siege", sa.Column("autofill_preview_expires_at", sa.TIMESTAMP(), nullable=True))
    op.add_column("siege", sa.Column("attack_day_preview", sa.JSON(), nullable=True))
    op.add_column(
        "siege", sa.Column("attack_day_preview_expires_at", sa.TIMESTAMP(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("siege", "attack_day_preview_expires_at")
    op.drop_column("siege", "attack_day_preview")
    op.drop_column("siege", "autofill_preview_expires_at")
    op.drop_column("siege", "autofill_preview")
