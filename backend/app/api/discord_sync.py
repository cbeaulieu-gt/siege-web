"""Endpoints for Discord guild member ↔ clan member sync."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.member import SyncApply, SyncApplyResponse, SyncPreviewResponse
from app.services import discord_sync as discord_sync_service

router = APIRouter(tags=["discord-sync"])


@router.post("/members/discord-sync/preview", response_model=SyncPreviewResponse)
async def preview_discord_sync(
    db: AsyncSession = Depends(get_db),
) -> SyncPreviewResponse:
    """Return proposed Discord ↔ clan member matches without writing to the DB."""
    return await discord_sync_service.preview_discord_sync(db)


@router.post("/members/discord-sync/apply", response_model=SyncApplyResponse)
async def apply_discord_sync(
    items: list[SyncApply],
    db: AsyncSession = Depends(get_db),
) -> SyncApplyResponse:
    """Apply accepted sync matches, updating discord_username and discord_id."""
    return await discord_sync_service.apply_discord_sync(db, items)
