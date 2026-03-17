"""Seed reference data into the database."""

import asyncio

from app.db.session import AsyncSessionLocal
from app.db.seeds import seed_post_conditions, seed_building_type_config


async def main():
    async with AsyncSessionLocal() as session:
        await seed_post_conditions(session)
        await seed_building_type_config(session)
        await session.commit()
        print("Seeded 36 post conditions + 5 building type configs.")


if __name__ == "__main__":
    asyncio.run(main())
