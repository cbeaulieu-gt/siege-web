"""Endpoint tests for Discord sync — /api/members/discord-sync/*

All tests mock the service layer (discord_sync_service) and/or bot_client.get_members
so that no real DB or bot connection is required.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.member import SyncApplyResponse, SyncMatch, SyncPreviewResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sync_match(
    member_id: int = 1,
    member_name: str = "Alice",
    current_discord_username: str | None = None,
    proposed_discord_username: str = "alice_discord",
    proposed_discord_id: str = "111",
    confidence: str = "exact",
) -> SyncMatch:
    return SyncMatch(
        member_id=member_id,
        member_name=member_name,
        current_discord_username=current_discord_username,
        proposed_discord_username=proposed_discord_username,
        proposed_discord_id=proposed_discord_id,
        confidence=confidence,
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Preview endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preview_returns_exact_match(client):
    """Exact confidence match (discord_id already set) is returned correctly."""
    preview = SyncPreviewResponse(
        matches=[_make_sync_match(confidence="exact")],
        unmatched_guild_members=[],
        unmatched_clan_members=[],
    )
    with patch(
        "app.api.discord_sync.discord_sync_service.preview_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/members/discord-sync/preview")

    assert response.status_code == 200
    data = response.json()
    assert len(data["matches"]) == 1
    assert data["matches"][0]["confidence"] == "exact"
    assert data["matches"][0]["member_name"] == "Alice"
    assert data["unmatched_guild_members"] == []
    assert data["unmatched_clan_members"] == []


@pytest.mark.asyncio
async def test_preview_returns_suggested_match(client):
    """Suggested confidence (name heuristic) is returned correctly."""
    preview = SyncPreviewResponse(
        matches=[_make_sync_match(confidence="suggested")],
        unmatched_guild_members=[],
        unmatched_clan_members=[],
    )
    with patch(
        "app.api.discord_sync.discord_sync_service.preview_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/members/discord-sync/preview")

    assert response.status_code == 200
    assert response.json()["matches"][0]["confidence"] == "suggested"


@pytest.mark.asyncio
async def test_preview_returns_ambiguous_match(client):
    """Ambiguous confidence (multiple guild members could match) is returned."""
    preview = SyncPreviewResponse(
        matches=[_make_sync_match(confidence="ambiguous")],
        unmatched_guild_members=[],
        unmatched_clan_members=[],
    )
    with patch(
        "app.api.discord_sync.discord_sync_service.preview_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/members/discord-sync/preview")

    assert response.status_code == 200
    assert response.json()["matches"][0]["confidence"] == "ambiguous"


@pytest.mark.asyncio
async def test_preview_reports_unmatched_guild_members(client):
    """Guild members with no clan counterpart appear in unmatched_guild_members."""
    preview = SyncPreviewResponse(
        matches=[],
        unmatched_guild_members=["ghost_user", "another_user"],
        unmatched_clan_members=[],
    )
    with patch(
        "app.api.discord_sync.discord_sync_service.preview_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/members/discord-sync/preview")

    data = response.json()
    assert data["unmatched_guild_members"] == ["ghost_user", "another_user"]


@pytest.mark.asyncio
async def test_preview_reports_unmatched_clan_members(client):
    """Clan members with no guild counterpart appear in unmatched_clan_members."""
    preview = SyncPreviewResponse(
        matches=[],
        unmatched_guild_members=[],
        unmatched_clan_members=["Bob", "Carol"],
    )
    with patch(
        "app.api.discord_sync.discord_sync_service.preview_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = preview
        async with client as c:
            response = await c.post("/api/members/discord-sync/preview")

    data = response.json()
    assert data["unmatched_clan_members"] == ["Bob", "Carol"]


# ---------------------------------------------------------------------------
# Apply endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_updates_matched_members(client):
    """Apply returns the count of updated members."""
    with patch(
        "app.api.discord_sync.discord_sync_service.apply_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = SyncApplyResponse(updated=2)
        async with client as c:
            response = await c.post(
                "/api/members/discord-sync/apply",
                json=[
                    {"member_id": 1, "discord_username": "alice_discord", "discord_id": "111"},
                    {"member_id": 2, "discord_username": "bob_discord", "discord_id": "222"},
                ],
            )

    assert response.status_code == 200
    assert response.json() == {"updated": 2}


@pytest.mark.asyncio
async def test_apply_with_empty_list_returns_zero(client):
    """Applying an empty list returns updated=0 without crashing."""
    with patch(
        "app.api.discord_sync.discord_sync_service.apply_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = SyncApplyResponse(updated=0)
        async with client as c:
            response = await c.post("/api/members/discord-sync/apply", json=[])

    assert response.status_code == 200
    assert response.json() == {"updated": 0}


@pytest.mark.asyncio
async def test_apply_with_unknown_member_id_skips_gracefully(client):
    """Unknown member_ids are silently skipped; updated count reflects only real rows."""
    with patch(
        "app.api.discord_sync.discord_sync_service.apply_discord_sync",
        new_callable=AsyncMock,
    ) as mock:
        # Service reports only 1 actual update even though 2 were submitted.
        mock.return_value = SyncApplyResponse(updated=1)
        async with client as c:
            response = await c.post(
                "/api/members/discord-sync/apply",
                json=[
                    {"member_id": 1, "discord_username": "alice_discord", "discord_id": "111"},
                    {"member_id": 9999, "discord_username": "ghost", "discord_id": "000"},
                ],
            )

    assert response.status_code == 200
    assert response.json()["updated"] == 1


# ---------------------------------------------------------------------------
# Service unit tests (preview logic, no DB required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_preview_exact_discord_id_match():
    """Heuristic 1: discord_id already set on the clan member → exact confidence."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import preview_discord_sync

    clan_member = SimpleNamespace(
        id=1,
        name="Alice",
        discord_username=None,
        discord_id="111",
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)

    guild_members = [{"id": "111", "username": "alice_discord", "display_name": "Alice D"}]

    with patch(
        "app.services.discord_sync.bot_client.get_members",
        new_callable=AsyncMock,
        return_value=guild_members,
    ):
        result = await preview_discord_sync(mock_session)

    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.confidence == "exact"
    assert match.proposed_discord_id == "111"
    assert match.proposed_discord_username == "alice_discord"
    assert result.unmatched_guild_members == []
    assert result.unmatched_clan_members == []


