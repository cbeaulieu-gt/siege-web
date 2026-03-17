from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.validation import ValidationResult
from app.services import validation as validation_service
from sqlalchemy import select
from app.models.siege import Siege

router = APIRouter(tags=["validation"])


@router.post("/sieges/{siege_id}/validate", response_model=ValidationResult)
async def validate_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Siege).where(Siege.id == siege_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Siege not found")
    return await validation_service.validate_siege(db, siege_id)
