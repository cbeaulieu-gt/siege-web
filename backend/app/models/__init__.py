# Import all models here so Alembic can detect them during autogenerate.
from app.models.enums import (  # noqa: F401
    BuildingType,
    MemberRole,
    NotificationBatchStatus,
    SiegeStatus,
)
from app.models.member import Member  # noqa: F401
from app.models.siege import Siege  # noqa: F401
from app.models.building_type_config import BuildingTypeConfig  # noqa: F401
from app.models.post_condition import PostCondition  # noqa: F401
from app.models.building import Building  # noqa: F401
from app.models.building_group import BuildingGroup  # noqa: F401
from app.models.position import Position  # noqa: F401
from app.models.post_active_condition import post_active_condition  # noqa: F401
from app.models.member_post_preference import member_post_preference  # noqa: F401
from app.models.post import Post  # noqa: F401
from app.models.siege_member import SiegeMember  # noqa: F401
from app.models.notification_batch import NotificationBatch  # noqa: F401
from app.models.notification_batch_result import NotificationBatchResult  # noqa: F401
