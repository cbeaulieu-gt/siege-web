import enum


class SiegeStatus(enum.StrEnum):
    planning = "planning"
    active = "active"
    complete = "complete"


class BuildingType(enum.StrEnum):
    stronghold = "stronghold"
    mana_shrine = "mana_shrine"
    magic_tower = "magic_tower"
    defense_tower = "defense_tower"
    post = "post"


class MemberRole(enum.StrEnum):
    heavy_hitter = "heavy_hitter"
    advanced = "advanced"
    medium = "medium"
    novice = "novice"


class PowerLevel(enum.StrEnum):
    lt_10m = "lt_10m"
    m_10_15 = "10_15m"
    m_16_20 = "16_20m"
    m_21_25 = "21_25m"
    gt_25m = "gt_25m"


class NotificationBatchStatus(enum.StrEnum):
    pending = "pending"
    completed = "completed"
