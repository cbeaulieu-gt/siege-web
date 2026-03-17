from pydantic import BaseModel

from app.models.enums import BuildingType


class PositionBoardResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    position_number: int
    member_id: int | None
    member_name: str | None  # denormalized for display
    is_reserve: bool
    is_disabled: bool


class GroupBoardResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    group_number: int
    slot_count: int
    positions: list[PositionBoardResponse]


class BuildingBoardResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    building_type: BuildingType
    building_number: int
    level: int
    is_broken: bool
    groups: list[GroupBoardResponse]


class BoardResponse(BaseModel):
    siege_id: int
    buildings: list[BuildingBoardResponse]


class PositionUpdate(BaseModel):
    member_id: int | None = None
    is_reserve: bool = False
    is_disabled: bool = False


class BulkPositionUpdate(BaseModel):
    updates: list[dict]  # list of {position_id: int, member_id, is_reserve, is_disabled}
