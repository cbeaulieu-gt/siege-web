"""Notification endpoints — send DMs and post images to Discord."""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import AsyncSessionLocal, get_db
from app.models.enums import NotificationBatchStatus, SiegeStatus
from app.models.notification_batch import NotificationBatch
from app.models.notification_batch_result import NotificationBatchResult
from app.models.siege_member import SiegeMember
from app.services import board as board_service
from app.services import image_gen
from app.services.bot_client import bot_client
from app.services.image_gen import SiegeMemberWithName
from app.services.sieges import get_siege
from app.services.validation import validate_siege

router = APIRouter(tags=["notifications"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class NotifyResponse(BaseModel):
    batch_id: int
    status: str
    member_count: int
    skipped_count: int  # members skipped (no discord_username or not in guild)


class NotificationResultItem(BaseModel):
    member_id: int
    member_name: str
    discord_username: str | None
    success: bool | None
    error: str | None
    sent_at: str | None


class NotificationBatchResponse(BaseModel):
    batch_id: int
    status: str
    results: list[NotificationResultItem]


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _send_dms(batch_id: int, members_data: list[dict]) -> None:
    """Send DMs for each member and record results in a fresh DB session."""
    async with AsyncSessionLocal() as session:
        try:
            for item in members_data:
                member_id = item["member_id"]
                discord_username = item["discord_username"]
                message = item["message"]

                success = False
                error_text: str | None = None
                sent_at: datetime | None = None

                if discord_username:
                    ok = await bot_client.notify(discord_username, message)
                    success = ok
                    if not ok:
                        error_text = "Bot failed to deliver message"
                    else:
                        sent_at = datetime.now(UTC)
                else:
                    error_text = "No discord_username set for member"

                result_row = await session.execute(
                    select(NotificationBatchResult).where(
                        NotificationBatchResult.batch_id == batch_id,
                        NotificationBatchResult.member_id == member_id,
                    )
                )
                result = result_row.scalar_one_or_none()
                if result is not None:
                    result.success = success
                    result.error = error_text
                    result.sent_at = sent_at

            batch_row = await session.execute(
                select(NotificationBatch).where(NotificationBatch.id == batch_id)
            )
            batch = batch_row.scalar_one_or_none()
            if batch is not None:
                batch.status = NotificationBatchStatus.completed

            await session.commit()
        except Exception:
            # Guarantee the batch is marked completed even if a mid-loop exception
            # occurs. BackgroundTasks swallow exceptions silently, so without this
            # the batch would remain "pending" forever.
            batch_row = await session.execute(
                select(NotificationBatch).where(NotificationBatch.id == batch_id)
            )
            batch = batch_row.scalar_one_or_none()
            if batch is not None and batch.status == NotificationBatchStatus.pending:
                batch.status = NotificationBatchStatus.completed
            await session.commit()
            raise


# ---------------------------------------------------------------------------
# POST /api/sieges/{siege_id}/notify
# ---------------------------------------------------------------------------


@router.post("/sieges/{siege_id}/notify", response_model=NotifyResponse)
async def notify_siege_members(
    siege_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Send DM notifications to all siege members asynchronously."""
    siege = await get_siege(db, siege_id)
    if siege.status == SiegeStatus.complete:
        raise HTTPException(status_code=400, detail="Cannot notify for a completed siege")

    validation = await validate_siege(db, siege_id)
    if validation.errors:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot notify: siege has {len(validation.errors)} validation error(s). "
                "Resolve all errors before sending notifications."
            ),
        )

    # Load siege members with member data
    result = await db.execute(
        select(SiegeMember)
        .where(SiegeMember.siege_id == siege_id)
        .options(selectinload(SiegeMember.member))
    )
    siege_members = result.scalars().all()

    # Pre-filter: fetch live guild members from bot to exclude non-members.
    # get_members() returns [] when the bot is unreachable — in that case we
    # fall back to filtering only on discord_username being set, so a bot
    # outage never silently cancels all DMs.
    guild_members = await bot_client.get_members()
    guild_usernames: set[str] = {m["username"].lower() for m in guild_members}
    bot_reachable = len(guild_usernames) > 0

    eligible: list[SiegeMember] = []
    skipped_count = 0
    for sm in siege_members:
        uname = sm.member.discord_username if sm.member else None
        if uname is None:
            skipped_count += 1
        elif bot_reachable and uname.lower() not in guild_usernames:
            skipped_count += 1
        else:
            eligible.append(sm)

    # Create batch
    batch = NotificationBatch(siege_id=siege_id, status=NotificationBatchStatus.pending)
    db.add(batch)
    await db.flush()

    # Create result rows only for eligible members
    message = "Siege assignments are ready! Check the latest siege board at <URL>."
    members_data: list[dict] = []
    for sm in eligible:
        result_row = NotificationBatchResult(
            batch_id=batch.id,
            member_id=sm.member_id,
            discord_username=sm.member.discord_username if sm.member else None,
        )
        db.add(result_row)
        members_data.append(
            {
                "member_id": sm.member_id,
                "discord_username": sm.member.discord_username if sm.member else None,
                "message": message,
            }
        )

    await db.commit()

    background_tasks.add_task(_send_dms, batch.id, members_data)

    return NotifyResponse(
        batch_id=batch.id,
        status=batch.status.value,
        member_count=len(eligible),
        skipped_count=skipped_count,
    )


# ---------------------------------------------------------------------------
# GET /api/sieges/{siege_id}/notify/{batch_id}
# ---------------------------------------------------------------------------


@router.get(
    "/sieges/{siege_id}/notify/{batch_id}",
    response_model=NotificationBatchResponse,
)
async def get_notification_batch(
    siege_id: int,
    batch_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the status and results of a notification batch."""
    result = await db.execute(
        select(NotificationBatch)
        .where(
            NotificationBatch.id == batch_id,
            NotificationBatch.siege_id == siege_id,
        )
        .options(
            selectinload(NotificationBatch.results).selectinload(NotificationBatchResult.batch)
        )
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Notification batch not found")

    # Load results with member names via separate query
    results_q = await db.execute(
        select(NotificationBatchResult)
        .where(NotificationBatchResult.batch_id == batch_id)
        .options(selectinload(NotificationBatchResult.batch))
    )
    result_rows = results_q.scalars().all()

    # Load member names
    from app.models.member import Member

    member_ids = [r.member_id for r in result_rows]
    members_q = await db.execute(select(Member).where(Member.id.in_(member_ids)))
    members_by_id = {m.id: m for m in members_q.scalars().all()}

    items = [
        NotificationResultItem(
            member_id=r.member_id,
            member_name=members_by_id.get(r.member_id, None)
            and members_by_id[r.member_id].name
            or "Unknown",
            discord_username=r.discord_username,
            success=r.success,
            error=r.error,
            sent_at=r.sent_at.isoformat() if r.sent_at is not None else None,
        )
        for r in result_rows
    ]

    return NotificationBatchResponse(
        batch_id=batch.id,
        status=batch.status.value,
        results=items,
    )


# ---------------------------------------------------------------------------
# POST /api/sieges/{siege_id}/post-to-channel
# ---------------------------------------------------------------------------


@router.post("/sieges/{siege_id}/post-to-channel")
async def post_to_channel(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Generate images and post them + a summary message to Discord channels."""
    siege = await get_siege(db, siege_id)
    siege_date = siege.date.isoformat()

    # Load board
    board_dict = await board_service.get_board(db, siege_id)
    from app.schemas.board import BoardResponse as BoardResp

    board = BoardResp.model_validate(board_dict)

    # Load siege members with member data
    sm_result = await db.execute(
        select(SiegeMember)
        .where(SiegeMember.siege_id == siege_id)
        .options(selectinload(SiegeMember.member))
    )
    siege_members = sm_result.scalars().all()

    # Fetch Discord role colors from bot. Falls back to empty dict if bot is
    # unreachable so image generation always succeeds (names appear white).
    discord_members = await bot_client.get_members()
    discord_id_to_color: dict[str, str] = {
        m["id"]: m["top_role_color"] for m in discord_members if m.get("top_role_color") is not None
    }
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

    # Generate images
    assignments_bytes = await image_gen.generate_assignments_image(
        board, siege_date, role_colors=member_id_to_color
    )
    reserves_bytes = await image_gen.generate_reserves_image(
        members_with_names, siege_date, role_colors=member_id_to_color
    )

    images_channel = settings.discord_siege_images_channel
    text_channel = settings.discord_siege_channel

    url1 = await bot_client.post_image(
        images_channel, assignments_bytes, f"assignments-{siege_date}.png"
    )
    if url1 is None:
        return {"status": "failed", "detail": "Failed to post assignments image"}

    url2 = await bot_client.post_image(images_channel, reserves_bytes, f"reserves-{siege_date}.png")
    if url2 is None:
        return {"status": "failed", "detail": "Failed to post reserves image"}

    summary = f"Siege assignments for {siege_date}:\nAssignments: {url1}\nReserves: {url2}"
    ok3 = await bot_client.post_message(text_channel, summary)
    if not ok3:
        return {"status": "failed", "detail": "Failed to post summary message"}

    return {"status": "posted"}