@pytest.mark.asyncio
async def test_service_preview_exact_discord_username_match():
    """Heuristic 2: discord_username set and matches guild username → exact confidence."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import preview_discord_sync

    clan_member = SimpleNamespace(
        id=2,
        name="Bob",
        discord_username="Bob_Discord",  # will be lowercased for comparison
        discord_id=None,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)

    guild_members = [{"id": "222", "username": "bob_discord", "display_name": "Bob D"}]

    with patch(
        "app.services.discord_sync.bot_client.get_members",
        new_callable=AsyncMock,
        return_value=guild_members,
    ):
        result = await preview_discord_sync(mock_session)

    assert len(result.matches) == 1
    assert result.matches[0].confidence == "exact"
    assert result.matches[0].proposed_discord_id == "222"


@pytest.mark.asyncio
async def test_service_preview_suggested_name_username_match():
    """Heuristic 3: clan name matches guild username → suggested confidence."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import preview_discord_sync

    clan_member = SimpleNamespace(
        id=3,
        name="Carol",
        discord_username=None,
        discord_id=None,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)

    guild_members = [{"id": "333", "username": "carol", "display_name": "Carol Smith"}]

    with patch(
        "app.services.discord_sync.bot_client.get_members",
        new_callable=AsyncMock,
        return_value=guild_members,
    ):
        result = await preview_discord_sync(mock_session)

    assert len(result.matches) == 1
    assert result.matches[0].confidence == "suggested"
    assert result.matches[0].proposed_discord_id == "333"


