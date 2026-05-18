# mom-bot: Post-Condition Preference Integration Guide

This document is a handoff brief for the agent implementing mom-bot's integration
with siege-web's member post-condition preference endpoints. It covers only the
per-member get/set surface. Post-condition catalog enumeration and all other
siege-web endpoints are out of scope.

---

## What this is

siege-web maintains a per-member list of preferred post-conditions — the
stronghold building states a member is willing to attack. mom-bot reads and writes
this list on behalf of individual Discord users by calling two `/api/members/me/`
endpoints. The `/me/` path variant resolves the target member from headers rather
than from a URL path parameter, which is the contract designed for bot consumers.

---

## Endpoints

| Method | Path                           | Request body                          | Response                        |
|--------|--------------------------------|---------------------------------------|---------------------------------|
| GET    | `/api/members/me/preferences`  | none                                  | `list[PostConditionResponse]`   |
| PUT    | `/api/members/me/preferences`  | `{"post_condition_ids": [int, ...]}`  | `list[PostConditionResponse]`   |

**PostConditionResponse shape:**

```json
{
  "id": 12,
  "description": "Only Barbarian Champions can be used.",
  "stronghold_level": 1,
  "condition_type": "faction"
}
```

Fields: `id` (stable backend integer), `description` (human-readable label),
`stronghold_level` (the stronghold level this condition applies to),
`condition_type` (category string — see Schema Contract below).

---

## Authentication

Both endpoints require two headers on every request. Neither is optional when
calling as a bot service.

| Header                  | Value                              | Purpose                                          |
|-------------------------|------------------------------------|--------------------------------------------------|
| `Authorization`         | `Bearer <BOT_SERVICE_TOKEN>`       | Authenticates mom-bot as a trusted service caller |
| `X-Acting-Discord-Id`   | Discord snowflake (numeric string) | Tells siege-web which member's data to operate on |

**What each header does:**

- `Authorization: Bearer <BOT_SERVICE_TOKEN>` — siege-web performs a
  timing-safe comparison against the `BOT_SERVICE_TOKEN` secret it was started
  with. A missing or wrong token returns **401**.
- `X-Acting-Discord-Id` — siege-web looks up the supplied Discord snowflake
  in its Member table to find the target member. A missing header on a
  service-token request returns **401** (no unambiguous subject). An ID that
  does not match any known member returns **404**.

**Security:** `BOT_SERVICE_TOKEN` is a shared secret. Store it in mom-bot's
secret store (environment variable, secrets manager, etc.) and never log it,
echo it to Discord, or include it in error messages.

---

## PUT semantics: replacement, not append

`PUT /api/members/me/preferences` is a **replacement set** operation. The IDs
you send become the member's complete preference list — any IDs previously saved
but absent from the new body are removed. There is no partial-update or additive
endpoint.

When building the Discord interaction that lets a user set preferences (e.g. a
select-menu), present all available choices and submit the full desired set in
one PUT. Do not read-modify-write; the API does not support incremental updates
and a read-modify-write pattern is subject to race conditions.

---

## Schema Contract

### PostConditionResponse — formal schema

```json
{
  "id": 5,                                   // int, ≥1, stable (never reused)
  "description": "Only HP Champions can be used.",  // string, human-readable
  "stronghold_level": 1,                     // int, one of: 1 | 2 | 3
  "condition_type": "role"                   // string, one of 7 closed values
}
```

`condition_type` is guaranteed present in all responses. The backend enforces
the closed set via a CHECK constraint — a value outside the seven listed below
cannot appear.

### `condition_type` value enumeration

Values are drawn from the seeded catalog (`backend/app/db/seeds.py`). The set is
closed — the backend enforces it with a CheckConstraint. A new value requires a
coordinated schema change; it will never appear silently.

| Value      | Meaning                                      | Example conditions (seeded)                                                    |
|------------|----------------------------------------------|--------------------------------------------------------------------------------|
| `league`   | Faction alliance (Telerian, Gaellen, etc.)   | Telerian League · Gaellen Pact · The Corrupted · Nyresan Union                |
| `role`     | Champion combat role                         | HP · DEF · Support · ATK                                                       |
| `faction`  | Specific in-game faction                     | Banner Lords · High Elves · Sacred Order · Barbarian · Ogryn Tribe · Lizardmen · Skinwalker · Orc · Demonspawn · Undead Horde · Dark Elves · Knights Revenant · Dwarves · Shadowkin · Sylvan Watcher |
| `affinity` | Elemental affinity                           | Void · Force · Magic · Spirit                                                  |
| `rarity`   | Champion rarity tier                         | Legendary · Epic · Rare                                                        |
| `effect`   | Immunity to a game mechanic                  | Turn Meter reduction immunity · Turn Meter fill immunity · Cooldown increasing immunity · Cooldown decreasing immunity · [Sheep] immunity |
| `other`    | Conditions that don't fit a specific category | Champions cannot be revived.                                                  |

