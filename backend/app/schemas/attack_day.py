from pydantic import BaseModel


class AttackDayAssignment(BaseModel):
    member_id: int
    attack_day: int


class AttackDayPreviewResult(BaseModel):
    assignments: list[AttackDayAssignment]
    expires_at: str


class AttackDayApplyResult(BaseModel):
    applied_count: int
