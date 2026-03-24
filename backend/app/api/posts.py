from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.post import Post
from app.schemas.post import PostConditionsUpdate, PostResponse, PostUpdate
from app.services import posts as posts_service

router = APIRouter(tags=["posts"])


def _serialize_post(post: Post) -> dict:
    """Build a PostResponse-compatible dict, denormalizing building_number from the relationship."""
    return {
        "id": post.id,
        "siege_id": post.siege_id,
        "building_id": post.building_id,
        "building_number": post.building.building_number,
        "priority": post.priority,
        "description": post.description,
        "active_conditions": [
            {"id": c.id, "description": c.description, "stronghold_level": c.stronghold_level}
            for c in post.active_conditions
        ],
    }


@router.get("/sieges/{siege_id}/posts", response_model=list[PostResponse])
async def list_posts(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
):
    posts = await posts_service.list_posts(db, siege_id)
    return [_serialize_post(p) for p in posts]


@router.put("/sieges/{siege_id}/posts/{post_id}", response_model=PostResponse)
async def update_post(
    siege_id: int,
    post_id: int,
    data: PostUpdate,
    db: AsyncSession = Depends(get_db),
):
    post = await posts_service.update_post(db, siege_id, post_id, data)
    return _serialize_post(post)


@router.put(
    "/sieges/{siege_id}/posts/{post_id}/conditions",
    response_model=PostResponse,
)
async def set_post_conditions(
    siege_id: int,
    post_id: int,
    data: PostConditionsUpdate,
    db: AsyncSession = Depends(get_db),
):
    post = await posts_service.set_post_conditions(db, siege_id, post_id, data.post_condition_ids)
    return _serialize_post(post)
