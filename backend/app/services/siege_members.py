from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SiegeStatus
from app.models.siege_member import SiegeMember
from app.schemas.siege_member import SiegeMemberUpdate
from app.services.sieges import get_siege


async def list_siege_members(session: AsyncSession, siege_id: int) -> list[SiegeMember]:
    result = await session.execute(
        select(SiegeMember).where(SiegeMember.siege_id == siege_id)
    )
    return list(result.scalars().all())


async def update_siege_member(
    session: AsyncSession, siege_id: int, member_id: int, data: SiegeMemberUpdate
) -> SiegeMember:
    siege = await get_siege(session, siege_id)
    if siege.status == SiegeStatus.complete:
        raise HTTPException(
            status_code=400, detail="Siege is complete — member data is fully locked"
        )

    result = await session.execute(
        select(SiegeMember).where(
            SiegeMember.siege_id == siege_id,
            SiegeMember.member_id == member_id,
        )
    )
    siege_member = result.scalar_one_or_none()
    if siege_member is None:
        raise HTTPException(status_code=404, detail="SiegeMember record not found")

    if data.attack_day is not None and data.attack_day not in (1, 2):
        raise HTTPException(status_code=400, detail="attack_day must be 1 or 2")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(siege_member, field, value)

    await session.commit()
    await session.refresh(siege_member)
    return siege_member
