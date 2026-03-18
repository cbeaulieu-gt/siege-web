"""Raise group_number_range constraint max from 9 to 10

Stronghold at level 6 requires 30 team slots = 10 groups of 3.
The previous cap of 9 caused a 500 error when setting level 6.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-18

"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("group_number_range", "building_group", type_="check")
    op.create_check_constraint(
        "group_number_range",
        "building_group",
        "group_number >= 1 AND group_number <= 10",
    )


def downgrade() -> None:
    op.drop_constraint("group_number_range", "building_group", type_="check")
    op.create_check_constraint(
        "group_number_range",
        "building_group",
        "group_number >= 1 AND group_number <= 9",
    )
