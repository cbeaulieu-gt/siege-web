from sqlalchemy import Column, ForeignKey, Integer, Table

from app.db.base import Base

member_post_preference = Table(
    "member_post_preference",
    Base.metadata,
    Column(
        "member_id",
        Integer,
        ForeignKey("member.id", ondelete="CASCADE"),
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
