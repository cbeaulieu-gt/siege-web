from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.post_condition import PostCondition
    from app.models.siege import Siege


class Post(Base):
    __tablename__ = "post"
    __table_args__ = (UniqueConstraint("siege_id", "building_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    siege_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("siege.id", ondelete="CASCADE"), nullable=False
    )
    building_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("building.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(String, nullable=True)

    siege: Mapped["Siege"] = relationship(back_populates="posts")
    building: Mapped["Building"] = relationship(back_populates="post")
    active_conditions: Mapped[list["PostCondition"]] = relationship(
        secondary="post_active_condition", back_populates="posts"
    )
