import datetime

from pydantic import BaseModel

from app.models.enums import SiegeStatus


class SiegeCreate(BaseModel):
    date: datetime.date


class SiegeUpdate(BaseModel):
    date: datetime.date | None = None


class SiegeResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    date: datetime.date | None
    status: SiegeStatus
    defense_scroll_count: int
    computed_scroll_count: int = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime
