"""Add condition_type column to post_condition table.

Adds a NOT NULL VARCHAR column with a CHECK constraint restricting values
to the seven canonical condition categories:
  role | affinity | faction | league | rarity | effect | other

Backfills existing rows from the id→type map that is the canonical source
of truth in frontend/src/lib/postConditionTypes.ts.

Revision ID: 0012
Revises: 0011_add_post_suggest_preview
Create Date: 2026-05-18
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Canonical id→condition_type map lifted verbatim from
# frontend/src/lib/postConditionTypes.ts (POST_CONDITION_TYPE_BY_ID).
# Any change to the map requires a coordinated frontend + migration update.
_CONDITION_TYPE_MAP: dict[int, str] = {
    # League (4)
    1: "league",
    2: "league",
    3: "league",
    4: "league",
    # Role (4)
    5: "role",
    6: "role",
    7: "role",
    8: "role",
    # Faction L1 (8)
    9: "faction",
    10: "faction",
    11: "faction",
    12: "faction",
    13: "faction",
    14: "faction",
    15: "faction",
    16: "faction",
    # Effect L1 (2)
    17: "effect",
    18: "effect",
    # Affinity (4)
    19: "affinity",
    20: "affinity",
    21: "affinity",
    22: "affinity",
    # Faction L2 (4)
    23: "faction",
    24: "faction",
    25: "faction",
    26: "faction",
    # Effect L2 (2)
    27: "effect",
    28: "effect",
    # Rarity (3)
    29: "rarity",
    30: "rarity",
    31: "rarity",
    # Faction L3 (3)
    32: "faction",
    33: "faction",
    34: "faction",
    # Effect L3 (1)
    35: "effect",
    # Other (1)
    36: "other",
}


def upgrade() -> None:
    """Add condition_type column, backfill from canonical map, enforce NOT NULL."""
    # Step 1: Add column as nullable so existing rows don't immediately violate
    # NOT NULL. The CHECK constraint is added after the backfill.
    op.add_column(
        "post_condition",
        sa.Column("condition_type", sa.String(), nullable=True),
    )

    # Step 2: Backfill each row from the canonical id→type map.
    connection = op.get_bind()
    for id_, condition_type in _CONDITION_TYPE_MAP.items():
        connection.execute(
            sa.text(
                "UPDATE post_condition SET condition_type = :ct WHERE id = :id"
            ),
            {"ct": condition_type, "id": id_},
        )

    # Step 3: Enforce NOT NULL now that all rows are populated.
    op.alter_column(
        "post_condition",
        "condition_type",
        nullable=False,
    )

    # Step 4: Add the CHECK constraint.
    op.create_check_constraint(
        "condition_type_valid",
        "post_condition",
        "condition_type IN ('role','affinity','faction','league','rarity','effect','other')",
    )


def downgrade() -> None:
    """Drop condition_type column and its CHECK constraint."""
    op.drop_constraint(
        "condition_type_valid",
        "post_condition",
        type_="check",
    )
    op.drop_column("post_condition", "condition_type")
