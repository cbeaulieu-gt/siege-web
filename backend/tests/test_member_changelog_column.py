"""Schema-aware tests for Member.last_seen_changelog_at (issue #295, AC 1).

These tests verify the ORM column definition — nullability, type, and
default — without requiring a live database connection.  They serve as a
regression guard: if the column is accidentally removed or made non-nullable
they will fail immediately in CI.
"""

import datetime

import sqlalchemy as sa

from app.models.member import Member

# ---------------------------------------------------------------------------
# 1. Column exists on the mapped class
# ---------------------------------------------------------------------------


def test_last_seen_changelog_at_column_exists() -> None:
    """Member mapper exposes last_seen_changelog_at as a mapped attribute."""
    assert hasattr(
        Member, "last_seen_changelog_at"
    ), "Member model is missing last_seen_changelog_at attribute"


# ---------------------------------------------------------------------------
# 2. Column is nullable
# ---------------------------------------------------------------------------


def test_last_seen_changelog_at_column_is_nullable() -> None:
    """last_seen_changelog_at column is defined nullable=True.

    Null is the sentinel value meaning 'user has never viewed the changelog'.
    Making it non-nullable would break new member rows that have no seen
    timestamp yet.
    """
    col = Member.__table__.c["last_seen_changelog_at"]
    assert col.nullable is True, (
        "last_seen_changelog_at must be nullable=True; " f"got nullable={col.nullable}"
    )


# ---------------------------------------------------------------------------
# 3. Column has no server default
# ---------------------------------------------------------------------------


def test_last_seen_changelog_at_has_no_server_default() -> None:
    """last_seen_changelog_at has no server-side default.

    Null is the intentional initial state.  A server default would mask
    new members who have genuinely never seen the changelog.
    """
    col = Member.__table__.c["last_seen_changelog_at"]
    assert col.server_default is None, (
        "last_seen_changelog_at must have no server default; "
        f"got server_default={col.server_default!r}"
    )


# ---------------------------------------------------------------------------
# 4. Column type is DateTime (no timezone)
# ---------------------------------------------------------------------------


def test_last_seen_changelog_at_column_type_is_datetime() -> None:
    """last_seen_changelog_at uses SQLAlchemy DateTime (no timezone).

    Matches the created_at column convention: naive timestamps stored and
    compared in UTC by application convention, not enforced by the DB type.
    """
    col = Member.__table__.c["last_seen_changelog_at"]
    assert isinstance(
        col.type, sa.DateTime
    ), f"Expected DateTime column type, got {type(col.type).__name__}"
    # Confirm no timezone flag — matches created_at precedent
    assert not getattr(
        col.type, "timezone", False
    ), "last_seen_changelog_at must not have timezone=True"


# ---------------------------------------------------------------------------
# 5. Python-level type annotation accepts datetime | None
# ---------------------------------------------------------------------------


def test_last_seen_changelog_at_accepts_none_at_python_level() -> None:
    """Mapped type annotation allows None (datetime | None).

    Constructing a Member with last_seen_changelog_at=None must not raise.
    This is a quick unit-level sanity check that the ORM annotation is
    correct; it does not exercise DB I/O.
    """
    member = Member(
        name="TestMember",
        last_seen_changelog_at=None,
    )
    assert member.last_seen_changelog_at is None


def test_last_seen_changelog_at_accepts_datetime_at_python_level() -> None:
    """Mapped type annotation allows a datetime value.

    Assigning a real datetime must not raise at construction time.
    """
    ts = datetime.datetime(2026, 5, 8, 12, 0, 0)
    member = Member(
        name="TestMember",
        last_seen_changelog_at=ts,
    )
    assert member.last_seen_changelog_at == ts
