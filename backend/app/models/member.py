from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MemberRole

if TYPE_CHECKING:
    from app.models.position import Position
    from app.models.siege_member import SiegeMember
    from app.models.post_condition import PostCondition


class Member(Base):
    __tablename__ = "member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    discord_username: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[MemberRole] = mapped_column(nullable=False)
    power: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    sort_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )

    positions: Mapped[list["Position"]] = relationship(
        back_populates="member"
    )
    siege_members: Mapped[list["SiegeMember"]] = relationship(
        back_populates="member"
    )
    post_preferences: Mapped[list["PostCondition"]] = relationship(
        secondary="member_post_preference", back_populates="member_preferences"
    )
