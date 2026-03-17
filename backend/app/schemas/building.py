from pydantic import BaseModel

from app.models.enums import BuildingType


class BuildingCreate(BaseModel):
    building_type: BuildingType
    building_number: int
    level: int = 1


class BuildingUpdate(BaseModel):
    level: int | None = None
    is_broken: bool | None = None


class PositionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    position_number: int
    member_id: int | None
    is_reserve: bool
    is_disabled: bool


class BuildingGroupResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    group_number: int
    slot_count: int


class BuildingResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    siege_id: int
    building_type: BuildingType
    building_number: int
    level: int
    is_broken: bool


class GroupCreate(BaseModel):
    group_number: int
    slot_count: int = 3
