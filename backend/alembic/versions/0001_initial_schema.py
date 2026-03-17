"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-16

"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Enum types ---
    siege_status = sa.Enum("planning", "active", "complete", name="siegestatus")
    building_type = sa.Enum(
        "stronghold", "mana_shrine", "magic_tower", "defense_tower", "post",
        name="buildingtype",
    )
    member_role = sa.Enum(
        "heavy_hitter", "advanced", "medium", "novice", name="memberrole"
    )
    notification_batch_status = sa.Enum(
        "pending", "completed", name="notificationbatchstatus"
    )
    siege_status.create(op.get_bind(), checkfirst=True)
    building_type.create(op.get_bind(), checkfirst=True)
    member_role.create(op.get_bind(), checkfirst=True)
    notification_batch_status.create(op.get_bind(), checkfirst=True)

    # 1. member
    op.create_table(
        "member",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("discord_username", sa.String(), nullable=True),
        sa.Column("role", member_role, nullable=False),
        sa.Column("power", sa.Numeric(), nullable=True),
        sa.Column("sort_value", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. siege
    op.create_table(
        "siege",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            siege_status,
            nullable=False,
            server_default="planning",
        ),
        sa.Column("defense_scroll_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. building_type_config
    op.create_table(
        "building_type_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_type", building_type, nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("base_group_count", sa.Integer(), nullable=False),
        sa.Column("base_last_group_slots", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("building_type"),
    )

    # 4. post_condition
    op.create_table(
        "post_condition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("stronghold_level", sa.Integer(), nullable=False),
        sa.CheckConstraint("stronghold_level IN (1, 2, 3)", name="stronghold_level_valid"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("description"),
    )

    # 5. building
    op.create_table(
        "building",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("siege_id", sa.Integer(), nullable=False),
        sa.Column("building_type", building_type, nullable=False),
        sa.Column("building_number", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "is_broken", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.CheckConstraint(
            "building_number >= 1 AND building_number <= 18",
            name="building_number_range",
        ),
        sa.ForeignKeyConstraint(["siege_id"], ["siege.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("siege_id", "building_type", "building_number"),
    )

    # 6. building_group
    op.create_table(
        "building_group",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("group_number", sa.Integer(), nullable=False),
        sa.Column("slot_count", sa.Integer(), nullable=False, server_default="3"),
        sa.CheckConstraint(
            "group_number >= 1 AND group_number <= 9", name="group_number_range"
        ),
        sa.CheckConstraint("slot_count >= 1 AND slot_count <= 3", name="slot_count_range"),
        sa.ForeignKeyConstraint(["building_id"], ["building.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("building_id", "group_number"),
    )

    # 7. position
    op.create_table(
        "position",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("building_group_id", sa.Integer(), nullable=False),
        sa.Column("position_number", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_reserve", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.CheckConstraint("position_number >= 1", name="position_number_min"),
        sa.CheckConstraint(
            "NOT (is_disabled = TRUE AND (member_id IS NOT NULL OR is_reserve = TRUE))",
            name="disabled_position_cannot_have_member_or_reserve",
        ),
        sa.CheckConstraint(
            "NOT (is_reserve = TRUE AND member_id IS NOT NULL)",
            name="reserve_position_cannot_have_member",
        ),
        sa.ForeignKeyConstraint(
            ["building_group_id"], ["building_group.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("building_group_id", "position_number"),
    )

    # 8. post
    op.create_table(
        "post",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("siege_id", sa.Integer(), nullable=False),
        sa.Column("building_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["siege_id"], ["siege.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["building_id"], ["building.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("siege_id", "building_id"),
    )

    # 9. post_active_condition
    op.create_table(
        "post_active_condition",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("post_condition_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["post.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["post_condition_id"], ["post_condition.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("post_id", "post_condition_id"),
    )

    # 10. member_post_preference
    op.create_table(
        "member_post_preference",
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("post_condition_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["post_condition_id"], ["post_condition.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("member_id", "post_condition_id"),
    )

    # 11. siege_member
    op.create_table(
        "siege_member",
        sa.Column("siege_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("attack_day", sa.Integer(), nullable=True),
        sa.Column("has_reserve_set", sa.Boolean(), nullable=True),
        sa.Column(
            "attack_day_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.CheckConstraint(
            "attack_day IN (1, 2) OR attack_day IS NULL", name="attack_day_valid"
        ),
        sa.ForeignKeyConstraint(["siege_id"], ["siege.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("siege_id", "member_id"),
    )

    # 12. notification_batch
    op.create_table(
        "notification_batch",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("siege_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            notification_batch_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["siege_id"], ["siege.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 13. notification_batch_result
    op.create_table(
        "notification_batch_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("discord_username", sa.String(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["notification_batch.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("notification_batch_result")
    op.drop_table("notification_batch")
    op.drop_table("siege_member")
    op.drop_table("member_post_preference")
    op.drop_table("post_active_condition")
    op.drop_table("post")
    op.drop_table("position")
    op.drop_table("building_group")
    op.drop_table("building")
    op.drop_table("post_condition")
    op.drop_table("building_type_config")
    op.drop_table("siege")
    op.drop_table("member")

    bind = op.get_bind()
    sa.Enum(name="notificationbatchstatus").drop(bind, checkfirst=True)
    sa.Enum(name="memberrole").drop(bind, checkfirst=True)
    sa.Enum(name="buildingtype").drop(bind, checkfirst=True)
    sa.Enum(name="siegestatus").drop(bind, checkfirst=True)
