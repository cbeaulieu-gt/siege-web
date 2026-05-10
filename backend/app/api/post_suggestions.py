"""API router for the Suggest Post Assignments feature.

Routes:
    POST /sieges/{siege_id}/post-suggestions
        Generate (and store) a greedy assignment preview.

    POST /sieges/{siege_id}/post-suggestions/apply
        Apply a caller-filtered subset of the stored preview atomically.

The /post-suggestions kebab-case sibling segment avoids the route-shadow
risk that /posts/suggest would have if a future /posts/{post_id} endpoint
were added.  See plan § "API endpoint" for the full rationale.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.post_suggestions import (
    PostSuggestionApplyRequest,
    PostSuggestionApplyResult,
    PostSuggestionPreviewResult,
)
from app.services import post_suggestions as post_suggestions_service

router = APIRouter(tags=["post_suggestions"])


@router.post(
    "/sieges/{siege_id}/post-suggestions",
    response_model=PostSuggestionPreviewResult,
)
async def preview_post_suggestions(
    siege_id: int,
    db: AsyncSession = Depends(get_db),
) -> PostSuggestionPreviewResult:
    """Generate a greedy post-assignment suggestion preview.

    Args:
        siege_id: Primary key of the target Siege.
        db: Injected async database session.

    Returns:
        PostSuggestionPreviewResult with one entry per post and an expiry.

    Raises:
        HTTPException(404): Siege not found.
        HTTPException(400): Siege is complete.
    """
    return await post_suggestions_service.preview_post_suggestions(db, siege_id)


@router.post(
    "/sieges/{siege_id}/post-suggestions/apply",
    response_model=PostSuggestionApplyResult,
)
async def apply_post_suggestions(
    siege_id: int,
    data: PostSuggestionApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> PostSuggestionApplyResult:
    """Apply a caller-filtered subset of the stored preview atomically.

    Uses SELECT ... FOR UPDATE to fence the TOCTOU window between
    revalidation and the inline writes.  Any stale state detected during
    revalidation is returned as a 409 with structured stale_entries detail.

    Args:
        siege_id: Primary key of the target Siege.
        data: Request body containing the position ids to apply.
        db: Injected async database session.

    Returns:
        PostSuggestionApplyResult with the count of positions updated.

    Raises:
        HTTPException(404): Siege not found.
        HTTPException(400): Siege is complete.
        HTTPException(409): Preview missing/expired or stale state detected.
    """
    return await post_suggestions_service.apply_post_suggestions(db, siege_id, data)
