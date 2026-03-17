from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.attack_day import AttackDayApplyResult, AttackDayPreviewResult
from app.services import attack_day as attack_day_service

router = APIRouter(tags=["attack_day"])


@router.post(
    "/sieges/{siege_id}/members/auto-assign-attack-day",
    response_model=AttackDayPreviewResult,
)
async def preview_attack_day(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await attack_day_service.preview_attack_day(db, siege_id)


@router.post(
    "/sieges/{siege_id}/members/auto-assign-attack-day/apply",
    response_model=AttackDayApplyResult,
)
async def apply_attack_day(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await attack_day_service.apply_attack_day(db, siege_id)
