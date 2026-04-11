"""make siege date nullable

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17

"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("siege", "date", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    # Set any NULLs to a placeholder before restoring NOT NULL
    op.execute("UPDATE siege SET date = '1970-01-01' WHERE date IS NULL")
    op.alter_column("siege", "date", existing_type=sa.Date(), nullable=False)
