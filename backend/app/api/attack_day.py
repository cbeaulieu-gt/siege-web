"""API routes for the attack-day auto-assign feature.

``preview_attack_day`` runs the assignment algorithm and stores the result
temporarily.  ``apply_attack_day`` commits the stored preview to
``SiegeMember.attack_day`` and then fans out one day-role-sync webhook
call per affected member via FastAPI ``BackgroundTasks``.

All fan-out calls share a single ``correlation_id`` generated here (one
per user action, per contract §8).  ``assigned_at`` timestamps are sourced
from PostgreSQL ``clock_timestamp()`` inside the service layer — each
``AppliedMemberEntry`` carries its own timestamp captured at mutation time
so the receiver can apply monotonic ordering (§7).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._role_sync import schedule_role_sync
from app.db.session import get_db
from app.schemas.attack_day import AttackDayApplyResult, AttackDayPreviewResult
from app.services import attack_day as attack_day_service

router = APIRouter(tags=["attack_day"])


@router.post(
    "/sieges/{siege_id}/members/auto-assign-attack-day",
    response_model=AttackDayPreviewResult,
)
async def preview_attack_day(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Run the attack-day auto-assign algorithm and store the preview."""
    return await attack_day_service.preview_attack_day(db, siege_id)


@router.post(
    "/sieges/{siege_id}/members/auto-assign-attack-day/apply",
    response_model=AttackDayApplyResult,
    response_model_exclude={"applied_members"},
)
async def apply_attack_day(
    siege_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Commit the stored attack-day preview to SiegeMember records.

    After the DB commit, fans out one day-role-sync webhook call per
    affected member whose ``discord_id`` is set.  All N calls share a
    single ``correlation_id`` (one per user action, contract §8).
    Each call receives a strictly-increasing ``assigned_at`` timestamp
    so the receiver can apply monotonic ordering (contract §7).

    Members with ``discord_id=None`` are silently skipped at the sender
    layer; no HTTP call is made for them.

    The HTTP response is returned before the background tasks fire
    (fire-and-forget per the brief).
    """
    result = await attack_day_service.apply_attack_day(db, siege_id)

    # One correlation_id for the entire user action (contract §8).
    correlation_id = str(uuid.uuid4())

    for entry in result.applied_members:
        # assigned_at is sourced from PostgreSQL clock_timestamp() per
        # member inside the service layer — each entry carries its own
        # timestamp captured at the moment of mutation (contract §7).
        action = "assign" if entry.attack_day is not None else "unassign"

        schedule_role_sync(
            background_tasks,
            discord_id=entry.discord_id,
            siege_id=siege_id,
            day_number=entry.attack_day,
            action=action,
            assigned_at=entry.assigned_at,
            correlation_id=correlation_id,
        )

    return result
