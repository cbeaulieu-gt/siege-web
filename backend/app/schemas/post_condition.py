from pydantic import BaseModel


class PostConditionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    description: str
    stronghold_level: int
