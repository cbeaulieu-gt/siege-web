from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.building_group import BuildingGroup
    from app.models.member import Member
    from app.models.post_condition import PostCondition


class Position(Base):
    __tablename__ = "position"
    __table_args__ = (
        UniqueConstraint("building_group_id", "position_number"),
        CheckConstraint(
            "position_number >= 1",
            name="position_number_min",
        ),
        CheckConstraint(
            "NOT (is_disabled = TRUE AND (member_id IS NOT NULL OR is_reserve = TRUE))",
            name="disabled_position_cannot_have_member_or_reserve",
        ),
        CheckConstraint(
            "NOT (is_reserve = TRUE AND member_id IS NOT NULL)",
            name="reserve_position_cannot_have_member",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("building_group.id", ondelete="CASCADE"), nullable=False
    )
    position_number: Mapped[int] = mapped_column(Integer, nullable=False)
    member_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    is_reserve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    matched_condition_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("post_condition.id", ondelete="SET NULL"), nullable=True
    )

    group: Mapped["BuildingGroup"] = relationship(back_populates="positions")
    member: Mapped["Member | None"] = relationship(back_populates="positions")
    matched_condition: Mapped["PostCondition | None"] = relationship()
