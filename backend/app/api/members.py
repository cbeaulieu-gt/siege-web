from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.member import (
    MemberCreate,
    MemberPreferencesUpdate,
    MemberResponse,
    MemberUpdate,
)
from app.schemas.post_condition import PostConditionResponse
from app.services import members as members_service

router = APIRouter(tags=["members"])


@router.get("/members", response_model=list[MemberResponse])
async def list_members(
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await members_service.list_members(db, is_active)


@router.post("/members", response_model=MemberResponse, status_code=201)
async def create_member(
    data: MemberCreate,
    db: AsyncSession = Depends(get_db),
):
    return await members_service.create_member(db, data)


@router.get("/members/{member_id}", response_model=MemberResponse)
async def get_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await members_service.get_member(db, member_id)


@router.put("/members/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: int,
    data: MemberUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await members_service.update_member(db, member_id, data)


@router.delete("/members/{member_id}", status_code=204)
async def delete_member(
    member_id: int,
    db: AsyncSession = Depends(get_db),
):
    await members_service.deactivate_member(db, member_id)
    return Response(status_code=204)


@router.get("/members/{member_id}/preferences", response_model=list[PostConditionResponse])
async def get_member_preferences(
    member_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await members_service.get_member_preferences(db, member_id)


@router.put("/members/{member_id}/preferences", response_model=list[PostConditionResponse])
async def set_member_preferences(
    member_id: int,
    data: MemberPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await members_service.set_member_preferences(db, member_id, data)
