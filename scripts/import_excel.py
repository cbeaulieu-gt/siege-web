"""
Excel import script for Raid Shadow Legends Siege Assignment Web App.

Imports historical .xlsm siege files into the database.

Usage:
    python scripts/import_excel.py [<path>]
    python scripts/import_excel.py [<path>] --database-url postgresql+asyncpg://...

Where <path> is a single .xlsm file or a directory containing .xlsm files.
If omitted, falls back to the IMPORT_EXCEL_PATH environment variable.
"""

import argparse
import asyncio
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Add backend to path so we can import app models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base  # noqa: F401 — needed to register all models with metadata
from app.models.building import Building
from app.models.building_group import BuildingGroup
from app.models.enums import BuildingType, MemberRole, SiegeStatus
from app.models.member import Member
from app.models.position import Position
from app.models.post import Post
from app.models.siege import Siege
from app.models.siege_member import SiegeMember

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FILENAME_PATTERN = re.compile(r"clan_siege_(\d{2})_(\d{2})_(\d{4})")

BUILDING_ALIASES: dict[str, str] = {
    "Stronghold": "stronghold",
    "Mana Shrine": "mana_shrine",
    "Mana": "mana_shrine",
    "Magic Tower": "magic_tower",
    "Magic": "magic_tower",
    "Defense Tower": "defense_tower",
    "Defense": "defense_tower",
    "Post": "post",
}

ROLE_ALIASES: dict[str, str] = {
    "Heavy Hitter": "heavy_hitter",
    "Advanced": "advanced",
    "Medium": "medium",
    "Novice": "novice",
}

# building_type -> (base_group_count, last_group_slots)
BUILDING_TYPE_CONFIG: dict[str, tuple[int, int]] = {
    "stronghold": (4, 3),
    "mana_shrine": (2, 3),
    "magic_tower": (1, 2),
    "defense_tower": (1, 2),
    "post": (1, 1),
}

# ---------------------------------------------------------------------------
# Data classes for parsed sheet rows
# ---------------------------------------------------------------------------


@dataclass
class ParsedMember:
    name: str
    role: str
    power: Optional[float]
    discord_username: Optional[str]


@dataclass
class ParsedAssignment:
    building_type: str  # canonical enum value e.g. "mana_shrine"
    building_number: int
    group_number: int
    position_number: int
    value: Optional[str]  # member name, "RESERVE", or None


@dataclass
class ParsedReserve:
    member_name: str
    attack_day: Optional[int]
    has_reserve_set: Optional[bool]


@dataclass
class ImportStats:
    filename: str
    date: Optional[date] = None
    members_created: int = 0
    members_existing: int = 0
    buildings_created: int = 0
    positions_assigned: int = 0
    positions_reserve: int = 0
    positions_empty: int = 0
    siege_members_created: int = 0
    posts_created: int = 0
    siege_id: Optional[int] = None
    skipped: bool = False
    skip_reason: str = ""
    error: bool = False
    error_message: str = ""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def parse_filename_date(filename: str) -> Optional[date]:
    """Extract the siege date from a filename like clan_siege_MM_DD_YYYY.xlsm."""
    match = FILENAME_PATTERN.search(filename)
    if not match:
        return None
    month, day, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def map_role(display_role: str) -> Optional[str]:
    """Map a display role string to its enum value."""
    return ROLE_ALIASES.get(display_role)


def map_building_alias(raw_type: str) -> tuple[Optional[str], Optional[int]]:
    """
    Map a raw building type string to its canonical enum value and optional building number.

    Handles formats like "Magic Tower 1", "Post 12", "Mana Shrine 2" by stripping
    the trailing number. Returns (canonical_type, building_number) where building_number
    is extracted from the name if present, else None.
    """
    # Try exact match first
    if raw_type in BUILDING_ALIASES:
        return BUILDING_ALIASES[raw_type], None

    # Try stripping trailing number: "Magic Tower 1" -> "Magic Tower" + 1
    match = re.match(r"^(.+?)\s+(\d+)$", raw_type)
    if match:
        base_name = match.group(1)
        number = int(match.group(2))
        canonical = BUILDING_ALIASES.get(base_name)
        if canonical is not None:
            return canonical, number

    return None, None