Suggested display order (matches frontend): `role`, `affinity`, `faction`, `league`, `rarity`, `effect`, `other`. Frontend display labels mirror the value names (title-cased); mom-bot may use the same or its own.

### PUT request schema

```json
{
  "post_condition_ids": [5, 12, 17]   // list[int]; each ID must exist in siege-web's DB
}
```

IDs that do not exist in siege-web's database return **422**. See the Error modes
table for the recommended recovery action.

### Worked example: grouping preferences by category

Given this GET response:

```json
[
  {"id": 5,  "description": "Only HP Champions can be used.",          "stronghold_level": 1, "condition_type": "role"},
  {"id": 12, "description": "Only Barbarian Champions can be used.",   "stronghold_level": 1, "condition_type": "faction"},
  {"id": 17, "description": "All Champions are immune to Turn Meter reduction effects.", "stronghold_level": 1, "condition_type": "effect"},
  {"id": 19, "description": "Only Void Champions can be used.",        "stronghold_level": 2, "condition_type": "affinity"}
]
```

Group by `condition_type` in display order, then render each group:

```python
DISPLAY_ORDER = ["role", "affinity", "faction", "league", "rarity", "effect", "other"]

def group_preferences(prefs):
    groups = {ct: [] for ct in DISPLAY_ORDER}
    for p in prefs:
        groups.setdefault(p["condition_type"], []).append(p["description"])
    return [(ct, groups[ct]) for ct in DISPLAY_ORDER if groups[ct]]

for label, descriptions in group_preferences(preferences):
    print(f"**{label.capitalize()}**")
    for desc in descriptions:
        print(f"  - {desc}")
```

---

## Example requests

Replace `<BOT_SERVICE_TOKEN>`, `<DISCORD_ID>`, and `<SIEGE_WEB_HOST>` with
values from your environment.

**GET — read a member's current preferences:**

```bash
curl -s \
  -H "Authorization: Bearer <BOT_SERVICE_TOKEN>" \
  -H "X-Acting-Discord-Id: <DISCORD_ID>" \
  https://<SIEGE_WEB_HOST>/api/members/me/preferences
```

Example response:

```json
[
  {"id": 5,  "description": "Only HP Champions can be used.",        "stronghold_level": 1, "condition_type": "role"},
  {"id": 12, "description": "Only Barbarian Champions can be used.", "stronghold_level": 1, "condition_type": "faction"}
]
```

**PUT — replace a member's preferences:**

```bash
curl -s -X PUT \
  -H "Authorization: Bearer <BOT_SERVICE_TOKEN>" \
  -H "X-Acting-Discord-Id: <DISCORD_ID>" \
  -H "Content-Type: application/json" \
  -d '{"post_condition_ids": [5, 12, 17]}' \
  https://<SIEGE_WEB_HOST>/api/members/me/preferences
```

Response is the same shape as GET — the full updated preference list.

---

## Error modes

| Status | Trigger                                                                 | Action                                                          |
|--------|-------------------------------------------------------------------------|-----------------------------------------------------------------|
| 400    | `X-Acting-Discord-Id` is present but not a valid numeric snowflake      | Validate the Discord ID before sending                          |
| 401    | Wrong or missing `Authorization` header                                 | Check `BOT_SERVICE_TOKEN` in mom-bot's config                   |
| 401    | Valid service token but `X-Acting-Discord-Id` header is absent          | Always include the header; there is no default subject          |
| 404    | `X-Acting-Discord-Id` value does not match any Member in siege-web's DB | The user may not be registered; surface a user-facing message   |
| 422    | `post_condition_ids` contains IDs that don't exist in siege-web's DB    | Fetch current valid IDs before submitting; do not cache IDs indefinitely |

---

## Out of scope

This document does not cover:

- How to enumerate the full catalog of available post-conditions (the set of
  valid IDs to present to users in a select-menu).
- The `/api/members/{member_id}/preferences` sibling routes — those require a
  user session cookie and are not for bot use.
- Any other siege-web API surface (boards, assignments, notifications, auth
  flow, etc.).
- mom-bot's internal command or interaction structure.
