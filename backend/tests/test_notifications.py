"""Endpoint tests for notification and post-to-channel routes."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.enums import MemberRole, NotificationBatchStatus, SiegeStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_siege(
    id: int = 1,
    status: SiegeStatus = SiegeStatus.planning,
    date: datetime.date = datetime.date(2026, 3, 20),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        date=date,
        status=status,
        defense_scroll_count=5,
        created_at=datetime.datetime(2026, 1, 1),
        updated_at=datetime.datetime(2026, 1, 1),
    )


def _make_member(
    id: int = 1,
    name: str = "Alice",
    discord_username: str | None = "alice#0001",
    discord_id: str | None = None,
    role: MemberRole = MemberRole.advanced,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        name=name,
        discord_username=discord_username,
        discord_id=discord_id,
        role=role,
        power=None,
        is_active=True,
    )


def _make_siege_member(
    siege_id: int = 1,
    member_id: int = 1,
    member: SimpleNamespace | None = None,
    attack_day: int | None = 1,
    has_reserve_set: bool | None = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        siege_id=siege_id,
        member_id=member_id,
        member=member or _make_member(id=member_id),
        attack_day=attack_day,
        has_reserve_set=has_reserve_set,
        attack_day_override=False,
    )


def _make_batch(
    id: int = 10,
    siege_id: int = 1,
    status: NotificationBatchStatus = NotificationBatchStatus.pending,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        siege_id=siege_id,
        status=status,
        created_at=datetime.datetime(2026, 1, 1),
    )


def _make_batch_result(
    id: int = 1,
    batch_id: int = 10,
    member_id: int = 1,
    discord_username: str | None = "alice#0001",
    success: bool | None = None,
    error: str | None = None,
    sent_at: datetime.datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        batch_id=batch_id,
        member_id=member_id,
        discord_username=discord_username,
        success=success,
        error=error,
        sent_at=sent_at,
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Mock DB session helper
# ---------------------------------------------------------------------------


def _make_db_session(siege=None, siege_members=None, batch=None, batch_results=None, members=None):
    """Build a mock DB session that returns the given objects."""
    session = MagicMock()

    async def mock_execute(stmt):
        result = MagicMock()
        # Determine what to return based on call order by checking the stmt
        stmt_str = str(stmt)
        if batch_results is not None and "notification_batch_result" in stmt_str.lower():
            result.scalars.return_value.all.return_value = batch_results or []
            result.scalar_one_or_none.return_value = batch
        elif batch is not None and "notification_batch" in stmt_str.lower():
            result.scalar_one_or_none.return_value = batch
            result.scalars.return_value.all.return_value = batch_results or []
        elif siege_members is not None and "siege_member" in stmt_str.lower():
            result.scalars.return_value.all.return_value = siege_members
        elif members is not None and "member" in stmt_str.lower():
            result.scalars.return_value.all.return_value = members
        elif siege is not None:
            result.scalar_one_or_none.return_value = siege
        else:
            result.scalar_one_or_none.return_value = None
            result.scalars.return_value.all.return_value = []
        return result

    session.execute = mock_execute
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# 1. POST /api/sieges/{id}/notify — 200 returns batch_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_returns_batch_id(client):
    siege = _make_siege()
    sm = _make_siege_member()
    batch = _make_batch(id=10)

    # We need a more controlled mock: patch get_siege and the DB execute calls
    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Simulate flush setting batch.id
    async def fake_flush():
        batch.id = 10

    mock_session.flush.side_effect = fake_flush

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[app.dependency_overrides.__class__] = {}

    from app.db.session import get_db

    app.dependency_overrides[get_db] = fake_get_db

    from app.schemas.validation import ValidationResult

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                return_value=[{"username": "alice#0001"}],
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    instance = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    instance.status = NotificationBatchStatus.pending
                    instance.id = 10
                    MockBatch.return_value = instance
                    with patch("app.api.notifications.NotificationBatchResult"):
                        with patch("app.api.notifications._send_dms"):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "batch_id" in data
    assert data["status"] == "pending"
    assert data["member_count"] == 1
    assert data["skipped_count"] == 0


# ---------------------------------------------------------------------------
# 2. POST /api/sieges/{id}/notify — 404 when siege not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_siege_not_found(client):
    from app.db.session import get_db

    async def fake_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = fake_get_db

    with patch(
        "app.api.notifications.get_siege",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=404, detail="Siege not found"),
    ):
        async with client as c:
            response = await c.post("/api/sieges/9999/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 3. POST /api/sieges/{id}/notify — 400 when siege is complete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_siege_complete_returns_400(client):
    siege = _make_siege(status=SiegeStatus.complete)

    from app.db.session import get_db

    async def fake_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = fake_get_db

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        async with client as c:
            response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 400
    assert "complete" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. GET /api/sieges/{id}/notify/{batch_id} — 200 returns batch with results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_notification_batch_returns_results(client):
    batch = _make_batch(id=10, siege_id=1, status=NotificationBatchStatus.completed)
    result_row = _make_batch_result(member_id=1, success=True)
    member = _make_member(id=1, name="Alice")

    call_count = 0

    mock_session = MagicMock()

    async def tracked_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # First call: get batch
            result.scalar_one_or_none.return_value = batch
        elif call_count == 2:
            # Second call: get results
            result.scalars.return_value.all.return_value = [result_row]
        else:
            # Third call: get members
            result.scalars.return_value.all.return_value = [member]
        return result

    mock_session.execute = tracked_execute

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    async with client as c:
        response = await c.get("/api/sieges/1/notify/10")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"] == 10
    assert data["status"] == "completed"
    assert len(data["results"]) == 1
    assert data["results"][0]["member_name"] == "Alice"
    assert data["results"][0]["success"] is True


# ---------------------------------------------------------------------------
# 5. GET /api/sieges/{id}/notify/{batch_id} — 404 when batch not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_notification_batch_not_found(client):
    mock_session = MagicMock()

    async def mock_execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result

    mock_session.execute = mock_execute

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    async with client as c:
        response = await c.get("/api/sieges/1/notify/9999")

    app.dependency_overrides.clear()
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 6. POST /api/sieges/{id}/post-to-channel — 200 (mock image gen and bot client)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_to_channel_success(client):
    siege = _make_siege()
    sm = _make_siege_member()

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm]
    mock_session.execute = AsyncMock(return_value=sm_result)

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    board_dict = {
        "siege_id": 1,
        "buildings": [],
    }

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.board_service.get_board",
            new_callable=AsyncMock,
            return_value=board_dict,
        ):
            with patch(
                "app.api.notifications.image_gen.generate_assignments_image",
                new_callable=AsyncMock,
                return_value=b"fake-assignments-png",
            ):
                with patch(
                    "app.api.notifications.image_gen.generate_reserves_image",
                    new_callable=AsyncMock,
                    return_value=b"fake-reserves-png",
                ):
                    with patch(
                        "app.api.notifications.bot_client.post_image",
                        new_callable=AsyncMock,
                        return_value="https://cdn.discordapp.com/attachments/123/img.png",
                    ):
                        with patch(
                            "app.api.notifications.bot_client.post_message",
                            new_callable=AsyncMock,
                            return_value=True,
                        ):
                            async with client as c:
                                response = await c.post("/api/sieges/1/post-to-channel")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "posted"


# ---------------------------------------------------------------------------
# 7. POST /api/sieges/{id}/post-to-channel — two-channel split with CDN URLs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_to_channel_posts_images_to_images_channel_and_summary_to_text_channel(client):
    """Images post to discord_siege_images_channel.

    Summary with CDN links posts to discord_siege_channel.
    """
    siege = _make_siege()
    sm = _make_siege_member()

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm]
    mock_session.execute = AsyncMock(return_value=sm_result)

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    board_dict = {"siege_id": 1, "buildings": []}
    assignments_url = "https://cdn.discordapp.com/attachments/111/assignments.png"
    reserves_url = "https://cdn.discordapp.com/attachments/222/reserves.png"

    mock_post_image = AsyncMock(side_effect=[assignments_url, reserves_url])
    mock_post_message = AsyncMock(return_value=True)

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.board_service.get_board",
            new_callable=AsyncMock,
            return_value=board_dict,
        ):
            with patch(
                "app.api.notifications.image_gen.generate_assignments_image",
                new_callable=AsyncMock,
                return_value=b"fake-assignments-png",
            ):
                with patch(
                    "app.api.notifications.image_gen.generate_reserves_image",
                    new_callable=AsyncMock,
                    return_value=b"fake-reserves-png",
                ):
                    with patch("app.api.notifications.bot_client.post_image", mock_post_image):
                        with patch(
                            "app.api.notifications.bot_client.post_message", mock_post_message
                        ):
                            with patch("app.api.notifications.settings") as mock_settings:
                                mock_settings.discord_siege_channel = "clan-siege-assignments"
                                mock_settings.discord_siege_images_channel = (
                                    "clan-siege-assignment-images"
                                )
                                async with client as c:
                                    response = await c.post("/api/sieges/1/post-to-channel")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "posted"

    # Both image posts go to the images channel
    assert mock_post_image.call_count == 2
    image_channels = [call.args[0] for call in mock_post_image.call_args_list]
    assert image_channels[0] == "clan-siege-assignment-images"
    assert image_channels[1] == "clan-siege-assignment-images"

    # Summary goes to the text channel
    assert mock_post_message.call_count == 1
    message_channel = mock_post_message.call_args.args[0]
    assert message_channel == "clan-siege-assignments"

    # Summary message contains both CDN URLs
    message_text = mock_post_message.call_args.args[1]
    assert assignments_url in message_text
    assert reserves_url in message_text


# ---------------------------------------------------------------------------
# 8. POST /api/sieges/{id}/post-to-channel — image failure returns {"status": "failed"}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_to_channel_image_failure_returns_failed(client):
    """When post_image returns None (failure), the endpoint returns status='failed'."""
    siege = _make_siege()
    sm = _make_siege_member()

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm]
    mock_session.execute = AsyncMock(return_value=sm_result)

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    board_dict = {"siege_id": 1, "buildings": []}

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.board_service.get_board",
            new_callable=AsyncMock,
            return_value=board_dict,
        ):
            with patch(
                "app.api.notifications.image_gen.generate_assignments_image",
                new_callable=AsyncMock,
                return_value=b"fake-assignments-png",
            ):
                with patch(
                    "app.api.notifications.image_gen.generate_reserves_image",
                    new_callable=AsyncMock,
                    return_value=b"fake-reserves-png",
                ):
                    with patch(
                        "app.api.notifications.bot_client.post_image",
                        new_callable=AsyncMock,
                        return_value=None,
                    ):
                        with patch(
                            "app.api.notifications.bot_client.post_message",
                            new_callable=AsyncMock,
                            return_value=True,
                        ):
                            async with client as c:
                                response = await c.post("/api/sieges/1/post-to-channel")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


# ---------------------------------------------------------------------------
# 9. notify — member with no discord_username is skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_skips_member_with_no_discord_username(client):
    """Members without a discord_username must not get a batch result row."""
    siege = _make_siege()
    sm_no_username = _make_siege_member(
        member_id=1, member=_make_member(id=1, discord_username=None)
    )

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm_no_username]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def fake_flush():
        pass

    mock_session.flush.side_effect = fake_flush

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    from app.schemas.validation import ValidationResult

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                return_value=[{"username": "someoneelse"}],
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    MockBatch.return_value = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    with patch("app.api.notifications.NotificationBatchResult") as MockResult:
                        with patch("app.api.notifications._send_dms"):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    # No eligible members — no result rows created
    assert MockResult.call_count == 0
    assert data["member_count"] == 0
    assert data["skipped_count"] == 1


# ---------------------------------------------------------------------------
# 10. notify — member not in guild is skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_skips_member_not_in_guild(client):
    """Members whose discord_username is absent from the guild list must be skipped."""
    siege = _make_siege()
    sm_not_in_guild = _make_siege_member(
        member_id=2, member=_make_member(id=2, discord_username="bob#1234")
    )

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm_not_in_guild]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    from app.schemas.validation import ValidationResult

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                # Guild has alice but NOT bob
                return_value=[{"username": "alice#0001"}],
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    MockBatch.return_value = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    with patch("app.api.notifications.NotificationBatchResult") as MockResult:
                        with patch("app.api.notifications._send_dms"):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert MockResult.call_count == 0
    assert data["member_count"] == 0
    assert data["skipped_count"] == 1


# ---------------------------------------------------------------------------
# 11. notify — eligible member gets a batch result row and a DM queued
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_eligible_member_gets_result_row_and_dm(client):
    """A member who has a discord_username AND is in the guild must get a result row."""
    siege = _make_siege()
    sm_eligible = _make_siege_member(
        member_id=1, member=_make_member(id=1, discord_username="alice#0001")
    )

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm_eligible]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    captured_members_data: list[dict] = []

    async def fake_send_dms(batch_id, members_data):
        captured_members_data.extend(members_data)

    from app.schemas.validation import ValidationResult

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                return_value=[{"username": "alice#0001"}],
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    MockBatch.return_value = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    with patch("app.api.notifications.NotificationBatchResult") as MockResult:
                        with patch("app.api.notifications._send_dms", side_effect=fake_send_dms):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    # One eligible member → one result row constructed, one DM queued
    assert MockResult.call_count == 1
    assert len(captured_members_data) == 1
    assert captured_members_data[0]["discord_username"] == "alice#0001"
    assert data["member_count"] == 1
    assert data["skipped_count"] == 0


# ---------------------------------------------------------------------------
# 12. notify — skipped_count reflects total skipped across mixed members
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_skipped_count_reflects_all_skipped_members(client):
    """skipped_count must equal the number of members excluded for any reason."""
    siege = _make_siege()
    sm_eligible = _make_siege_member(
        member_id=1, member=_make_member(id=1, discord_username="alice#0001")
    )
    sm_no_username = _make_siege_member(
        member_id=2, member=_make_member(id=2, discord_username=None)
    )
    sm_not_in_guild = _make_siege_member(
        member_id=3, member=_make_member(id=3, discord_username="charlie#9999")
    )

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm_eligible, sm_no_username, sm_not_in_guild]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    from app.schemas.validation import ValidationResult

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                # Only alice is in the guild
                return_value=[{"username": "alice#0001"}],
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    MockBatch.return_value = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    with patch("app.api.notifications.NotificationBatchResult"):
                        with patch("app.api.notifications._send_dms"):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert data["member_count"] == 1  # only alice
    assert data["skipped_count"] == 2  # no-username + not-in-guild


# ---------------------------------------------------------------------------
# 13. notify — 400 when siege has validation errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_blocked_when_siege_has_validation_errors(client):
    """POST /notify must return 400 when validate_siege returns errors."""
    from app.schemas.validation import ValidationIssue, ValidationResult

    siege = _make_siege()

    from app.db.session import get_db

    async def fake_get_db():
        yield MagicMock()

    app.dependency_overrides[get_db] = fake_get_db

    validation_with_errors = ValidationResult(
        errors=[
            ValidationIssue(
                rule=13,
                message="Member 'Alice' has no attack day assigned",
                context={"member_id": 1},
            )
        ],
        warnings=[],
    )

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=validation_with_errors,
        ):
            async with client as c:
                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "validation error" in detail.lower()
    assert "1" in detail


# ---------------------------------------------------------------------------
# 14. notify — passes validation guard when siege has no errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_passes_validation_guard_when_no_errors(client):
    """POST /notify must not be blocked when validate_siege returns no errors."""
    from app.schemas.validation import ValidationResult

    siege = _make_siege()
    sm = _make_siege_member()

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def fake_get_db():
        yield mock_session

    from app.db.session import get_db

    app.dependency_overrides[get_db] = fake_get_db

    clean_validation = ValidationResult(errors=[], warnings=[])

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=clean_validation,
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                return_value=[{"username": "alice#0001"}],
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    MockBatch.return_value = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    with patch("app.api.notifications.NotificationBatchResult"):
                        with patch("app.api.notifications._send_dms"):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "batch_id" in data


# ---------------------------------------------------------------------------
# 15. notify — bot unreachable (get_members returns []) falls back to
#     discord_username filter only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_bot_unreachable_falls_back_to_username_filter(client):
    """When get_members() returns [] the endpoint must not block all DMs.

    Members with a discord_username are treated as eligible; those without
    are still skipped.
    """
    siege = _make_siege()
    sm_has_username = _make_siege_member(
        member_id=1, member=_make_member(id=1, discord_username="alice#0001")
    )
    sm_no_username = _make_siege_member(
        member_id=2, member=_make_member(id=2, discord_username=None)
    )

    mock_session = MagicMock()
    sm_result = MagicMock()
    sm_result.scalars.return_value.all.return_value = [sm_has_username, sm_no_username]
    mock_session.execute = AsyncMock(return_value=sm_result)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    from app.db.session import get_db

    async def fake_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = fake_get_db

    from app.schemas.validation import ValidationResult

    with patch("app.api.notifications.get_siege", new_callable=AsyncMock, return_value=siege):
        with patch(
            "app.api.notifications.validate_siege",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ):
            with patch(
                "app.api.notifications.bot_client.get_members",
                new_callable=AsyncMock,
                return_value=[],  # bot unreachable
            ):
                with patch("app.api.notifications.NotificationBatch") as MockBatch:
                    MockBatch.return_value = SimpleNamespace(
                        id=10, siege_id=1, status=NotificationBatchStatus.pending
                    )
                    with patch("app.api.notifications.NotificationBatchResult") as MockResult:
                        with patch("app.api.notifications._send_dms"):
                            async with client as c:
                                response = await c.post("/api/sieges/1/notify")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    # alice has a username → eligible even with bot unreachable
    assert MockResult.call_count == 1
    assert data["member_count"] == 1
    # member with no username is still skipped
    assert data["skipped_count"] == 1


# ---------------------------------------------------------------------------
# 16. _send_dms — batch status is set to completed even when bot raises mid-loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_dms_sets_completed_status_even_when_bot_raises():
    """_send_dms must guarantee batch.status = completed in its finally block.

    Scenario: two members; bot raises on the first notify call. The batch
    must still be committed as completed so the frontend polling terminates.
    """
    from app.api.notifications import _send_dms

    batch = _make_batch(id=42, siege_id=1, status=NotificationBatchStatus.pending)
    result_row = _make_batch_result(batch_id=42, member_id=1)

    # Build a session that tracks mutations on the batch object.
    call_count = 0
    mock_session = MagicMock()

    async def tracked_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        stmt_str = str(stmt)
        if "notification_batch_result" in stmt_str.lower():
            result.scalar_one_or_none.return_value = result_row
        else:
            # notification_batch lookup (both in try and in except finally)
            result.scalar_one_or_none.return_value = batch
        return result

    mock_session.execute = tracked_execute
    mock_session.commit = AsyncMock()

    # AsyncSessionLocal is used as an async context manager; patch it so it
    # yields our controlled session instead of opening a real DB connection.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session_local():
        yield mock_session

    members_data = [
        {"member_id": 1, "discord_username": "alice#0001", "message": "test"},
    ]

    with patch("app.api.notifications.AsyncSessionLocal", fake_session_local):
        with patch(
            "app.api.notifications.bot_client.notify",
            new_callable=AsyncMock,
            side_effect=RuntimeError("bot exploded"),
        ):
            with pytest.raises(RuntimeError, match="bot exploded"):
                await _send_dms(42, members_data)

    # The except block must have committed the session with completed status.
    assert mock_session.commit.called
    assert batch.status == NotificationBatchStatus.completed