def parse_members_sheet(ws) -> list[ParsedMember]:
    """
    Parse the 'Members' worksheet.

    Expected columns:
      A: name, B: role, C: power, D: discord_username
    Row 1 is header; data starts at row 2.
    """
    members = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name = row[0] if len(row) > 0 else None
        if not name or not str(name).strip():
            continue
        role_raw = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        power_raw = row[2] if len(row) > 2 else None
        discord_raw = row[3] if len(row) > 3 else None

        power: Optional[float] = None
        if power_raw is not None:
            try:
                power = float(power_raw)
            except (TypeError, ValueError):
                power = None

        discord_username: Optional[str] = None
        if discord_raw is not None and str(discord_raw).strip():
            discord_username = str(discord_raw).strip()

        members.append(
            ParsedMember(
                name=str(name).strip(),
                role=role_raw,
                power=power,
                discord_username=discord_username,
            )
        )
    return members


def parse_assignments_sheet(ws) -> list[ParsedAssignment]:
    """
    Parse the 'Assignments' worksheet in its visual grid format.

    Layout:
      Row 1: header row (Location | Group | Assigned | None | None | ...)
      Row 2: position sub-headers (None | None | 1 | 2 | 3 | ...)
      Row 3+: data rows
        Col A (index 0): building type display name — only filled on the FIRST row
                         of each new building instance; blank for subsequent groups
                         of the same building.
        Col B (index 1): group number (integer)
        Col C+ (index 2+): member name (or None) at position 1, 2, 3, ...

    Building number tracking:
      Each time col A is non-blank for the same canonical building type, it signals
      a new building instance and the building_number increments for that type.
      When col A is blank, the previous building type and number are carried forward.
    """
    assignments = []

    all_rows = list(ws.iter_rows(min_row=1, values_only=True))
    if len(all_rows) < 3:
        return assignments

    # Row 2 (index 1): position sub-headers starting at col C (index 2).
    # Read how many position columns the sheet actually has.
    subheader_row = all_rows[1]
    position_count = 0
    for col_idx in range(2, len(subheader_row)):
        cell = subheader_row[col_idx]
        if cell is not None:
            position_count += 1
        else:
            # Stop at first blank — positions are contiguous
            break
    # Fallback: if sub-header row is entirely blank in cols C+, infer from data width
    if position_count == 0:
        for data_row in all_rows[2:]:
            if len(data_row) > 2:
                position_count = max(position_count, len(data_row) - 2)

    # Track current building context as we scan data rows
    current_type: Optional[str] = None   # canonical building type
    # Map canonical type -> how many building instances of that type we've seen so far
    building_number_counter: dict[str, int] = {}
    current_building_number: int = 0

    for row in all_rows[2:]:  # data starts at row 3 (index 2)
        # Col A: building type name (may be blank)
        raw_type_cell = row[0] if len(row) > 0 else None
        raw_type = str(raw_type_cell).strip() if raw_type_cell is not None else ""

        # Col B: group number (may be "N/A" for single-group buildings)
        group_raw = row[1] if len(row) > 1 else None
        if group_raw is None:
            continue
        try:
            group_number = int(group_raw)
        except (TypeError, ValueError):
            # "N/A" or similar — treat as group 1
            group_number = 1

        if raw_type:
            # Non-blank col A: new building instance
            canonical_type, explicit_number = map_building_alias(raw_type)
            if canonical_type is None:
                # Unknown building type — skip this row and clear context so
                # subsequent blank-A rows don't inherit a bad type
                current_type = None
                current_building_number = 0
                continue
            current_type = canonical_type
            if explicit_number is not None:
                # Name had a number like "Magic Tower 1" — use it directly
                current_building_number = explicit_number
            else:
                # No number in name — auto-increment
                building_number_counter[canonical_type] = building_number_counter.get(canonical_type, 0) + 1
                current_building_number = building_number_counter[canonical_type]
        else:
            # Blank col A: continuing the same building as the last non-blank row
            if current_type is None:
                # No building context yet — skip
                continue

        # Emit one ParsedAssignment per position column
        for pos_idx in range(position_count):
            col_idx = 2 + pos_idx
            value_raw = row[col_idx] if col_idx < len(row) else None

            value: Optional[str] = None
            if value_raw is not None and str(value_raw).strip():
                value = str(value_raw).strip()

            assignments.append(
                ParsedAssignment(
                    building_type=current_type,
                    building_number=current_building_number,
                    group_number=group_number,
                    position_number=pos_idx + 1,
                    value=value,
                )
            )

    return assignments


