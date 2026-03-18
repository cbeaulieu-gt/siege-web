from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.post_priority_config import PostPriorityConfig

router = APIRouter(tags=["config"])


class PostPriorityResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    post_number: int
    priority: int


class PostPriorityUpdate(BaseModel):
    priority: int


@router.get("/post-priorities", response_model=list[PostPriorityResponse])
async def list_post_priorities(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PostPriorityConfig).order_by(PostPriorityConfig.post_number)
    )
    return list(result.scalars().all())


@router.put("/post-priorities/{post_number}", response_model=PostPriorityResponse)
async def update_post_priority(
    post_number: int,
    data: PostPriorityUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PostPriorityConfig).where(PostPriorityConfig.post_number == post_number)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Post number not found")
    config.priority = data.priority
    await db.commit()
    await db.refresh(config)
    return config
