"""Integration tests for GET /api/members and GET /api/members/{id}.

Exercises the live bot sidecar (started by the ``bot_url`` fixture in
``conftest.py``) over a real TCP socket.

Contract source: ``bot/INTERFACE.md`` → ``GET /api/members`` and
``GET /api/members/{discord_user_id}`` sections.

Key shape notes (from INTERFACE.md)
------------------------------------
- ``GET /api/members`` element key for Discord ID is ``id`` (NOT
  ``discord_id``).  This is load-bearing; alternative sidecars MUST use
  ``id`` here.
- ``GET /api/members/{id}`` key for Discord ID is ``discord_id``.
- All six keys are always present in ``/members/{id}`` responses regardless
  of membership status.

Known member (configured in ``FakeDiscordClient``)
---------------------------------------------------
  id=``"111000111000111001"``, username=``"known-user"``
"""

from __future__ import annotations

import httpx

from .conftest import AUTH_HEADERS

_KNOWN_MEMBER_ID = "111000111000111001"
_UNKNOWN_MEMBER_ID = "999000999000999001"

# Keys required by the interface contract for GET /api/members elements
_MEMBERS_LIST_KEYS = {"id", "username", "display_name"}

# Keys required by the interface contract for GET /api/members/{id} responses
_MEMBER_DETAIL_KEYS = {
    "is_member",
    "discord_id",
    "username",
    "display_name",
    "roles",
    "role_names",
}


# ---------------------------------------------------------------------------
# GET /api/members
# ---------------------------------------------------------------------------


def test_get_members_returns_200_with_array(bot_url: str) -> None:
    """GET /api/members returns 200 with a JSON array.

    Validates both status code and body shape per acceptance criteria.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_members_elements_have_three_required_keys(bot_url: str) -> None:
    """GET /api/members each element has exactly ``id``, ``username``, ``display_name``.

    The ``id`` key (not ``discord_id``) is load-bearing per the interface
    contract.  This test explicitly catches the ``id`` → ``discord_id``
    rename regression that ``BotClient`` depends on.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1, "Expected at least the known member in the list"
    for element in data:
        assert set(element.keys()) == _MEMBERS_LIST_KEYS, (
            f"Member element keys mismatch: got {set(element.keys())}, "
            f"expected {_MEMBERS_LIST_KEYS}"
        )


def test_get_members_known_member_present_with_correct_fields(bot_url: str) -> None:
    """GET /api/members includes the known member with correct field types.

    All three fields (``id``, ``username``, ``display_name``) must be
    non-empty strings.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members", headers=AUTH_HEADERS)
    assert response.status_code == 200
    members = response.json()
    known = next((m for m in members if m["id"] == _KNOWN_MEMBER_ID), None)
    assert known is not None, f"Known member {_KNOWN_MEMBER_ID} not found in response"
    assert isinstance(known["id"], str)
    assert isinstance(known["username"], str)
    assert isinstance(known["display_name"], str)
    assert len(known["id"]) > 0
    assert len(known["username"]) > 0


# ---------------------------------------------------------------------------
# GET /api/members/{discord_user_id} — known member
# ---------------------------------------------------------------------------


def test_get_member_by_id_known_returns_200_is_member_true(bot_url: str) -> None:
    """GET /api/members/{id} for a known member returns 200 with ``is_member: true``.

    Validates all six keys are present with non-null values for member fields.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members/{_KNOWN_MEMBER_ID}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == _MEMBER_DETAIL_KEYS
    assert data["is_member"] is True
    assert isinstance(data["discord_id"], str)
    assert isinstance(data["username"], str)
    assert isinstance(data["display_name"], str)
    assert isinstance(data["roles"], list)
    assert isinstance(data["role_names"], list)


def test_get_member_by_id_known_has_correct_values(bot_url: str) -> None:
    """GET /api/members/{id} known member fields match the fake's configured values.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members/{_KNOWN_MEMBER_ID}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["discord_id"] == _KNOWN_MEMBER_ID
    assert data["username"] == "known-user"
    assert data["display_name"] == "Known User"


# ---------------------------------------------------------------------------
# GET /api/members/{discord_user_id} — unknown member
# ---------------------------------------------------------------------------


def test_get_member_by_id_unknown_returns_200_is_member_false(bot_url: str) -> None:
    """GET /api/members/{id} for an unknown ID returns 200 with ``is_member: false``.

    All six keys must be present; the five non-discriminator keys must be
    ``null``.

    Args:
        bot_url: Base URL of the running bot sidecar (session fixture).
    """
    response = httpx.get(f"{bot_url}/api/members/{_UNKNOWN_MEMBER_ID}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == _MEMBER_DETAIL_KEYS
    assert data["is_member"] is False
    assert data["discord_id"] is None
    assert data["username"] is None
    assert data["display_name"] is None
    assert data["roles"] is None
    assert data["role_names"] is None
