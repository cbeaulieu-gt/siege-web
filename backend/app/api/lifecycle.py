from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.siege import SiegeCloneResponse, SiegeResponse
from app.services import lifecycle as lifecycle_service

router = APIRouter(tags=["lifecycle"])


@router.post("/sieges/{siege_id}/activate", response_model=SiegeResponse)
async def activate_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await lifecycle_service.activate_siege(db, siege_id)


@router.post("/sieges/{siege_id}/complete", response_model=SiegeResponse)
async def complete_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await lifecycle_service.complete_siege(db, siege_id)


@router.post("/sieges/{siege_id}/clone", response_model=SiegeCloneResponse, status_code=201)
async def clone_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await lifecycle_service.clone_siege(db, siege_id)
