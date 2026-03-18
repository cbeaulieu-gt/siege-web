from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.siege import SiegeResponse
from app.services import lifecycle as lifecycle_service
from app.services import sieges as sieges_service

router = APIRouter(tags=["lifecycle"])


@router.post("/sieges/{siege_id}/activate", response_model=SiegeResponse)
async def activate_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    siege = await lifecycle_service.activate_siege(db, siege_id)
    scroll_count = await sieges_service.compute_scroll_count(db, siege_id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response


@router.post("/sieges/{siege_id}/complete", response_model=SiegeResponse)
async def complete_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    siege = await lifecycle_service.complete_siege(db, siege_id)
    scroll_count = await sieges_service.compute_scroll_count(db, siege_id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response


@router.post("/sieges/{siege_id}/reopen", response_model=SiegeResponse)
async def reopen_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    siege = await lifecycle_service.reopen_siege(db, siege_id)
    scroll_count = await sieges_service.compute_scroll_count(db, siege_id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response


@router.post("/sieges/{siege_id}/clone", response_model=SiegeResponse, status_code=201)
async def clone_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    siege = await lifecycle_service.clone_siege(db, siege_id)
    scroll_count = await sieges_service.compute_scroll_count(db, siege.id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response
