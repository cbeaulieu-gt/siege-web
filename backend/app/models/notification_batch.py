from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import NotificationBatchStatus

if TYPE_CHECKING:
    from app.models.notification_batch_result import NotificationBatchResult
    from app.models.siege import Siege


class NotificationBatch(Base):
    __tablename__ = "notification_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    siege_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("siege.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[NotificationBatchStatus] = mapped_column(
        nullable=False, default=NotificationBatchStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    siege: Mapped["Siege"] = relationship(back_populates="notification_batches")
    results: Mapped[list["NotificationBatchResult"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True
    )
