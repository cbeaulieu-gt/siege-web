# Bot HTTP Sidecar — Interface Contract

This document is the human-readable contract between `backend/` and the Discord bot
sidecar (`bot/`). It is specific enough that an alternative sidecar implementation
(e.g. mom-bot, or an integration-test stub) can be built against it without reading
the bundled bot's source. Motivated by umbrella issue
[#347](https://github.com/glitchwerks/rsl-siege-manager/issues/347); sequencing and
broader context live in
`docs/superpowers/plans/2026-05-10-bot-seam-hardening.md`.

> **Authority.** This document is human-readable documentation. The normative source
> of truth is the integration test suite at
> `backend/tests/integration/sidecar/`. When this document and the tests disagree,
> the tests win and this document gets updated.

---

## Process model

`SiegeBot` (discord.py client) and the FastAPI HTTP sidecar run concurrently in the
same process via `asyncio.TaskGroup` (`bot/app/main.py:43-45`). The HTTP server
listens on `0.0.0.0:8001` (uvicorn). Backend communicates with the sidecar exclusively
over HTTP — it never imports or calls discord.py directly.

---

## Authentication

Every endpoint except `GET /api/version` and `GET /api/health` requires an HTTP
`Authorization` header carrying a Bearer token.

```
Authorization: Bearer <token>
```

| Side | Environment variable | Notes |
|---|---|---|
| Backend (caller) | `DISCORD_BOT_API_KEY` | Sent as the Bearer token |
| Bot sidecar (validator) | `BOT_API_KEY` | Compared using `secrets.compare_digest` |

The bundled sidecar uses `HTTPBearer(auto_error=True)` (FastAPI/Starlette default).
This produces **two distinct failure modes**:

**403 Forbidden — `Authorization` header absent entirely.**

```http
HTTP/1.1 403 Forbidden

{"detail": "Not authenticated"}
```

No `WWW-Authenticate` header is returned. This is the FastAPI `HTTPBearer` default
when no header is present (`bot/app/http_api.py:17`).

**401 Unauthorized — header present but scheme is not `Bearer`, or token is wrong.**

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer

{"detail": "Invalid API key"}
```

The `WWW-Authenticate: Bearer` header is set by `verify_api_key`
(`bot/app/http_api.py:36-43`), which only runs when the header is present.

> **Conformance note.** Alternative sidecars MUST return 401 on a wrong token and
> MAY return either 401 or 403 on a missing header. The backend's `BotClient` does
> not inspect the specific auth-failure code — it treats any 4xx as an auth failure.

Source: `bot/app/http_api.py:17`, `bot/app/http_api.py:36-43`

---

## Discord coupling

The sidecar operates against a single Discord guild identified by the `DISCORD_GUILD_ID`
environment variable. Callers should be aware of the following coupling:

- `discord_id` values are Discord snowflake strings (e.g. `"123456789012345678"`).
- `channel_name` and `username` are resolved within the configured guild only.
- Image CDN URLs returned by `POST /api/post-image` are Discord CDN URLs; their
  lifetime and access policy are governed by Discord, not siege-web.
- The bundled `bot/` and any alternate sidecar sharing the same Discord token cannot
  coexist. An operator replacing the sidecar must exclude the bundled bot via the
  `useExternalSidecar` Bicep parameter (prod) or the `sidecar-external` docker-compose
  profile (local dev). See Step 4 of #347 for enforcement details.

---

## Error semantics

The sidecar produces two distinct error body shapes depending on where the error originates.

**Handler-raised errors (401, 403, 404, 503).** These are raised explicitly by route
handlers or FastAPI dependencies via `HTTPException`. The body is:

```json
{"detail": "<human-readable string>"}
```

Example:

```json
{"detail": "Member 'SomeMember' not found in guild"}
```

**Framework-raised validation errors (422).** When a request body or form field is
missing, the wrong type, or malformed JSON/form data, FastAPI's request-validation layer
raises `RequestValidationError` before the handler runs. The body is a **list of
objects**, not a string:

```json
{
  "detail": [
    {
      "loc": ["body", "username"],
      "msg": "field required",
      "type": "missing"
    }
  ]
}
```

Each element in the `detail` array has three keys: `loc` (path to the invalid field),
`msg` (human-readable description), and `type` (machine-readable error code).

Consumers that parse error bodies MUST handle both shapes. The status code is the
reliable discriminator: 422 always uses the list shape; 401/403/404/503 always use
the string shape.

| Status | Common trigger | Backend (`BotClient`) behaviour |
|---|---|---|
| 401 | Wrong or malformed Bearer token | `httpx.HTTPStatusError` propagates; most methods return `False` or `[]`; `get_member` re-raises |
| 403 | `Authorization` header absent | Same as 401 |
| 404 | Channel or member not found in guild (see per-endpoint notes) | Same as 401 |
| 422 | Missing required field, wrong type, malformed JSON or form data | Same as 401 |
| 503 | Bot not connected (`is_ready()` false), guild unavailable, Discord API error | Same as 401 |

`BotClient` swallows `httpx.HTTPError` in `notify`, `post_message`, `post_image`, and
`get_members`, returning `False`, `False`, `None`, and `[]` respectively on any HTTP
error. `get_member` does **not** swallow — it propagates `httpx.HTTPError` and raises
`AssertionError` if the response body violates the discriminated shape. Callers must
distinguish between a `None`/`False` return (transient sidecar failure) and a missing
`url` key (contract violation) when consuming `post_image`.

---

## Endpoint reference

### `GET /api/version`

Returns the sidecar version string. No authentication required.

**Request.** No parameters.

**Response — 200 OK.**

```json
{"version": "1.0.1+42.abc1234"}
```

The value is `<semver>+<BUILD_NUMBER>.<GIT_SHA[:7]>` when both `BUILD_NUMBER` and
`GIT_SHA` environment variables are present (CI-built images), or bare semver in
local development. Semver is read from `bot/VERSION` at startup; falls back to
`"unknown"` if the file is missing.

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Always (file missing returns `{"version": "unknown"}`) |

Source: `bot/app/http_api.py:56-73`

---

### `GET /api/health`

Health probe. No authentication required.

**Request.** No parameters.

**Response — 200 OK.**

```json
{"status": "healthy", "bot_connected": true}
```

`bot_connected` is `true` when the discord.py client is connected and ready;
`false` otherwise (during startup or after a disconnect).

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Always |

Source: `bot/app/http_api.py:76-79`

---

### `POST /api/notify`

Send a direct message (DM) to a guild member by username. Requires authentication.

**Request body — JSON.**

```json
{"username": "SomeMember", "message": "Your siege assignment is ready."}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `username` | `string` | yes | Discord username of the target member (not display name) |
| `message` | `string` | yes | DM content |

**Response — 200 OK.**

```json
{"status": "sent"}
```

**Status codes.**

| Code | Condition |
|---|---|
| 200 | DM delivered successfully |
| 401 | Wrong or malformed Bearer token |
| 403 | `Authorization` header absent |
| 404 | See below |
| 422 | Missing required field, wrong type, or malformed JSON |
| 503 | Bot is not connected to Discord |

**404 causes.** The bundled sidecar raises 404 for any `ValueError` from `bot.send_dm`
(`bot/app/http_api.py:91-92`). The only `ValueError` that `send_dm` raises is:

- **Username not found in guild cache.** The member's `name` (exact, case-insensitive)
  does not match any member in the locally cached guild member list
  (`bot/app/discord_client.py:25-29`).

There is exactly one 404 cause. Delivery failures after the member is found (e.g.
the member has DMs closed or blocked) are not caught at the sidecar layer — they
surface as unhandled discord.py exceptions producing a 500, not a 404. The consumer
cannot distinguish "member found, DM blocked" from other 5xx conditions via status
code alone.

Source: `bot/app/http_api.py:82-93`, `bot/app/discord_client.py:22-31`

---

### `POST /api/post-message`

Post a text message to a guild channel by name. Requires authentication.

**Request body — JSON.**

```json
{"channel_name": "siege-assignments", "message": "Day 1 roster is locked."}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `channel_name` | `string` | yes | Discord channel name (exact match, without `#`) |
| `message` | `string` | yes | Message content |

**Response — 200 OK.**

```json
{"status": "sent"}
```

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Message posted successfully |
| 401 | Wrong or malformed Bearer token |
| 403 | `Authorization` header absent |
| 404 | See below |
| 422 | Missing required field, wrong type, or malformed JSON |
| 503 | Bot is not connected to Discord |

**404 causes.** The bundled sidecar raises 404 for any `ValueError` from `bot.post_message`
(`bot/app/http_api.py:105-106`). The only `ValueError` that `post_message` raises is:

- **Channel not found by name.** No `TextChannel` in the guild's channel list has a
  name exactly matching `channel_name` (`bot/app/discord_client.py:36-41`).

**Channel-resolution failures collapse to 404.** A channel that exists but for which
the bot lacks send permission does not match the name-lookup path — the 404 fires on
name resolution, before any send attempt. A permission error on `channel.send()` would
be an unhandled discord.py exception (500), not a 404. Consumers cannot distinguish
"channel name not in guild" from other resolution failures via status code alone.
Alternative sidecars MUST also collapse all channel-resolution-class failures to 404
and MUST NOT split them into separate 403/404 codes.

Source: `bot/app/http_api.py:96-107`, `bot/app/discord_client.py:33-42`

---

### `POST /api/post-image`

Upload an image and post it to a guild channel. Returns the Discord CDN URL of the
posted attachment. Requires authentication.

**Request body — `multipart/form-data`.** The `channel_name` field and the `file`
field must both be sent as multipart form parts in the same request body. `channel_name`
is a `Form(...)` field — it is **not** a query parameter.

| Part | Type | Required | Description |
|---|---|---|---|
| `file` | binary (UploadFile) | yes | PNG image bytes; filename defaults to `image.png` if not provided |
| `channel_name` | `string` | yes | Discord channel name to post into |

Example using `httpx`:

```python
client.post(
    "/api/post-image",
    data={"channel_name": "siege-images"},
    files={"file": ("assignment.png", image_bytes, "image/png")},
)
```

**Response — 200 OK.**

```json
{"status": "sent", "url": "https://cdn.discordapp.com/attachments/.../assignment.png"}
```

| Field | Type | Description |
|---|---|---|
| `status` | `string` | Always `"sent"` |
| `url` | `string` | Discord CDN URL of the uploaded attachment |

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Image posted; `url` is the Discord CDN link |
| 401 | Wrong or malformed Bearer token |
| 403 | `Authorization` header absent |
| 404 | See below |
| 422 | Missing `channel_name` form field, missing `file` part, or malformed multipart data |
| 503 | Bot is not connected to Discord |

**404 causes.** The bundled sidecar raises 404 for any `ValueError` from `bot.post_image`
(`bot/app/http_api.py:121-122`). The only `ValueError` that `post_image` raises is:

- **Channel not found by name.** No `TextChannel` in the guild's channel list has a
  name exactly matching `channel_name` (`bot/app/discord_client.py:52-57`).

The same collapse rule applies as for `POST /api/post-message`: all channel-resolution-class
failures (name not found, and any other pre-send resolution failure) collapse to 404.
Alternative sidecars MUST conform to this collapse; consumers cannot distinguish channel
absence from other resolution failures via status code alone.

Source: `bot/app/http_api.py:110-123`, `bot/app/discord_client.py:44-59`

---

### `GET /api/members`

Retrieve the full guild member list. Requires authentication.

**Request.** No parameters.

**Response — 200 OK.**

A JSON array. Each element has exactly three keys as returned by `SiegeBot.get_members()`
(`bot/app/discord_client.py:61-71`):

```json
[
  {
    "id": "123456789012345678",
    "username": "SomeMember",
    "display_name": "Some Member"
  }
]
```

**Element shape.**

| Key | Type | Description |
|---|---|---|
| `id` | `string` | Discord snowflake ID (numeric string) |
| `username` | `string` | Discord username (`member.name`) |
| `display_name` | `string` | Guild display name (`member.display_name`) |

All three keys are always present for every element. The array may be empty if the
guild has no cached members. Roles are not included in this endpoint's response — use
`GET /api/members/{discord_user_id}` for role data.

> **Note.** The key for the Discord ID in this response is `id`, not `discord_id`.
> The `GET /api/members/{discord_user_id}` endpoint uses `discord_id`. Alternative
> sidecars MUST use `id` here to match the bundled implementation.

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Member list returned (may be empty) |
| 401 | Wrong or malformed Bearer token |
| 403 | `Authorization` header absent |
| 503 | Bot is not connected to Discord |

Source: `bot/app/http_api.py:126-132`, `bot/app/discord_client.py:61-71`

---

### `GET /api/members/{discord_user_id}`

Look up a single guild member by Discord user ID. Requires authentication.

**Path parameter.**

| Parameter | Type | Description |
|---|---|---|
| `discord_user_id` | `string` | Discord snowflake ID (numeric string, e.g. `"123456789012345678"`) |

**Response — 200 OK (member found).**

```json
{
  "is_member": true,
  "discord_id": "123456789012345678",
  "username": "SomeMember",
  "display_name": "Some Member",
  "roles": ["987654321098765432"],
  "role_names": ["Clan Deputies"]
}
```

**Response — 200 OK (not a guild member).**

```json
{
  "is_member": false,
  "discord_id": null,
  "username": null,
  "display_name": null,
  "roles": null,
  "role_names": null
}
```

The `is_member: bool` field is the discriminator. All six keys are always present
regardless of membership status. When `is_member` is `false`, the remaining five
fields are `null`. The `@everyone` role is excluded from `roles` and `role_names`.

**Required key set** (asserted by `BotClient.get_member` — `backend/app/services/bot_client.py:120-131`):

| Key | Type when member | Type when not member |
|---|---|---|
| `is_member` | `bool` (`true`) | `bool` (`false`) |
| `discord_id` | `string` | `null` |
| `username` | `string` | `null` |
| `display_name` | `string` | `null` |
| `roles` | `string[]` | `null` |
| `role_names` | `string[]` | `null` |

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Always when the Discord API responds (including "not a member") |
| 401 | Wrong or malformed Bearer token |
| 403 | `Authorization` header absent |
| 503 | Bot is not connected, guild is unavailable, or Discord API returns an unexpected error |

Source: `bot/app/http_api.py:135-172`

---

## Replaceability requirements

An alternative sidecar conforming to this contract MUST satisfy every row in the
following conformance table. Each row names a concrete stimulus and the expected
observable response. A conformance test can implement this table mechanically.

### `GET /api/version`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| `GET /api/version` (no auth header) | 200 | `{"version": "<non-empty string>"}` | — |

### `GET /api/health`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| `GET /api/health` (no auth header) | 200 | `{"status": "healthy", "bot_connected": <bool>}` | — |

### Authentication (all protected endpoints)

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| Valid-path request, `Authorization` header absent | 401 or 403 | `{"detail": "<string>"}` | — |
| Valid-path request, header present with wrong token | 401 | `{"detail": "<string>"}` | `WWW-Authenticate: Bearer` |

### `POST /api/notify`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| Valid auth, body `{"username": "<existing-member>", "message": "x"}` | 200 | `{"status": "sent"}` | — |
| Valid auth, body `{"username": "<non-member>", "message": "x"}` | 404 | `{"detail": "<string>"}` | — |
| Valid auth, body missing `username` field | 422 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | — |
| Valid auth, body missing `message` field | 422 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | — |
| Valid auth, bot not connected | 503 | `{"detail": "<string>"}` | — |

### `POST /api/post-message`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| Valid auth, body `{"channel_name": "<existing-channel>", "message": "x"}` | 200 | `{"status": "sent"}` | — |
| Valid auth, body `{"channel_name": "<non-existent-channel>", "message": "x"}` | 404 | `{"detail": "<string>"}` | — |
| Valid auth, body missing `channel_name` field | 422 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | — |
| Valid auth, bot not connected | 503 | `{"detail": "<string>"}` | — |

### `POST /api/post-image`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| Valid auth, valid multipart (`channel_name` + PNG file), existing channel | 200 | `{"status": "sent", "url": "<non-empty string>"}` | — |
| Valid auth, valid multipart, non-existent `channel_name` | 404 | `{"detail": "<string>"}` | — |
| Valid auth, `channel_name` form field missing | 422 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | — |
| Valid auth, `channel_name` sent as query parameter instead of form field | 422 | `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` | — |
| Valid auth, bot not connected | 503 | `{"detail": "<string>"}` | — |

### `GET /api/members`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| Valid auth, bot connected | 200 | JSON array; each element has `id` (string), `username` (string), `display_name` (string) | — |
| Valid auth, bot not connected | 503 | `{"detail": "<string>"}` | — |

### `GET /api/members/{discord_user_id}`

| Stimulus | Expected status | Expected body | Expected headers |
|---|---|---|---|
| Valid auth, ID of guild member | 200 | All six keys present; `is_member: true`; non-null string fields | — |
| Valid auth, ID of non-member (or unknown ID) | 200 | All six keys present; `is_member: false`; remaining five keys `null` | — |
| Valid auth, bot not connected or guild unavailable | 503 | `{"detail": "<string>"}` | — |

**Additional shape constraints (all member endpoints):**

- `GET /api/members` element key for Discord ID is `id`, not `discord_id`.
- `GET /api/members/{discord_user_id}` key for Discord ID is `discord_id`.
- `@everyone` role is excluded from `roles` and `role_names` in all member responses.
- `POST /api/post-image` response `url` field must be a non-empty string on 200.
- All six keys (`is_member`, `discord_id`, `username`, `display_name`, `roles`,
  `role_names`) must be present in every `GET /api/members/{discord_user_id}` response,
  regardless of membership status.

---

## Versioning

The `/api/version` endpoint returns a version string for observability. There is no
runtime version handshake — the backend does not check this value before calling other
endpoints. The string is informational only.

**Breaking vs. additive changes.**

| Change | Classification |
|---|---|
| Adding a key to a response body | Additive — safe |
| Removing or renaming a key | Breaking — update doc, tests, and `BotClient` in the same PR |
| Changing a path, method, or status code | Breaking — same |
| Changing `channel_name` from form field back to query param | Breaking |
| Changing `is_member` semantics or key set | Breaking |

Per Step 2 of #347: `INTERFACE.md` is updated in the same PR as any change to the
seam. No deprecation window is provided for breaking changes because the only consumers
are within this repository and the interface is internal (not public/versioned).

---

## Cross-references

- **Plan:** `docs/superpowers/plans/2026-05-10-bot-seam-hardening.md`
- **Umbrella issue:** [#347](https://github.com/glitchwerks/rsl-siege-manager/issues/347)
- **Step 1 cleanup PR:** [#415](https://github.com/glitchwerks/rsl-siege-manager/pull/415)
  — moved `/version` → `/api/version`, moved `channel_name` to multipart form body,
  added `is_member` discriminator with full nullable key set
- **Step 3:** `backend/tests/integration/sidecar/` (integration tests, normative source
  of truth for this contract)
- **Backend consumer:** `backend/app/services/bot_client.py`
- **Sidecar implementation:** `bot/app/http_api.py`, `bot/app/discord_client.py`