def parse_reserves_sheet(ws) -> list[ParsedReserve]:
    """
    Parse the 'Reserves' worksheet.

    Expected columns:
      A: member_name, B: attack_day, C: has_reserve_set
    Row 1 is header; data starts at row 2.
    """
    reserves = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name_raw = row[0] if len(row) > 0 else None
        if not name_raw or not str(name_raw).strip():
            continue

        attack_day_raw = row[1] if len(row) > 1 else None
        has_reserve_raw = row[2] if len(row) > 2 else None

        attack_day: Optional[int] = None
        if attack_day_raw is not None:
            try:
                val = int(attack_day_raw)
                if val in (1, 2):
                    attack_day = val
            except (TypeError, ValueError):
                pass

        has_reserve_set: Optional[bool] = None
        if has_reserve_raw is not None:
            normalized = str(has_reserve_raw).strip().lower()
            if normalized == "yes":
                has_reserve_set = True
            elif normalized == "no":
                has_reserve_set = False

        reserves.append(
            ParsedReserve(
                member_name=str(name_raw).strip(),
                attack_day=attack_day,
                has_reserve_set=has_reserve_set,
            )
        )
    return reserves


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def build_group_structure(building_type: str) -> list[int]:
    """
    Return a list of slot_counts for each group of the given building type.

    e.g. stronghold -> [3, 3, 3, 3]  (4 groups, last group also has 3)
    e.g. magic_tower -> [3, 2]        (but only 1 group for magic_tower? see config)

    Actually per config:
      stronghold:   base_groups=4, last_slots=3  -> [3, 3, 3, 3]
      mana_shrine:  base_groups=2, last_slots=3  -> [3, 3]
      magic_tower:  base_groups=1, last_slots=2  -> [2]
      defense_tower:base_groups=1, last_slots=2  -> [2]
      post:         base_groups=1, last_slots=1  -> [1]

    All groups except the last have slot_count=3. The last group has last_slots.
    """
    base_groups, last_slots = BUILDING_TYPE_CONFIG[building_type]
    if base_groups == 1:
        return [last_slots]
    return [3] * (base_groups - 1) + [last_slots]


