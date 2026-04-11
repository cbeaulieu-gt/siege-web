#!/usr/bin/env python
"""Run all seed scripts against the configured database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db.seeds import seed_building_type_config, seed_post_conditions, seed_post_priority_config


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        await seed_post_conditions(session)
        await seed_building_type_config(session)
        await seed_post_priority_config(session)
        await session.commit()
    await engine.dispose()
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(main())
