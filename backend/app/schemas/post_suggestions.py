"""Pydantic schemas for the Suggest Post Assignments feature.

These schemas define the request and response shapes for the
/sieges/{siege_id}/post-suggestions endpoints.
"""

from typing import Literal

from pydantic import BaseModel


class PostSuggestionEntry(BaseModel):
    """A single post assignment suggestion produced by the greedy algorithm.

    Attributes:
        post_id: The Post row id.
        building_number: Building number (1-18) used for display ordering.
        priority: Raw integer priority; higher = first-pick in the algorithm.
        position_id: The target Position row id the algorithm intends to
            write.  The apply step uses this as the write target.
        suggested_member_id: Suggested member, or None when the post is
            skipped (see skip_reason).
        suggested_member_name: Display name of the suggested member, or
            None when skipped.
        suggested_condition_id: The PostCondition id that drove the match,
            or None when skipped.
        suggested_condition_description: Human-readable condition text, or
            None when skipped.
        current_member_id: The member currently assigned to the position,
            or None if empty.
        current_member_name: Display name of the current member, or None.
        current_condition_id: The matched_condition_id currently on the
            position, or None.
        current_condition_description: Human-readable text of the current
            matched condition, or None.
        matches_current: True when the suggestion exactly matches the
            existing assignment.  Always False when suggested_member_id is
            None.
        skip_reason: Set when suggested_member_id is None.  Indicates why
            the post was skipped:
            - "no_conditions": the post has zero active conditions so no
              member can ever match (user must configure the post first).
            - "no_match": conditions exist but no candidate member's
              preferences intersect the post's active conditions.
            - "reserve": target position has is_reserve=True.
            - "disabled": target position has is_disabled=True.
    """

    post_id: int
    building_number: int
    priority: int
    position_id: int
    suggested_member_id: int | None
    suggested_member_name: str | None
    suggested_condition_id: int | None
    suggested_condition_description: str | None
    current_member_id: int | None
    current_member_name: str | None
    current_condition_id: int | None
    current_condition_description: str | None
    matches_current: bool
    skip_reason: Literal["no_conditions", "no_match", "reserve", "disabled"] | None


class PostSuggestionPreviewResult(BaseModel):
    """The full preview result returned by POST /post-suggestions.

    Attributes:
        assignments: One entry per post on the siege (including skipped
            posts).  Ordered by priority desc, building_number asc.
        expires_at: ISO 8601 datetime string indicating when the stored
            preview expires (30 minutes from generation).
    """

    assignments: list[PostSuggestionEntry]
    expires_at: str


class PostSuggestionApplyRequest(BaseModel):
    """Request body for POST /post-suggestions/apply.

    Attributes:
        apply_position_ids: Caller-filtered subset of position_ids from
            the preview.  Only these positions will be written.
            Empty list is valid (no-op apply).
    """

    apply_position_ids: list[int]


class StaleEntry(BaseModel):
    """A single stale-state violation detected during apply revalidation.

    Attributes:
        position_id: The position that is in an unexpected state.
        reason: Why this position is considered stale:
            - "position_missing": the position row no longer exists.
            - "position_disabled": the position is now disabled (or its
              building is broken, which is functionally equivalent).
            - "position_reserve": the position is now in reserve mode.
            - "member_inactive": the suggested member is no longer active.
            - "member_changed": another planner assigned a different member
              to this position between preview and apply.
    """

    position_id: int
    reason: Literal[
        "position_missing",
        "position_disabled",
        "position_reserve",
        "member_inactive",
        "member_changed",
    ]


class PostSuggestionApplyResult(BaseModel):
    """Response body for a successful POST /post-suggestions/apply.

    Attributes:
        applied_count: The number of positions that were updated.
    """

    applied_count: int