async def get_or_create_member(
    session: AsyncSession,
    parsed: ParsedMember,
) -> tuple[Member, bool]:
    """
    Return (member, created).
    Looks up by name (case-insensitive). Creates if not found.
    """
    result = await session.execute(
        select(Member).where(Member.name.ilike(parsed.name))
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing, False

    role_value = map_role(parsed.role)
    if role_value is None:
        # Default to novice if role is unrecognised
        role_value = "novice"

    member = Member(
        name=parsed.name,
        role=MemberRole(role_value),
        power=parsed.power,
        discord_username=parsed.discord_username,
        is_active=True,
    )
    session.add(member)
    await session.flush()  # get the id without committing
    return member, True


async def create_building_with_groups_and_positions(
    session: AsyncSession,
    siege_id: int,
    building_type: str,
    building_number: int,
) -> tuple[Building, dict[tuple[int, int], Position]]:
    """
    Create a Building, its BuildingGroups, and their Positions.

    Returns (building, positions_map) where positions_map is
    {(group_number, position_number): Position}.
    """
    building = Building(
        siege_id=siege_id,
        building_type=BuildingType(building_type),
        building_number=building_number,
        level=1,
        is_broken=False,
    )
    session.add(building)
    await session.flush()

    slot_counts = build_group_structure(building_type)
    positions_map: dict[tuple[int, int], Position] = {}

    for group_idx, slot_count in enumerate(slot_counts, start=1):
        group = BuildingGroup(
            building_id=building.id,
            group_number=group_idx,
            slot_count=slot_count,
        )
        session.add(group)
        await session.flush()

        for pos_num in range(1, slot_count + 1):
            position = Position(
                building_group_id=group.id,
                position_number=pos_num,
            )
            session.add(position)
            await session.flush()
            positions_map[(group_idx, pos_num)] = position

    return building, positions_map


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------


async def import_file(
    session: AsyncSession,
    filepath: Path,
) -> ImportStats:
    """Import a single .xlsm file. Returns ImportStats."""
    import openpyxl

    stats = ImportStats(filename=filepath.name)

    # 1. Extract date from filename
    siege_date = parse_filename_date(filepath.name)
    if siege_date is None:
        stats.skipped = True
        stats.skip_reason = f"Filename does not match pattern clan_siege_DD_MM_YYYY: {filepath.name}"
        return stats

    stats.date = siege_date

    # Load workbook
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    except Exception as exc:
        stats.error = True
        stats.error_message = f"Failed to open workbook: {exc}"
        return stats

    # 2. Parse sheets
    print(f"  Available sheets: {wb.sheetnames}")
    try:
        members_ws = wb["Members"]
        assignments_ws = wb["Assignments"]
        reserves_ws = wb["Reserves"]
    except KeyError as exc:
        stats.error = True
        stats.error_message = f"Missing required sheet: {exc}. Available: {wb.sheetnames}"
        wb.close()
        return stats

    parsed_members = parse_members_sheet(members_ws)
    parsed_assignments = parse_assignments_sheet(assignments_ws)
    parsed_reserves = parse_reserves_sheet(reserves_ws)
    wb.close()

    print(f"  Parsed: {len(parsed_members)} members, {len(parsed_assignments)} assignments, {len(parsed_reserves)} reserves")

    # Debug: dump ALL raw rows from Assignments sheet
    wb2 = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws2 = wb2["Assignments"]
    print("  DEBUG Assignments ALL rows:")
    for i, row in enumerate(ws2.iter_rows(min_row=1, values_only=True)):
        # Only print rows that have any non-None value in first 6 cols
        first6 = row[:6] if len(row) >= 6 else row
        if any(c is not None for c in first6):
            print(f"    Row {i+1}: {first6}")
    wb2.close()

    # 3. Upsert members
    member_name_map: dict[str, Member] = {}  # lowercase name -> Member
    for pm in parsed_members:
        member, created = await get_or_create_member(session, pm)
        member_name_map[member.name.lower()] = member
        if created:
            stats.members_created += 1
        else:
            stats.members_existing += 1

    # 4. Create Siege
    siege = Siege(
        date=siege_date,
        status=SiegeStatus.complete,
        defense_scroll_count=3,
    )
    session.add(siege)
    await session.flush()
    stats.siege_id = siege.id

    # 5. Create Buildings, groups, and positions
    # Collect unique (building_type, building_number) pairs in insertion order
    seen_buildings: dict[tuple[str, int], tuple[Building, dict[tuple[int, int], Position]]] = {}
    for assignment in parsed_assignments:
        key = (assignment.building_type, assignment.building_number)
        if key not in seen_buildings:
            building, positions_map = await create_building_with_groups_and_positions(
                session,
                siege.id,
                assignment.building_type,
                assignment.building_number,
            )
            seen_buildings[key] = (building, positions_map)
            stats.buildings_created += 1

    # 6. Assign positions
    for assignment in parsed_assignments:
        key = (assignment.building_type, assignment.building_number)
        if key not in seen_buildings:
            continue
        _, positions_map = seen_buildings[key]
        pos_key = (assignment.group_number, assignment.position_number)
        position = positions_map.get(pos_key)
        if position is None:
            # Position doesn't exist in our structure (data mismatch), skip
            continue

        if assignment.value is None:
            stats.positions_empty += 1
        elif assignment.value.upper() == "RESERVE":
            position.is_reserve = True
            stats.positions_reserve += 1
        else:
            # Member assignment — look up by name
            member = member_name_map.get(assignment.value.lower())
            if member is not None:
                position.member_id = member.id
                stats.positions_assigned += 1
            else:
                # Member appeared in assignments but not in Members sheet
                # Try a DB lookup as fallback
                result = await session.execute(
                    select(Member).where(Member.name.ilike(assignment.value))
                )
                fallback_member = result.scalar_one_or_none()
                if fallback_member:
                    position.member_id = fallback_member.id
                    member_name_map[fallback_member.name.lower()] = fallback_member
                    stats.positions_assigned += 1
                else:
                    stats.positions_empty += 1

    # 7. Create SiegeMember rows
    for reserve in parsed_reserves:
        member = member_name_map.get(reserve.member_name.lower())
        if member is None:
            # Try DB lookup
            result = await session.execute(
                select(Member).where(Member.name.ilike(reserve.member_name))
            )
            member = result.scalar_one_or_none()
            if member:
                member_name_map[member.name.lower()] = member

        if member is None:
            continue

        siege_member = SiegeMember(
            siege_id=siege.id,
            member_id=member.id,
            attack_day=reserve.attack_day,
            has_reserve_set=reserve.has_reserve_set,
        )
        session.add(siege_member)
        stats.siege_members_created += 1

    # 8. Create Post rows for all post-type buildings
    for (building_type, _), (building, _) in seen_buildings.items():
        if building_type == "post":
            post = Post(
                siege_id=siege.id,
                building_id=building.id,
                priority=0,
                description=None,
            )
            session.add(post)
            stats.posts_created += 1

    await session.flush()
    return stats


async def import_files(
    database_url: str,
    filepaths: list[Path],
) -> None:
    """Import a list of .xlsm files into the database."""
    engine = create_async_engine(database_url, echo=False)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    total_imported = 0
    total_skipped = 0
    total_errors = 0

    for filepath in filepaths:
        print(f"Importing: {filepath.name}")

        async with SessionFactory() as session:
            async with session.begin():
                try:
                    stats = await import_file(session, filepath)
                except Exception as exc:
                    await session.rollback()
                    print(f"  ERROR: Unexpected error — {exc}")
                    total_errors += 1
                    continue

        if stats.skipped:
            print(f"  SKIPPED: {stats.skip_reason}")
            total_skipped += 1
            continue

        if stats.error:
            print(f"  ERROR: {stats.error_message}")
            total_errors += 1
            continue

        print(f"  Date: {stats.date}")
        print(
            f"  Members: {stats.members_created} created, "
            f"{stats.members_existing} existing"
        )
        print(f"  Buildings: {stats.buildings_created} created")
        print(
            f"  Positions: {stats.positions_assigned} assigned, "
            f"{stats.positions_reserve} RESERVE, "
            f"{stats.positions_empty} empty"
        )
        print(f"  Siege members: {stats.siege_members_created} created")
        print(f"  Posts: {stats.posts_created} created")
        print(f"  + Siege #{stats.siege_id} created (status: complete)")
        total_imported += 1

    print()
    print(
        f"Summary: {total_imported} files imported, "
        f"{total_skipped} skipped, "
        f"{total_errors} errors"
    )

    await engine.dispose()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def collect_xlsm_files(path: Path) -> list[Path]:
    """Return a sorted list of .xlsm files from a file path or directory."""
    if path.is_file():
        if path.suffix.lower() == ".xlsm":
            return [path]
        print(f"Warning: {path} is not a .xlsm file, skipping.")
        return []
    if path.is_dir():
        files = sorted(path.glob("*.xlsm"))
        if not files:
            print(f"Warning: no .xlsm files found in {path}")
        return list(files)
    print(f"Error: {path} does not exist.")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import historical .xlsm siege files into the database."
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to a single .xlsm file or a directory containing .xlsm files. "
        "Falls back to IMPORT_EXCEL_PATH env var if not provided.",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("IMPORT_DATABASE_URL", os.environ.get("DATABASE_URL")),
        help="Database connection URL (defaults to IMPORT_DATABASE_URL, then DATABASE_URL env var).",
    )
    args = parser.parse_args()

    if not args.database_url:
        print(
            "Error: DATABASE_URL is not set. "
            "Provide it via --database-url or the DATABASE_URL environment variable."
        )
        sys.exit(1)

    path = args.path or os.environ.get("IMPORT_EXCEL_PATH")
    if not path:
        print(
            "Error: No import path provided. "
            "Pass it as an argument or set the IMPORT_EXCEL_PATH environment variable."
        )
        sys.exit(1)

    filepaths = collect_xlsm_files(Path(path))
    if not filepaths:
        sys.exit(0)

    asyncio.run(import_files(args.database_url, filepaths))


if __name__ == "__main__":
    main()
