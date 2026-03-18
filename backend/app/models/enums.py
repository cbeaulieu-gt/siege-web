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


class PowerLevel(str, enum.Enum):
    lt_10m = "lt_10m"
    m_10_15 = "10_15m"
    m_16_20 = "16_20m"
    m_21_25 = "21_25m"
    gt_25m = "gt_25m"


class NotificationBatchStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
