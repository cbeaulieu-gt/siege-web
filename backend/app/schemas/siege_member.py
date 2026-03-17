from pydantic import BaseModel, model_validator


class SiegeMemberResponse(BaseModel):
    model_config = {"from_attributes": True}
    siege_id: int
    member_id: int
    member_name: str = ""
    attack_day: int | None
    has_reserve_set: bool | None
    attack_day_override: bool

    @model_validator(mode="before")
    @classmethod
    def resolve_member_name(cls, data):
        if hasattr(data, "member") and data.member is not None:
            data.member_name = data.member.name
        return data


class SiegeMemberUpdate(BaseModel):
    attack_day: int | None = None
    has_reserve_set: bool | None = None
    attack_day_override: bool | None = None
