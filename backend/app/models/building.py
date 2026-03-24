from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BuildingType

if TYPE_CHECKING:
    from app.models.building_group import BuildingGroup
    from app.models.post import Post
    from app.models.siege import Siege


class Building(Base):
    __tablename__ = "building"
    __table_args__ = (
        UniqueConstraint("siege_id", "building_type", "building_number"),
        CheckConstraint(
            "building_number >= 1 AND building_number <= 18",
            name="building_number_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    siege_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("siege.id", ondelete="CASCADE"), nullable=False
    )
    building_type: Mapped[BuildingType] = mapped_column(nullable=False)
    building_number: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_broken: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    siege: Mapped["Siege"] = relationship(back_populates="buildings")
    groups: Mapped[list["BuildingGroup"]] = relationship(
        back_populates="building", cascade="all, delete-orphan", passive_deletes=True
    )
    post: Mapped["Post | None"] = relationship(back_populates="building", uselist=False)
