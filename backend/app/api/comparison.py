from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.siege import Siege
from app.schemas.comparison import ComparisonResult
from app.services import comparison as comparison_service

router = APIRouter(tags=["comparison"])


@router.get("/sieges/{siege_id}/compare", response_model=ComparisonResult)
async def compare_with_most_recent(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Siege).where(Siege.id == siege_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Siege not found")

    other = await comparison_service.get_most_recent_completed(db, exclude_siege_id=siege_id)
    if other is None:
        raise HTTPException(status_code=404, detail="No completed siege found to compare against")

    return await comparison_service.compare_sieges(db, siege_id, other.id)


@router.get("/sieges/{siege_id}/compare/{other_id}", response_model=ComparisonResult)
async def compare_with_specific(
    siege_id: int,
    other_id: int,
    db: AsyncSession = Depends(get_db),
):
    results = await db.execute(
        select(Siege).where(Siege.id.in_([siege_id, other_id]))
    )
    found_ids = {s.id for s in results.scalars().all()}
    if siege_id not in found_ids:
        raise HTTPException(status_code=404, detail="Siege not found")
    if other_id not in found_ids:
        raise HTTPException(status_code=404, detail="Other siege not found")

    return await comparison_service.compare_sieges(db, siege_id, other_id)
