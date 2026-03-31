from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.building import Building
from app.models.building_group import BuildingGroup
from app.models.enums import SiegeStatus
from app.models.member import Member
from app.models.position import Position
from app.models.siege import Siege
from app.schemas.comparison import ComparisonResult, MemberDiff, PositionKey


async def _load_assignments(session: AsyncSession, siege_id: int) -> dict[int, list[PositionKey]]:
    """Return {member_id: [PositionKey, ...]} for non-reserve, non-disabled assigned positions.

    Only positions belonging to active members are included.  Assignments copied from a cloned
    siege may reference members who are (or have since become) inactive; those are excluded here
    so they never surface in the comparison view.
    """
    result = await session.execute(
        select(Position, BuildingGroup, Building)
        .join(BuildingGroup, Position.building_group_id == BuildingGroup.id)
        .join(Building, BuildingGroup.building_id == Building.id)
        .join(Member, Position.member_id == Member.id)
        .where(Building.siege_id == siege_id)
        .where(Position.member_id.is_not(None))
        .where(Position.is_reserve.is_(False))
        .where(Position.is_disabled.is_(False))
        .where(Member.is_active.is_(True))
    )

    assignments: dict[int, list[PositionKey]] = {}
    for pos, group, building in result.all():
        key = PositionKey(
            building_type=building.building_type,
            building_number=building.building_number,
            group_number=group.group_number,
            position_number=pos.position_number,
        )
        assignments.setdefault(pos.member_id, []).append(key)

    return assignments


async def _load_member_names(session: AsyncSession, member_ids: set[int]) -> dict[int, str]:
    if not member_ids:
        return {}
    result = await session.execute(select(Member).where(Member.id.in_(member_ids)))
    return {m.id: m.name for m in result.scalars().all()}


async def get_most_recent_completed(session: AsyncSession, exclude_siege_id: int) -> Siege | None:
    result = await session.execute(
        select(Siege)
        .where(Siege.status == SiegeStatus.complete)
        .where(Siege.id != exclude_siege_id)
        .order_by(Siege.date.desc(), Siege.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def compare_sieges(
    session: AsyncSession, siege_a_id: int, siege_b_id: int
) -> ComparisonResult:
    a_assignments = await _load_assignments(session, siege_a_id)
    b_assignments = await _load_assignments(session, siege_b_id)

    all_member_ids = set(a_assignments.keys()) | set(b_assignments.keys())
    member_names = await _load_member_names(session, all_member_ids)

    member_diffs: list[MemberDiff] = []
    for member_id in sorted(all_member_ids):
        a_keys = {
            (k.building_type, k.building_number, k.group_number, k.position_number): k
            for k in a_assignments.get(member_id, [])
        }
        b_keys = {
            (k.building_type, k.building_number, k.group_number, k.position_number): k
            for k in b_assignments.get(member_id, [])
        }

        a_set = set(a_keys.keys())
        b_set = set(b_keys.keys())

        added = [b_keys[k] for k in sorted(b_set - a_set)]
        removed = [a_keys[k] for k in sorted(a_set - b_set)]
        unchanged = [a_keys[k] for k in sorted(a_set & b_set)]

        member_diffs.append(
            MemberDiff(
                member_id=member_id,
                member_name=member_names.get(member_id, f"Member {member_id}"),
                added=added,
                removed=removed,
                unchanged=unchanged,
            )
        )

    return ComparisonResult(
        siege_a_id=siege_a_id,
        siege_b_id=siege_b_id,
        members=member_diffs,
    )
