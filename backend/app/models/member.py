from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MemberRole

if TYPE_CHECKING:
    from app.models.position import Position
    from app.models.post_condition import PostCondition
    from app.models.siege_member import SiegeMember


class Member(Base):
    __tablename__ = "member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    discord_username: Mapped[str | None] = mapped_column(String, nullable=True)
    discord_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    role: Mapped[MemberRole] = mapped_column(nullable=False)
    power_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    positions: Mapped[list["Position"]] = relationship(back_populates="member")
    siege_members: Mapped[list["SiegeMember"]] = relationship(back_populates="member")
    post_preferences: Mapped[list["PostCondition"]] = relationship(
        secondary="member_post_preference", back_populates="member_preferences"
    )
