"""Replace power with power_level, drop sort_value"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("member", sa.Column("power_level", sa.String(20), nullable=True))
    op.drop_column("member", "power")
    op.drop_column("member", "sort_value")


def downgrade() -> None:
    op.add_column("member", sa.Column("sort_value", sa.Integer(), nullable=True))
    op.add_column("member", sa.Column("power", sa.Numeric(), nullable=True))
    op.drop_column("member", "power_level")
