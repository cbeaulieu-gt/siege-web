from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.board import BoardResponse, BulkPositionUpdate, PositionUpdate
from app.services import board as board_service

router = APIRouter(tags=["board"])


@router.get("/sieges/{siege_id}/board", response_model=BoardResponse)
async def get_board(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await board_service.get_board(db, siege_id)


@router.put("/sieges/{siege_id}/positions/{position_id}")
async def update_position(
    siege_id: int,
    position_id: int,
    data: PositionUpdate,
    db: AsyncSession = Depends(get_db),
):
    position = await board_service.update_position(db, siege_id, position_id, data)
    return {
        "id": position.id,
        "position_number": position.position_number,
        "member_id": position.member_id,
        "is_reserve": position.is_reserve,
        "is_disabled": position.is_disabled,
    }


@router.post("/sieges/{siege_id}/assignments/bulk")
async def bulk_update_positions(
    siege_id: int,
    data: BulkPositionUpdate,
    db: AsyncSession = Depends(get_db),
):
    positions = await board_service.bulk_update_positions(db, siege_id, data.updates)
    return [
        {
            "id": p.id,
            "position_number": p.position_number,
            "member_id": p.member_id,
            "is_reserve": p.is_reserve,
            "is_disabled": p.is_disabled,
        }
        for p in positions
    ]
