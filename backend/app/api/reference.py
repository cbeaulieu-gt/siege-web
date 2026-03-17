from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.post_condition import PostConditionResponse
from app.services import reference as reference_service

router = APIRouter(tags=["reference"])


@router.get("/post-conditions", response_model=list[PostConditionResponse])
async def get_post_conditions(
    stronghold_level: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await reference_service.get_post_conditions(db, stronghold_level)


@router.get("/building-types")
async def get_building_types(db: AsyncSession = Depends(get_db)):
    return await reference_service.get_building_types(db)


@router.get("/member-roles")
async def get_member_roles():
    return await reference_service.get_member_roles()
