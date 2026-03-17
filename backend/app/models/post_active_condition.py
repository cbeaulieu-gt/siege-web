from sqlalchemy import Column, ForeignKey, Integer, Table

from app.db.base import Base

post_active_condition = Table(
    "post_active_condition",
    Base.metadata,
    Column(
        "post_id",
        Integer,
        ForeignKey("post.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    ),
    Column(
        "post_condition_id",
        Integer,
        ForeignKey("post_condition.id", ondelete="CASCADE"),
        nullable=False,
        primary_key=True,
    ),
)
