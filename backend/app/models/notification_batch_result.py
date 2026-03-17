from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.notification_batch import NotificationBatch


class NotificationBatchResult(Base):
    __tablename__ = "notification_batch_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("notification_batch.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    discord_username: Mapped[str | None] = mapped_column(String, nullable=True)
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)

    batch: Mapped["NotificationBatch"] = relationship(back_populates="results")
