from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PostPriorityConfig(Base):
    __tablename__ = "post_priority_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
