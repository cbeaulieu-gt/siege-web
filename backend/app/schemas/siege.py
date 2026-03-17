from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import SiegeStatus


class SiegeCreate(BaseModel):
    date: date
    defense_scroll_count: int


class SiegeUpdate(BaseModel):
    date: date | None = None
    defense_scroll_count: int | None = None


class SiegeResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    date: date
    status: SiegeStatus
    defense_scroll_count: int
    created_at: datetime
    updated_at: datetime
