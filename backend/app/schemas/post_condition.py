from typing import Literal

from pydantic import BaseModel


class PostConditionResponse(BaseModel):
    """Pydantic response schema for a PostCondition catalog entry."""

    model_config = {"from_attributes": True}
    id: int
    description: str
    stronghold_level: int
    condition_type: Literal["role", "affinity", "faction", "league", "rarity", "effect", "other"]
