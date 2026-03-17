from pydantic import BaseModel

from app.schemas.post_condition import PostConditionResponse


class PostResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    siege_id: int
    building_id: int
    building_number: int  # denormalized for display
    priority: int
    description: str | None
    active_conditions: list[PostConditionResponse]


class PostUpdate(BaseModel):
    priority: int | None = None
    description: str | None = None


class PostConditionsUpdate(BaseModel):
    post_condition_ids: list[int]  # 0 to 3 items
