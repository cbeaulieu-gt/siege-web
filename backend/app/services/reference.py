from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.building_type_config import BuildingTypeConfig
from app.models.post_condition import PostCondition


async def get_post_conditions(
    session: AsyncSession, stronghold_level: int | None
) -> list[PostCondition]:
    stmt = select(PostCondition)
    if stronghold_level is not None:
        stmt = stmt.where(PostCondition.stronghold_level == stronghold_level)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_building_types(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(BuildingTypeConfig))
    configs = result.scalars().all()
    return [
        {
            "value": cfg.building_type.value,
            "display": cfg.building_type.value.replace("_", " ").title(),
            "count": cfg.count,
            "base_group_count": cfg.base_group_count,
            "base_last_group_slots": cfg.base_last_group_slots,
        }
        for cfg in configs
    ]


async def get_member_roles() -> list[dict]:
    return [
        {"value": "heavy_hitter", "display": "Heavy Hitter", "default_attack_day": 2},
        {"value": "advanced", "display": "Advanced", "default_attack_day": 2},
        {"value": "medium", "display": "Medium", "default_attack_day": 1},
        {"value": "novice", "display": "Novice", "default_attack_day": 1},
    ]
