import datetime

from pydantic import BaseModel

from app.models.enums import SiegeStatus


class SiegeCreate(BaseModel):
    date: datetime.date
    defense_scroll_count: int


class SiegeUpdate(BaseModel):
    date: datetime.date | None = None
    defense_scroll_count: int | None = None


class SiegeResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    date: datetime.date | None
    status: SiegeStatus
    defense_scroll_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
