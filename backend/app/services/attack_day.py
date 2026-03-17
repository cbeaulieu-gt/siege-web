from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.member import Member
from app.models.siege import Siege
from app.models.siege_member import SiegeMember
from app.models.enums import MemberRole
from app.schemas.attack_day import AttackDayApplyResult, AttackDayAssignment, AttackDayPreviewResult

PREVIEW_TTL_MINUTES = 30
DAY2_TARGET = 10


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def preview_attack_day(session: AsyncSession, siege_id: int) -> AttackDayPreviewResult:
    siege_result = await session.execute(
        select(Siege)
        .where(Siege.id == siege_id)
        .options(selectinload(Siege.siege_members).selectinload(SiegeMember.member))
    )
    siege = siege_result.scalar_one_or_none()
    if siege is None:
        raise HTTPException(status_code=404, detail="Siege not found")

    assignments: dict[int, int] = {}  # member_id -> attack_day

    # Step 2: Lock overridden members
    overridden = [sm for sm in siege.siege_members if sm.attack_day_override]
    non_overridden = [sm for sm in siege.siege_members if not sm.attack_day_override]

    for sm in overridden:
        if sm.attack_day is not None:
            assignments[sm.member_id] = sm.attack_day

    # Step 3: Seed day2_count from overridden members already on Day 2
    day2_count = sum(1 for sm in overridden if sm.attack_day == 2)

    # Separate non-overridden by role (skip members with no Member row)
    heavy_hitters: list[SiegeMember] = []
    advanced: list[SiegeMember] = []
    medium: list[SiegeMember] = []
    novice: list[SiegeMember] = []

    for sm in non_overridden:
        if sm.member is None:
            continue
        role = sm.member.role
        if role == MemberRole.heavy_hitter:
            heavy_hitters.append(sm)
        elif role == MemberRole.advanced:
            advanced.append(sm)
        elif role == MemberRole.medium:
            medium.append(sm)
        elif role == MemberRole.novice:
            novice.append(sm)

    # Step 4: Assign heavy hitters + advanced to Day 2
    for sm in heavy_hitters + advanced:
        assignments[sm.member_id] = 2
        day2_count += 1

    # Step 5: If already at/over 10, everyone else goes to Day 1
    if day2_count >= DAY2_TARGET:
        for sm in medium + novice:
            assignments[sm.member_id] = 1
        return await _build_preview(session, siege, assignments)

    # Step 6-7: Sort medium by power desc, promote until 10
    medium_sorted = sorted(
        medium,
        key=lambda sm: float(sm.member.power) if sm.member and sm.member.power is not None else 0.0,
        reverse=True,
    )
    remaining_medium: list[SiegeMember] = []
    for sm in medium_sorted:
        if day2_count < DAY2_TARGET:
            assignments[sm.member_id] = 2
            day2_count += 1
        else:
            remaining_medium.append(sm)
            assignments[sm.member_id] = 1

    # Remaining medium → Day 1
    for sm in remaining_medium:
        assignments[sm.member_id] = 1

    if day2_count >= DAY2_TARGET:
        for sm in novice:
            assignments[sm.member_id] = 1
        return await _build_preview(session, siege, assignments)

    # Step 8-9: Sort novice by power desc, promote until 10
    novice_sorted = sorted(
        novice,
        key=lambda sm: float(sm.member.power) if sm.member and sm.member.power is not None else 0.0,
        reverse=True,
    )
    for sm in novice_sorted:
        if day2_count < DAY2_TARGET:
            assignments[sm.member_id] = 2
            day2_count += 1
        else:
            assignments[sm.member_id] = 1

    return await _build_preview(session, siege, assignments)


async def _build_preview(session: AsyncSession, siege: Siege, assignments: dict[int, int]) -> AttackDayPreviewResult:
    assignment_list = [
        AttackDayAssignment(member_id=mid, attack_day=day)
        for mid, day in assignments.items()
    ]
    expires_at = _now_utc().replace(tzinfo=None) + timedelta(minutes=PREVIEW_TTL_MINUTES)
    siege.attack_day_preview = {
        "assignments": [a.model_dump() for a in assignment_list]
    }
    siege.attack_day_preview_expires_at = expires_at
    await session.commit()
    return AttackDayPreviewResult(
        assignments=assignment_list,
        expires_at=expires_at.isoformat(),
    )


async def apply_attack_day(session: AsyncSession, siege_id: int) -> AttackDayApplyResult:
    siege_result = await session.execute(
        select(Siege)
        .where(Siege.id == siege_id)
        .options(selectinload(Siege.siege_members))
    )
    siege = siege_result.scalar_one_or_none()
    if siege is None:
        raise HTTPException(status_code=404, detail="Siege not found")

    if siege.attack_day_preview is None or siege.attack_day_preview_expires_at is None:
        raise HTTPException(status_code=409, detail="No valid preview to apply, generate a new one")

    expires_at = siege.attack_day_preview_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if _now_utc() > expires_at:
        raise HTTPException(status_code=409, detail="No valid preview to apply, generate a new one")

    raw_assignments: list[dict] = siege.attack_day_preview.get("assignments", [])
    sm_by_member = {sm.member_id: sm for sm in siege.siege_members}

    applied_count = 0
    for entry in raw_assignments:
        sm = sm_by_member.get(entry["member_id"])
        if sm is not None:
            sm.attack_day = entry["attack_day"]
            applied_count += 1

    siege.attack_day_preview = None
    siege.attack_day_preview_expires_at = None

    await session.commit()

    return AttackDayApplyResult(applied_count=applied_count)
