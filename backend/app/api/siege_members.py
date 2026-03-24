from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.siege_member import MemberPreferenceSummary, SiegeMemberResponse, SiegeMemberUpdate
from app.services import siege_members as siege_members_service

router = APIRouter(tags=["siege_members"])


class SiegeMemberCreate(BaseModel):
    member_id: int


@router.get(
    "/sieges/{siege_id}/members/preferences",
    response_model=list[MemberPreferenceSummary],
)
async def get_siege_member_preferences(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await siege_members_service.get_siege_member_preferences(db, siege_id)


@router.get("/sieges/{siege_id}/members", response_model=list[SiegeMemberResponse])
async def list_siege_members(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await siege_members_service.list_siege_members(db, siege_id)


@router.post("/sieges/{siege_id}/members", response_model=SiegeMemberResponse, status_code=201)
async def add_siege_member(
    siege_id: int,
    data: SiegeMemberCreate,
    db: AsyncSession = Depends(get_db),
):
    return await siege_members_service.add_siege_member(db, siege_id, data.member_id)


@router.put("/sieges/{siege_id}/members/{member_id}", response_model=SiegeMemberResponse)
async def update_siege_member(
    siege_id: int,
    member_id: int,
    data: SiegeMemberUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await siege_members_service.update_siege_member(db, siege_id, member_id, data)
