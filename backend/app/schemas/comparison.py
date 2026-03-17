from pydantic import BaseModel


class PositionKey(BaseModel):
    building_type: str
    building_number: int
    group_number: int
    position_number: int


class MemberDiff(BaseModel):
    member_id: int
    member_name: str
    added: list[PositionKey]
    removed: list[PositionKey]
    unchanged: list[PositionKey]


class ComparisonResult(BaseModel):
    siege_a_id: int
    siege_b_id: int
    members: list[MemberDiff]
