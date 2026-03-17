import enum


class SiegeStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    complete = "complete"


class BuildingType(str, enum.Enum):
    stronghold = "stronghold"
    mana_shrine = "mana_shrine"
    magic_tower = "magic_tower"
    defense_tower = "defense_tower"
    post = "post"


class MemberRole(str, enum.Enum):
    heavy_hitter = "heavy_hitter"
    advanced = "advanced"
    medium = "medium"
    novice = "novice"


class NotificationBatchStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
