"""Image generation endpoints."""

import base64

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.siege_member import SiegeMember
from app.services import board as board_service
from app.services import image_gen
from app.services.bot_client import bot_client
from app.services.image_gen import SiegeMemberWithName
from app.services.sieges import get_siege

router = APIRouter(tags=["images"])


class GenerateImagesResponse(BaseModel):
    assignments_image: str  # base64-encoded PNG
    reserves_image: str  # base64-encoded PNG


@router.post(
    "/sieges/{siege_id}/generate-images",
    response_model=GenerateImagesResponse,
)
async def generate_images(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate PNG images for siege assignments and members list."""
    siege = await get_siege(db, siege_id)
    siege_date = siege.date.isoformat()

    # Load board
    board_dict = await board_service.get_board(db, siege_id)
    from app.schemas.board import BoardResponse

    board = BoardResponse.model_validate(board_dict)

    # Load siege members with member data
    result = await db.execute(
        select(SiegeMember)
        .where(SiegeMember.siege_id == siege_id)
        .options(selectinload(SiegeMember.member))
    )
    siege_members = result.scalars().all()

    # Fetch Discord role colors from bot. Falls back to empty dict if bot is
    # unreachable so image generation always succeeds (names appear white).
    discord_members = await bot_client.get_members()
    discord_id_to_color: dict[str, str] = {
        m["id"]: m["top_role_color"]
        for m in discord_members
        if m.get("top_role_color") is not None
    }
    # Map internal member_id → role color via the member's discord_id field.
    member_id_to_color: dict[int, str] = {}
    for sm in siege_members:
        if sm.member is not None and sm.member.discord_id is not None:
            color = discord_id_to_color.get(sm.member.discord_id)
            if color is not None:
                member_id_to_color[sm.member_id] = color

    members_with_names = [
        SiegeMemberWithName(
            name=sm.member.name,
            role=sm.member.role,
            attack_day=sm.attack_day,
            has_reserve_set=sm.has_reserve_set,
            member_id=sm.member_id,
        )
        for sm in siege_members
        if sm.member is not None
    ]

    assignments_bytes = await image_gen.generate_assignments_image(
        board, siege_date, role_colors=member_id_to_color
    )
    reserves_bytes = await image_gen.generate_reserves_image(
        members_with_names, siege_date, role_colors=member_id_to_color
    )

    return GenerateImagesResponse(
        assignments_image=base64.b64encode(assignments_bytes).decode(),
        reserves_image=base64.b64encode(reserves_bytes).decode(),
    )
