from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SiegeStatus

if TYPE_CHECKING:
    from app.models.building import Building
    from app.models.notification_batch import NotificationBatch
    from app.models.post import Post
    from app.models.siege_member import SiegeMember


class Siege(Base):
    __tablename__ = "siege"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[SiegeStatus] = mapped_column(nullable=False, default=SiegeStatus.planning)
    defense_scroll_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )
    autofill_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    autofill_preview_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    attack_day_preview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attack_day_preview_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)

    buildings: Mapped[list["Building"]] = relationship(
        back_populates="siege", cascade="all, delete-orphan", passive_deletes=True
    )
    siege_members: Mapped[list["SiegeMember"]] = relationship(
        back_populates="siege", cascade="all, delete-orphan", passive_deletes=True
    )
    posts: Mapped[list["Post"]] = relationship(
        back_populates="siege", cascade="all, delete-orphan", passive_deletes=True
    )
    notification_batches: Mapped[list["NotificationBatch"]] = relationship(
        back_populates="siege", cascade="all, delete-orphan", passive_deletes=True
    )
