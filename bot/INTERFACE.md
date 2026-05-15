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

**Failure mode.** A missing, malformed, or incorrect token returns:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer

{"detail": "Invalid API key"}
```

Source: `bot/app/http_api.py:36-43`

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
| 401 | Missing or invalid Bearer token |
| 404 | Member not found in guild |
| 503 | Bot is not connected to Discord |

Source: `bot/app/http_api.py:82-93`

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
| 401 | Missing or invalid Bearer token |
| 404 | Channel not found in guild |
| 503 | Bot is not connected to Discord |

Source: `bot/app/http_api.py:96-107`

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
| 401 | Missing or invalid Bearer token |
| 404 | Channel not found in guild |
| 503 | Bot is not connected to Discord |

Source: `bot/app/http_api.py:110-123`

---

### `GET /api/members`

Retrieve the full guild member list. Requires authentication.

**Request.** No parameters.

**Response — 200 OK.**

A JSON array. Each element's shape is unverified beyond being a `dict` — the backend
consumer (`BotClient.get_members`) returns the raw array without asserting on individual
element keys. The integration tests in Step 3 of #347 will pin the exact shape.

```json
[
  {
    "discord_id": "123456789012345678",
    "username": "SomeMember",
    "display_name": "Some Member",
    "roles": ["987654321098765432"],
    "role_names": ["Clan Deputies"]
  }
]
```

**Status codes.**

| Code | Condition |
|---|---|
| 200 | Member list returned (may be empty) |
| 401 | Missing or invalid Bearer token |
| 503 | Bot is not connected to Discord |

Source: `bot/app/http_api.py:126-132`

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
| 401 | Missing or invalid Bearer token |
| 503 | Bot is not connected, guild is unavailable, or Discord API returns an unexpected error |

Source: `bot/app/http_api.py:135-172`

---

## Error semantics

Unless noted per-endpoint, error response bodies follow the FastAPI default shape:

```json
{"detail": "<human-readable message>"}
```

| Status | Common trigger | Backend (`BotClient`) behaviour |
|---|---|---|
| 401 | Missing or invalid Bearer token | `httpx.HTTPStatusError` propagates; most methods return `False` or `[]`; `get_member` re-raises |
| 404 | Channel or member not found in guild | Same as 401 |
| 503 | Bot not connected (`is_ready()` false), guild unavailable, Discord API error | Same as 401 |

`BotClient` swallows `httpx.HTTPError` in `notify`, `post_message`, `post_image`, and
`get_members`, returning `False`, `False`, `None`, and `[]` respectively on any HTTP
error. `get_member` does **not** swallow — it propagates `httpx.HTTPError` and raises
`AssertionError` if the response body violates the discriminated shape. Callers must
distinguish between a `None`/`False` return (transient sidecar failure) and a missing
`url` key (contract violation) when consuming `post_image`.

---

## Replaceability requirements

An alternative sidecar conforming to this contract MUST:

- Expose all seven endpoints at the exact paths documented above, on port 8001 (or
  whatever `DISCORD_BOT_API_URL` is set to in the backend environment).
- Require `Authorization: Bearer <BOT_API_KEY>` on all endpoints except
  `GET /api/version` and `GET /api/health`.
- Return `401` (with `WWW-Authenticate: Bearer`) on missing or invalid tokens.
- Return `503` when the underlying Discord connection is unavailable.
- Return `404` when a named channel or member cannot be resolved.
- Return `{"status": "sent", "url": "<string>"}` from `POST /api/post-image` with a
  non-empty `url` field on success.
- Return all six keys (`is_member`, `discord_id`, `username`, `display_name`, `roles`,
  `role_names`) from `GET /api/members/{discord_user_id}`, with `is_member` as a
  boolean discriminator and the remaining five fields `null` when `is_member` is
  `false`.
- Accept `POST /api/post-image` with `channel_name` as a `multipart/form-data` field
  alongside the `file` upload — not as a query parameter.
- Exclude the `@everyone` role from `roles` and `role_names` in member responses.
- Not share the same Discord token as the bundled `bot/` when both processes would
  otherwise be running simultaneously (singleton-token constraint).

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
- **Sidecar implementation:** `bot/app/http_api.py`
