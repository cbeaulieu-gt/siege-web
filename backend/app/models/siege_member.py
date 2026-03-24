from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.member import Member
    from app.models.siege import Siege


class SiegeMember(Base):
    __tablename__ = "siege_member"
    __table_args__ = (
        CheckConstraint(
            "attack_day IN (1, 2) OR attack_day IS NULL",
            name="attack_day_valid",
        ),
    )

    siege_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("siege.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False, primary_key=True
    )
    attack_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_reserve_set: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attack_day_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    siege: Mapped["Siege"] = relationship(back_populates="siege_members")
    member: Mapped["Member"] = relationship(back_populates="siege_members")
