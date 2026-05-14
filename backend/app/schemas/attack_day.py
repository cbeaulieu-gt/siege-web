"""Pydantic schemas and internal dataclasses for the attack-day endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field


class AttackDayAssignment(BaseModel):
    """A single member's attack-day assignment from the auto-assign preview."""

    member_id: int
    attack_day: int


class AttackDayPreviewResult(BaseModel):
    """Response body for the attack-day preview endpoint."""

    assignments: list[AttackDayAssignment]
    expires_at: str


@dataclass
class AppliedMemberEntry:
    """Per-member data needed for day-role-sync webhook fan-out.

    This dataclass is internal — it is never serialized to JSON.  The API
    layer reads it from ``AttackDayApplyResult.applied_members`` to schedule
    outbound webhook calls after returning the HTTP response.

    Attributes:
        member_id: Primary key of the member record.
        attack_day: The day number (1 or 2) applied.
        discord_id: Discord snowflake string, or ``None`` if the member
            has no linked Discord account (webhook will be skipped).
        assigned_at: UTC-aware datetime sourced from PostgreSQL
            ``clock_timestamp()`` at the moment of mutation.  Used by
            the API layer as the ``assigned_at`` field in the outbound
            day-role-sync webhook payload.
    """

    member_id: int
    attack_day: int
    discord_id: str | None
    assigned_at: datetime


class AttackDayApplyResult(BaseModel):
    """Response body for the attack-day apply endpoint.

    ``applied_members`` is an internal field populated by the service layer
    so the API layer can schedule outbound webhook calls.  It is excluded
    from the HTTP JSON response via ``response_model_exclude`` on the route
    (see ``api/attack_day.py``).

    Attributes:
        applied_count: Number of siege members whose attack_day was updated.
        applied_members: Per-member data for webhook fan-out; not exposed in
            the API response.
    """

    model_config = {"arbitrary_types_allowed": True}

    applied_count: int
    applied_members: list[AppliedMemberEntry] = Field(
        default_factory=list,
        exclude=True,
    )
