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
    discord_id: str | None = None
    is_active: bool
    created_at: datetime


class MemberPreferencesUpdate(BaseModel):
    post_condition_ids: list[int]


# ---------------------------------------------------------------------------
# Discord sync schemas
# ---------------------------------------------------------------------------


class SyncMatch(BaseModel):
    member_id: int
    member_name: str
    current_discord_username: str | None
    proposed_discord_username: str
    proposed_discord_id: str
    confidence: str  # "exact" | "suggested" | "ambiguous"


class SyncPreviewResponse(BaseModel):
    matches: list[SyncMatch]
    unmatched_guild_members: list[str]  # guild usernames with no clan match
    unmatched_clan_members: list[str]  # clan member names with no guild match


class SyncApply(BaseModel):
    member_id: int
    discord_username: str
    discord_id: str


class SyncApplyResponse(BaseModel):
    updated: int
