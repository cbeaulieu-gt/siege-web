from pydantic import BaseModel


class AutofillAssignment(BaseModel):
    position_id: int
    member_id: int | None
    is_reserve: bool


class AutofillPreviewResult(BaseModel):
    assignments: list[AutofillAssignment]
    expires_at: str


class AutofillApplyResult(BaseModel):
    applied_count: int
    reserve_count: int
