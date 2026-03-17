from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.autofill import AutofillApplyResult, AutofillPreviewResult
from app.services import autofill as autofill_service

router = APIRouter(tags=["autofill"])


@router.post("/sieges/{siege_id}/auto-fill", response_model=AutofillPreviewResult)
async def preview_autofill(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await autofill_service.preview_autofill(db, siege_id)


@router.post("/sieges/{siege_id}/auto-fill/apply", response_model=AutofillApplyResult)
async def apply_autofill(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await autofill_service.apply_autofill(db, siege_id)
