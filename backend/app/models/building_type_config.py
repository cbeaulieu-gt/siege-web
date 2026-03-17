from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import BuildingType


class BuildingTypeConfig(Base):
    __tablename__ = "building_type_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    building_type: Mapped[BuildingType] = mapped_column(nullable=False, unique=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    base_group_count: Mapped[int] = mapped_column(Integer, nullable=False)
    base_last_group_slots: Mapped[int] = mapped_column(Integer, nullable=False)
