from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import SiegeStatus
from app.schemas.siege import SiegeCreate, SiegeResponse, SiegeUpdate
from app.services import sieges as sieges_service

router = APIRouter(tags=["sieges"])


@router.get("/sieges", response_model=list[SiegeResponse])
async def list_sieges(
    status: SiegeStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    sieges = await sieges_service.list_sieges(db, status)
    results = []
    for s in sieges:
        scroll_count = await sieges_service.compute_scroll_count(db, s.id)
        response = SiegeResponse.model_validate(s)
        response.computed_scroll_count = scroll_count
        results.append(response)
    return results


@router.post("/sieges", response_model=SiegeResponse, status_code=201)
async def create_siege(
    data: SiegeCreate,
    db: AsyncSession = Depends(get_db),
):
    siege = await sieges_service.create_siege(db, data)
    scroll_count = await sieges_service.compute_scroll_count(db, siege.id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response


@router.get("/sieges/{siege_id}", response_model=SiegeResponse)
async def get_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    siege = await sieges_service.get_siege(db, siege_id)
    scroll_count = await sieges_service.compute_scroll_count(db, siege_id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response


@router.put("/sieges/{siege_id}", response_model=SiegeResponse)
async def update_siege(
    siege_id: int,
    data: SiegeUpdate,
    db: AsyncSession = Depends(get_db),
):
    siege = await sieges_service.update_siege(db, siege_id, data)
    scroll_count = await sieges_service.compute_scroll_count(db, siege_id)
    response = SiegeResponse.model_validate(siege)
    response.computed_scroll_count = scroll_count
    return response


@router.delete("/sieges/{siege_id}", status_code=204)
async def delete_siege(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    await sieges_service.delete_siege(db, siege_id)
    return Response(status_code=204)
