from pydantic import BaseModel


class SiegeMemberResponse(BaseModel):
    model_config = {"from_attributes": True}
    siege_id: int
    member_id: int
    attack_day: int | None
    has_reserve_set: bool | None
    attack_day_override: bool


class SiegeMemberUpdate(BaseModel):
    attack_day: int | None = None
    has_reserve_set: bool | None = None
    attack_day_override: bool | None = None
