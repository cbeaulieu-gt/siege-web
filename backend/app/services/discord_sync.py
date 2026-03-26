"""Service logic for Discord guild member → clan member matching."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.schemas.member import SyncApply, SyncApplyResponse, SyncMatch, SyncPreviewResponse
from app.services.bot_client import bot_client


async def preview_discord_sync(session: AsyncSession) -> SyncPreviewResponse:
    """Return proposed matches between Discord guild members and clan members.

    Matching is attempted in priority order:
    1. discord_id already set and matches guild id (exact — already linked)
    2. discord_username matches guild username (case-insensitive, exact)
    3. clan name matches guild username (case-insensitive)
    4. clan name matches guild display_name (case-insensitive)

    Confidence is "exact" for heuristics 1–2, "suggested" for 3–4, and
    "ambiguous" when more than one guild member maps to the same clan member
    (or vice versa).
    """
    guild_members: list[dict] = await bot_client.get_members()

    result = await session.execute(select(Member))
    clan_members: list[Member] = list(result.scalars().all())

    # Build lookup maps for guild members to allow fast case-insensitive search.
    # key: lowercase username → guild member dict
    guild_by_username: dict[str, list[dict]] = {}
    # key: lowercase display_name → guild member dict
    guild_by_display: dict[str, list[dict]] = {}
    # key: discord id → guild member dict
    guild_by_id: dict[str, dict] = {}

    for gm in guild_members:
        gm_id = gm.get("id", "")
        gm_username = gm.get("username", "")
        gm_display = gm.get("display_name", "")

        if gm_id:
            guild_by_id[gm_id] = gm

        if gm_username:
            key = gm_username.lower()
            guild_by_username.setdefault(key, []).append(gm)

        if gm_display:
            key = gm_display.lower()
            guild_by_display.setdefault(key, []).append(gm)

    # For ambiguity detection we track how many clan members map to each guild id.
    # guild_id → list of clan member ids that matched it
    guild_id_to_clan_ids: dict[str, list[int]] = {}

    # First pass: determine best candidate guild member for each clan member.
    # candidate: (guild_member_dict, confidence_rank)
    # confidence_rank: 1=exact, 2=exact, 3=suggested, 4=suggested
    CandidateEntry = tuple[dict, int]
    clan_to_candidates: dict[int, list[CandidateEntry]] = {}

    for cm in clan_members:
        candidates: list[CandidateEntry] = []

        # Heuristic 1: discord_id already set and matches a guild member.
        if cm.discord_id and cm.discord_id in guild_by_id:
            candidates.append((guild_by_id[cm.discord_id], 1))

        # Heuristic 2: discord_username matches guild username (case-insensitive).
        if cm.discord_username:
            key = cm.discord_username.lower()
            for gm in guild_by_username.get(key, []):
                if not any(c[0]["id"] == gm["id"] for c in candidates):
                    candidates.append((gm, 2))

        # Heuristic 3: clan name matches guild username.
        key = cm.name.lower()
        for gm in guild_by_username.get(key, []):
            if not any(c[0]["id"] == gm["id"] for c in candidates):
                candidates.append((gm, 3))

        # Heuristic 4: clan name matches guild display_name.
        for gm in guild_by_display.get(key, []):
            if not any(c[0]["id"] == gm["id"] for c in candidates):
                candidates.append((gm, 4))

        if candidates:
            # Keep only the best rank (lowest number).
            best_rank = min(c[1] for c in candidates)
            best = [c for c in candidates if c[1] == best_rank]
            clan_to_candidates[cm.id] = best

            for gm, _ in best:
                guild_id_to_clan_ids.setdefault(gm["id"], []).append(cm.id)

    # Second pass: build matches, flagging ambiguous cases.
    matched_clan_ids: set[int] = set()
    matched_guild_ids: set[str] = set()
    matches: list[SyncMatch] = []

    clan_member_by_id = {cm.id: cm for cm in clan_members}

    for cm in clan_members:
        candidates = clan_to_candidates.get(cm.id)
        if not candidates:
            continue

        best_rank = candidates[0][1]
        base_confidence = "exact" if best_rank <= 2 else "suggested"

        # Ambiguous if this clan member has multiple best candidates, OR if
        # any of its best candidates also match another clan member.
        is_ambiguous = len(candidates) > 1 or any(
            len(guild_id_to_clan_ids.get(gm["id"], [])) > 1 for gm, _ in candidates
        )

        confidence = "ambiguous" if is_ambiguous else base_confidence

        # For ambiguous matches we still emit a row so the user can see them,
        # but we pick the first candidate arbitrarily for display.
        chosen_gm = candidates[0][0]

        matches.append(
            SyncMatch(
                member_id=cm.id,
                member_name=cm.name,
                current_discord_username=cm.discord_username,
                proposed_discord_username=chosen_gm.get("username", ""),
                proposed_discord_id=chosen_gm.get("id", ""),
                confidence=confidence,
            )
        )
        matched_clan_ids.add(cm.id)
        matched_guild_ids.add(chosen_gm.get("id", ""))

    # Collect unmatched guild members (by username for display).
    unmatched_guild_members = [
        gm.get("username", gm.get("id", ""))
        for gm in guild_members
        if gm.get("id", "") not in matched_guild_ids
    ]

    # Collect unmatched clan members.
    unmatched_clan_members = [cm.name for cm in clan_members if cm.id not in matched_clan_ids]

    return SyncPreviewResponse(
        matches=matches,
        unmatched_guild_members=unmatched_guild_members,
        unmatched_clan_members=unmatched_clan_members,
    )


async def apply_discord_sync(session: AsyncSession, items: list[SyncApply]) -> SyncApplyResponse:
    """Apply accepted sync matches, writing discord_username and discord_id.

    Unknown member_ids are silently skipped.
    """
    if not items:
        return SyncApplyResponse(updated=0)

    member_ids = [item.member_id for item in items]
    result = await session.execute(select(Member).where(Member.id.in_(member_ids)))
    members_by_id: dict[int, Member] = {m.id: m for m in result.scalars().all()}

    updated = 0
    for item in items:
        member = members_by_id.get(item.member_id)
        if member is None:
            # Unknown id — skip gracefully.
            continue
        member.discord_username = item.discord_username
        member.discord_id = item.discord_id
        updated += 1

    await session.commit()
    return SyncApplyResponse(updated=updated)
