from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.building import (
    BuildingCreate,
    BuildingGroupResponse,
    BuildingResponse,
    BuildingUpdate,
    GroupCreate,
)
from app.services import buildings as buildings_service

router = APIRouter(tags=["buildings"])


@router.get("/sieges/{siege_id}/buildings", response_model=list[BuildingResponse])
async def list_buildings(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await buildings_service.list_buildings(db, siege_id)


@router.post("/sieges/{siege_id}/buildings", response_model=BuildingResponse, status_code=201)
async def add_building(
    siege_id: int,
    data: BuildingCreate,
    db: AsyncSession = Depends(get_db),
):
    return await buildings_service.add_building(db, siege_id, data)


@router.put("/sieges/{siege_id}/buildings/{building_id}", response_model=BuildingResponse)
async def update_building(
    siege_id: int,
    building_id: int,
    data: BuildingUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await buildings_service.update_building(db, siege_id, building_id, data)


@router.delete("/sieges/{siege_id}/buildings/{building_id}", status_code=204)
async def delete_building(
    siege_id: int,
    building_id: int,
    db: AsyncSession = Depends(get_db),
):
    await buildings_service.delete_building(db, siege_id, building_id)
    return Response(status_code=204)


@router.post(
    "/sieges/{siege_id}/buildings/{building_id}/groups",
    response_model=BuildingGroupResponse,
    status_code=201,
)
async def add_group(
    siege_id: int,
    building_id: int,
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
):
    return await buildings_service.add_group(db, siege_id, building_id, data)


@router.delete("/sieges/{siege_id}/buildings/{building_id}/groups/{group_id}", status_code=204)
async def delete_group(
    siege_id: int,
    building_id: int,
    group_id: int,
    db: AsyncSession = Depends(get_db),
):
    await buildings_service.delete_group(db, siege_id, building_id, group_id)
    return Response(status_code=204)
