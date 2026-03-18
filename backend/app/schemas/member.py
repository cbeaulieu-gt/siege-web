from datetime import datetime

from pydantic import BaseModel

from app.models.enums import MemberRole


class MemberBase(BaseModel):
    name: str
    discord_username: str | None = None
    role: MemberRole
    power_level: str | None = None


class MemberCreate(MemberBase):
    pass


class MemberUpdate(BaseModel):
    name: str | None = None
    discord_username: str | None = None
    role: MemberRole | None = None
    power_level: str | None = None
    is_active: bool | None = None


class MemberResponse(MemberBase):
    model_config = {"from_attributes": True}
    id: int
    is_active: bool
    created_at: datetime


class MemberPreferencesUpdate(BaseModel):
    post_condition_ids: list[int]
