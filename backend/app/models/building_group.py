from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.position import Position


class BuildingGroup(Base):
    __tablename__ = "building_group"
    __table_args__ = (
        UniqueConstraint("building_id", "group_number"),
        CheckConstraint(
            "group_number >= 1 AND group_number <= 10",
            name="group_number_range",
        ),
        CheckConstraint(
            "slot_count >= 1 AND slot_count <= 3",
            name="slot_count_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("building.id", ondelete="CASCADE"), nullable=False
    )
    group_number: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    building: Mapped["Building"] = relationship(back_populates="groups")
    positions: Mapped[list["Position"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", passive_deletes=True
    )
