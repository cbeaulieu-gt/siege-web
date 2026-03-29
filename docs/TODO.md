# TODO

## Bug #74 — Notification spinner never stops (PR #76)
- [x] Compute `batchInProgress` state in `SiegeSettingsPage`
- [x] Show spinner on "Notify Members" button while batch is in-progress (not just POST)
- [x] Add test: button stays disabled/spinning while batch is in-progress
- [x] Add test: button re-enables after batch completes

## Bug #75 — Unchecking Broken doesn't restore slot count (PR #77)
- [x] Add `else` branch in `update_building` for `is_broken=False` case
- [x] Restore building groups/positions to level-appropriate config when unbreaking
- [x] Add backend tests for unbreak restoration

## Issue #68 — Image layout improvements (PR #72)
- [x] Remove building level from building header (keep `#N` and `[broken]` only)
- [x] Make building number a spanning `<thead>` row inside the table
- [x] Render Post buildings as a flat single table (one column per post, one member row)
- [x] Update `test_image_gen.py` to match new layout (fix level assertions, add thead/post tests)

## Issue #57 — Rich per-member Discord DM (PR #73)
- [x] Add `PositionInfo` dataclass and `build_member_notification_message` helper
- [x] Unit tests for message builder (no change / remove from / set at sections, first siege, empty sections)
- [x] Update `notify_siege_members` to query previous siege and per-member positions
- [x] Build per-member message and pass it in `members_data` instead of static string

## Issue #71 — Role colors in Discord images should match UI
- [x] Update `_MEMBER_ROLE_COLORS` in `image_gen.py` to match UI hue families (red/amber/green/blue)
- [x] Update existing role-color test assertions in `test_image_gen.py`
- [x] Add new tests asserting each role maps to the correct dark-mode-friendly color

## Issue #78 — Discord DM icons per change type + blank-line section spacing (PR #84)
- [x] Replace `_build_section` header with per-type emoji prefix on each line (no section header)
- [x] Add blank line between each change-type group in `build_member_notification_message`
- [x] Update existing tests in `test_notification_message.py` to match new format
- [x] Add new tests: icons appear on correct lines, blank-line separator present

## Issues #78 + #71 — Fix Discord DM format: icons belong on section headers, not per-line
- [x] Replace raw Unicode `_CHANGE_TYPE_ICON` values with Discord shortcode strings
- [x] Add `_CHANGE_TYPE_LABEL` dict for human-readable section headers
- [x] Rewrite `_build_section()` to produce `{icon}  {Label}  {icon}` header + plain position lines
- [x] Update `ICON_*` constants in test file to use shortcode strings
- [x] Replace 3 "per-line icon prefix" tests with 3 "section header + plain lines" tests
- [x] Add 2 new tests for exact header format (group 13)
- [x] All 21 tests pass

## Discord DM formatting polish (PR #86)
- [x] Add WIP warning line at top of message
- [x] Bold the title line
- [x] Bold the metadata field keys (`Have Reserve Set:`, `Attack Day:`)
- [x] Change section header to `{icon} ** {Label} ** {icon}` (bold label with surrounding spaces)
- [x] Prefix each position line with `- `
- [x] Update test assertions to match new format

## Bug #80 — Batch succeeds but per-member status shows "Notification failed" / "Status unknown"
- [x] Backend: commit `batch.status = completed` atomically with result rows in the same transaction (try block), not in always-running `finally`
- [x] Backend: keep `finally` block as safety net — only fires when try block raised, marks batch `completed` via isolated session
- [x] Frontend: change "Notification failed" label to "Status unknown" for `batchComplete && success === null` case (result recording failed, DM status is ambiguous)
- [x] Frontend test: update existing test to expect "Status unknown" instead of "Notification failed"
- [x] Backend (root cause): `sent_at = datetime.now(UTC)` stores timezone-aware datetime into a `TIMESTAMP WITHOUT TIME ZONE` column — asyncpg raises DataError on flush, silently aborting the commit. Fix: `.replace(tzinfo=None)` (matches pattern in autofill.py and attack_day.py)

## Issue #88 — Split .env.deploy into per-environment files
- [x] Rename `.env.deploy` → `.env.deploy.prod`
- [x] Copy to `.env.deploy.dev` with header comment listing values to change
- [x] Update `.gitignore`: `.env.deploy` → `.env.deploy.*`
- [x] Update `.env.deploy.example` to reflect new naming convention
- [x] Update `bootstrap-images.ps1`: add `-EnvFile` parameter, default `.env.deploy.prod`
- [x] Update `README.md`: add Deploy environments section
- [x] Verify both new files are gitignored
- [x] Commit tracked changes and open PR

## Issue #94 — Scroll-per-member: use total potential scrolls from unbroken buildings (PR #97)
- [x] Add `Building.is_broken == False` filter to `compute_scroll_count` in `backend/app/services/sieges.py`
- [x] Update docstring to explain both filters serve independent purposes
- [x] Add regression tests asserting both filters appear in generated SQL
