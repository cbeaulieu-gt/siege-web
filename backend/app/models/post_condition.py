from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.post import Post


class PostCondition(Base):
    __tablename__ = "post_condition"
    __table_args__ = (
        CheckConstraint(
            "stronghold_level IN (1, 2, 3)",
            name="stronghold_level_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    stronghold_level: Mapped[int] = mapped_column(Integer, nullable=False)

    posts: Mapped[list["Post"]] = relationship(
        secondary="post_active_condition", back_populates="active_conditions"
    )
    member_preferences: Mapped[list["Member"]] = relationship(
        secondary="member_post_preference", back_populates="post_preferences"
    )