@pytest.mark.asyncio
async def test_service_preview_suggested_name_display_name_match():
    """Heuristic 4: clan name matches guild display_name → suggested confidence."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import preview_discord_sync

    clan_member = SimpleNamespace(
        id=4,
        name="Dave",
        discord_username=None,
        discord_id=None,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # username doesn't match "dave", but display_name does
    guild_members = [{"id": "444", "username": "d4ve_x", "display_name": "Dave"}]

    with patch(
        "app.services.discord_sync.bot_client.get_members",
        new_callable=AsyncMock,
        return_value=guild_members,
    ):
        result = await preview_discord_sync(mock_session)

    assert len(result.matches) == 1
    assert result.matches[0].confidence == "suggested"
    assert result.matches[0].proposed_discord_id == "444"


@pytest.mark.asyncio
async def test_service_preview_ambiguous_multiple_guild_matches():
    """Two guild members match the same clan member → ambiguous."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import preview_discord_sync

    clan_member = SimpleNamespace(
        id=5,
        name="Eve",
        discord_username=None,
        discord_id=None,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Both guild members have username "eve" — should trigger ambiguous
    guild_members = [
        {"id": "500", "username": "eve", "display_name": "Eve A"},
        {"id": "501", "username": "eve", "display_name": "Eve B"},
    ]

    with patch(
        "app.services.discord_sync.bot_client.get_members",
        new_callable=AsyncMock,
        return_value=guild_members,
    ):
        result = await preview_discord_sync(mock_session)

    assert len(result.matches) == 1
    assert result.matches[0].confidence == "ambiguous"


@pytest.mark.asyncio
async def test_service_preview_unmatched_guild_and_clan():
    """Members with no counterpart appear in the respective unmatched lists."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import preview_discord_sync

    clan_member = SimpleNamespace(
        id=6,
        name="Frank",
        discord_username=None,
        discord_id=None,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Guild member "ghost_user" doesn't match "Frank" on any heuristic.
    guild_members = [{"id": "999", "username": "ghost_user", "display_name": "Ghost"}]

    with patch(
        "app.services.discord_sync.bot_client.get_members",
        new_callable=AsyncMock,
        return_value=guild_members,
    ):
        result = await preview_discord_sync(mock_session)

    assert result.matches == []
    assert "ghost_user" in result.unmatched_guild_members
    assert "Frank" in result.unmatched_clan_members


@pytest.mark.asyncio
async def test_service_apply_updates_discord_fields():
    """apply_discord_sync writes discord_username and discord_id to matched members."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.member import SyncApply
    from app.services.discord_sync import apply_discord_sync

    clan_member = SimpleNamespace(
        id=1,
        name="Alice",
        discord_username=None,
        discord_id=None,
    )

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [clan_member]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    items = [SyncApply(member_id=1, discord_username="alice_discord", discord_id="111")]
    result = await apply_discord_sync(mock_session, items)

    assert result.updated == 1
    assert clan_member.discord_username == "alice_discord"
    assert clan_member.discord_id == "111"
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_apply_unknown_member_id_skipped():
    """apply_discord_sync skips member_ids not found in the DB without crashing."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.member import SyncApply
    from app.services.discord_sync import apply_discord_sync

    mock_session = MagicMock(spec=AsyncSession)
    mock_result = MagicMock()
    # DB returns nothing — the requested member_id doesn't exist.
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    items = [SyncApply(member_id=9999, discord_username="ghost", discord_id="000")]
    result = await apply_discord_sync(mock_session, items)

    assert result.updated == 0
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_apply_empty_list_returns_zero():
    """apply_discord_sync with an empty list returns updated=0 immediately."""
    from unittest.mock import MagicMock

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.discord_sync import apply_discord_sync

    mock_session = MagicMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    result = await apply_discord_sync(mock_session, [])

    assert result.updated == 0
    # Should short-circuit before executing any DB query.
    mock_session.execute.assert_not_awaited()
    mock_session.commit.assert_not_awaited()
