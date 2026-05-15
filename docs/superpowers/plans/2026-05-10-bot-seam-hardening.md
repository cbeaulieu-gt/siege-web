**Issue:** [#347](https://github.com/glitchwerks/rsl-siege-manager/issues/347)
**Status:** Approved 2026-05-10 (two adversarial inquisitor passes). Step 1 pending implementation as of 2026-05-15.

---

# Plan: Harden the siege-web ↔ `bot/` Seam; Enable Sidecar Replacement Without Public-Contract Ceremony

## Context

**Why this change.** The original mom-bot plan (`glitchwerks/mom-bot/docs/superpowers/plans/2026-05-08-mom-bot-framework.md`) called for *replacing* siege-web's bundled `bot/` with mom-bot at Epic 4 cutover. That framing has changed: mom-bot is evolving into a general-purpose clan management bot beyond siege-web's scope, and belongs in its own repo on its own release cadence. But siege-web should remain **easy to adopt** — Discord OAuth login, DMs, image posting, and slash-command-driven UX are core, so removing the bundled bot would force every adopter to either build their own bot or accept a Discord-less product, neither of which is viable.

**The intended outcome.** Keep `bot/` as siege-web's zero-config Discord sidecar. Harden the HTTP seam between backend and bot — already abstracted via `BotClient` and `DISCORD_BOT_API_URL` — so an alternate sidecar (mom-bot in the user's deployment, possibly others later) can be substituted by an operator without forking siege-web. **Do not** promote that seam to a "public versioned contract" — the ceremony of versioning + public surface is YAGNI for a single known second implementer.

This plan also resolves issues two adversarial review passes surfaced: existing wart enshrinement, an in-repo consumer of the path being renamed, the Discord-singleton-token constraint that was glossed in earlier framings, the bulk-vs-per-row webhook payload tradeoff (and its hidden out-of-order delivery hole), the prod-vs-local-dev enforcement gap, and the cost of inlining mom-bot-specific code into siege-web's day-assignment hot path.

## Process trail

This plan was rewritten twice after adversarial inquisitor reviews. Major decisions traceable to specific charges:

- **Pass 1 → drop "public contract" framing**: the seam was structurally Discord-bound; calling it generic was dishonest. Resolved by reframing as internal hardening + `bot/INTERFACE.md` documentation, no version locking.
- **Pass 1 → acknowledge Discord singleton-token mutual exclusion**: bundled `bot/` and any alternate sidecar with the same Discord token cannot coexist. Resolved at the architecture layer (Step 4, see below) rather than papered over.
- **Pass 2 → fix the false "no external consumers" claim**: `backend/app/api/version.py:44` is in fact a consumer of `/version`. Resolved by including the coordinated edit in Step 1 and dropping the deprecation-window paperwork.
- **Pass 2 → solve out-of-order webhook delivery**: per-row events with `(siege_id, member_id)` upsert have an ordering hole on rapid re-applies. Resolved by adding `applied_at` timestamp + receiver-discards-if-older contract (Step 6).
- **Pass 2 → make singleton-token enforcement actually enforce in prod**: docker-compose profiles only cover local dev; prod uses Container Apps via Bicep. Resolved with a Bicep parameter `useExternalSidecar` that excludes the bundled bot Container App when set (Step 4).
- **Pass 2 → keep mom-bot-specific code out of `apply_attack_day`'s hot path**: webhook firing migrated from inline-in-service to **outbox table + drainer worker** (Step 6).

## Goals

1. siege-web remains zero-config Discord-functional via the bundled `bot/`. **No new burden on adopters who don't replace it.**
2. The seam between `backend/` and `bot/` is documented at `bot/INTERFACE.md` so an alternate sidecar (mom-bot) can be implemented against it.
3. Black-box integration tests exercise the bundled bot's HTTP surface end-to-end (currently missing per Explore — both bot-side and backend-side test suites unit-test in isolation). **Tests are the normative source of truth; `INTERFACE.md` is the human-readable companion.**
4. Existing inconsistencies in the seam are cleaned up before being documented, with all in-repo consumers (notably `backend/app/api/version.py`) updated in lockstep.
5. Issues #322 and #323 are reframed and gated so non-mom-bot deployments are unaffected; reframing preserves the rationale via decision-log additions to the issue bodies.
6. Operators can swap to an alternate sidecar via a Bicep parameter (prod) and docker-compose profile (local dev), with the singleton-token mutual exclusion enforced — not just documented — at deploy time.
7. Mom-bot-specific outbound integration code (the day-assignment webhook in #323) lives outside `apply_attack_day`'s hot path so future refactors of core domain logic don't need to reason about it.

## Non-goals

- Public/versioned contract, v1 semver, plugin registry, runtime version-handshake endpoint.
- Making Discord truly optional / non-Discord auth.
- Splitting `bot/` into its own repo.
- Multi-process topology for the alternate sidecar (separate processes for API vs webhook receiver). v1 assumes one process implements whichever surfaces it claims to.
- "Reference implementation" framing — this is residue from the public-contract draft and is not used in this plan. The bundled bot is just the bundled bot.

## Approach

### Step 1: Clean up existing seam inconsistencies (with coordinated in-repo edits)

Fix the warts before documenting. All consumers in the repo are updated in the same PR.

| Wart | Fix | Coordinated in-repo edit |
|---|---|---|
| `/api/post-image` takes `channel_name` as a query param while siblings use JSON body | Move `channel_name` into the multipart form body alongside `file` | `backend/app/services/bot_client.py::post_image` updates accordingly |
| `/version` lives at root; everything else under `/api/` | Move to `/api/version`. **No alias, no deprecation window** — the only consumer is in this repo | `backend/app/api/version.py:44` updated in the same PR to call `/api/version` |
| `GET /api/members/{id}` returns either `{is_member: false}` or a full member shape with no documented discriminator | Always return the full key set with `is_member: bool` as the discriminator, nullable for non-members | `BotClient.get_member()` already tolerates both shapes; tighten its assertions |

### Step 2: Write `bot/INTERFACE.md`

Internal-facing doc, in `bot/` next to the implementation. Sections:

- **Purpose** — describes the HTTP surface `siege-web/backend/` calls on the Discord sidecar process. Names the seven endpoints. The bundled `bot/` is the in-tree implementation; alternate sidecars (mom-bot) implement against this surface.
- **Endpoint reference** — the seven endpoints (`/api/version`, `/api/health`, `/api/notify`, `/api/post-message`, `/api/post-image`, `/api/members/{id}`, `/api/members`) with method, path, request shape, response shape, auth (lifted verbatim from `bot/app/http_api.py` Pydantic models, post Step 1 cleanup).
- **Discord coupling** — explicit: returned URLs are Discord CDN URLs (lifetime/auth governed by Discord, not siege-web); `discord_id` strings are Discord snowflakes; channel/username lookups happen against a single guild identified by `DISCORD_GUILD_ID`.
- **Auth** — Bearer token via `DISCORD_BOT_API_KEY`, sidecar validates against its own `BOT_API_KEY`.
- **Singleton constraint** — explicit: bundled `bot/` and any alternate sidecar using the same Discord token cannot coexist. Operators replacing the sidecar must also exclude the bundled bot via the Bicep parameter (prod) or docker-compose profile (local dev).
- **Authority** — *"This document is human-readable documentation; the normative source of truth is the integration test suite at `backend/tests/integration/sidecar/`. When this document and the tests disagree, the tests win and this document gets updated."*
- **Maintenance** — INTERFACE.md is updated in the same PR as any change to the seam. #322 and #323 implementation PRs are expected to extend it; mom-bot's planned `/api/internal/role-sync` endpoint (Epic 2.6) similarly extends it when it lands.

### Step 3: Add black-box integration tests against the bundled bot

New module: `backend/tests/integration/sidecar/`

Pytest tests that exercise the live bundled-bot HTTP surface in the docker-compose stack. **Each success-path assertion checks both response status AND response body shape** — important because `BotClient` swallows `httpx.HTTPError` in five of six methods, so a regression to a 4xx becomes a `None` return at the call-site rather than an exception. Body-shape assertions catch this; status-only assertions don't.

Coverage:
- All seven endpoints respond with documented shapes (status + body)
- Auth: 401 on missing/wrong Bearer
- Negative paths: unknown channel name, unknown member, malformed payload — assert specific status codes and error body shape
- Singleton-bot health: `/api/health` returns `bot_connected: true` after startup

CI gets a new job that runs these against the docker-compose-bundled bot. Existing unit suites (`bot/tests/test_http_api.py`, `backend/tests/test_bot_client.py`) stay — they cover internals.

**Followup, not in this plan**: tightening `BotClient`'s exception swallowing so contract-shape failures distinguish from transient sidecar outages. File as a follow-up issue if Step 3's body-shape assertions prove insufficient at catching regressions.

### Step 4: Bicep + docker-compose enforce the Discord-singleton-token mutual exclusion

**Prod enforcement** (`infra/modules/container-apps.bicep`):

- Add parameter: `param useExternalSidecar bool = false`
- When `useExternalSidecar == true`, the bundled bot Container App resource is **not provisioned** (conditional `if (!useExternalSidecar)` on the resource block, or equivalent module-level conditional).
- The backend Container App's `DISCORD_BOT_API_URL` env var is set from a separate parameter so operators can point it at their alternate sidecar's URL.
- `infra-deploy.yml` workflow accepts the parameter via Bicep parameter file or workflow input.

**Local dev** (`docker-compose.yml`):

- Default profile: `backend`, `bot`, `frontend`, `postgres`.
- New profile `sidecar-external`: `backend`, `frontend`, `postgres` (bot excluded). Operator brings up their own sidecar separately.

**README** documents both: how to deploy with `useExternalSidecar=true` and how to run locally with `--profile sidecar-external`. Singleton-token constraint is stated explicitly in both contexts.

This is the honest version of mom-bot's Epic 4 Step 6 — not a project-wide decommission of the bundled bot, but an enforced deployment-time exclusion when an operator opts into an alternate sidecar.

### Step 5: Reframe #322 with decision-log entry

Edit issue body:

- Title: **"backend: extension-sidecar acting-user header + /me/preferences endpoints"**
- Body removes mom-bot-specific framing; describes `X-Acting-Discord-Id` as a generic mechanism for any sidecar driving interactive Discord commands.
- The endpoints land regardless — harmless for non-extension-sidecar deployments (the bundled bot has no slash-command UI to drive them; they sit unused).
- Acceptance criteria unchanged.
- **Append a `## Decision log (2026-05-10)` section** citing this plan and noting that the framing was reworked from mom-bot-specific to generic-extension-sidecar, with link to the umbrella issue.

### Step 6: Reframe #323 with per-row events + ordering signal + outbox-table architecture

Edit issue body:

- Title: **"backend: outbound event webhook for Day-Assignment changes (extension sidecar integration)"**
- Env var renamed: `MOM_BOT_BASE_URL` → `DISCORD_BOT_EVENT_WEBHOOK_URL` (matches existing `DISCORD_BOT_API_*` family). Webhook is a no-op when unset.
- **Payload shape: per-row events with ordering signal.**

  ```json
  {
    "siege_id": <int>,
    "member_id": <int>,
    "discord_id": <string>,
    "day_number": <1 | 2 | null>,
    "prev_day_number": <1 | 2 | null>,
    "applied_at": "<ISO-8601 UTC>",
    "apply_id": "<uuid>"
  }
  ```
- **Idempotency + ordering contract on receiver**:
  - Dedupe key: `(siege_id, member_id)`.
  - Receiver MUST track per-key `last_applied_at` and **discard events whose `applied_at` is earlier than the stored value** (out-of-order delivery is possible because of retries from the outbox drainer; see below).
  - `apply_id` shared across all rows fired by a single `apply_attack_day` call for correlation/logging — not the dedupe key.
- **Architecture: outbox table, not inline.**
  - New table `attack_day_event_outbox` (or similar): `id`, `siege_id`, `member_id`, `discord_id`, `day_number`, `prev_day_number`, `applied_at`, `apply_id`, `delivered_at`, `attempt_count`, `last_error`.
  - `apply_attack_day` and `attack_day_override` mutations write outbox rows **in the same DB transaction** as the `SiegeMember` updates. Atomic — no risk of "siege state changed but webhook never fired."
  - A drainer (in-process asyncio background task in the backend, polling every N seconds; document scaling path to a dedicated worker if volume warrants) reads undelivered rows, fires the webhook, marks `delivered_at` on success or increments `attempt_count`/`last_error` on failure with bounded retry.
  - At-least-once delivery: the receiver MUST be idempotent — which the `applied_at`-comparison contract above guarantees.
- **`apply_attack_day` itself stays clean**: it writes the outbox rows but knows nothing about webhooks, retries, or HTTP. Future refactors of attack-day logic don't have to reason about it.
- **Append `## Decision log (2026-05-10)` section** to the issue body citing this plan, the bulk-vs-per-row analysis, the out-of-order-delivery finding, and the outbox-table choice.

## Critical Files

**Will change in this plan's scope (Steps 1–4):**

- `bot/app/http_api.py` — wart cleanup
- `backend/app/services/bot_client.py` — match wart cleanup
- `backend/app/api/version.py` — coordinated path update for `/version` → `/api/version`
- `bot/INTERFACE.md` — **new** internal seam documentation
- `backend/tests/integration/sidecar/` — **new** black-box integration tests (with body-shape assertions per Step 3)
- `docker-compose.yml` — add `sidecar-external` profile
- `infra/modules/container-apps.bicep` — add `useExternalSidecar` parameter, conditional bundled-bot provisioning
- `infra-deploy.yml` workflow — accept the parameter
- `README.md` — document both deployment modes, singleton constraint, and the new INTERFACE.md
- `.github/workflows/ci.yml` — add integration-test job

**Edited but not implemented in this plan:**

- GitHub issue **#322** — reframe + append `## Decision log (2026-05-10)`
- GitHub issue **#323** — reframe + lock per-row payload + outbox architecture + append `## Decision log (2026-05-10)`
- `glitchwerks/mom-bot/docs/superpowers/plans/2026-05-08-mom-bot-framework.md` — separate PR in mom-bot repo:
  - Reframe Epic 4 Step 6 from "decommission old siege-bot" to "siege-web deployment-side: set `useExternalSidecar=true`."
  - Update the cutover sequence to reference the Bicep parameter rather than a manual decommission.
  - **Reconcile endpoint count**: mom-bot Epic 2 says "6 endpoints"; siege-web's INTERFACE.md says seven. `/version` (now `/api/version`) is part of the seam — mom-bot must implement it. Update Epic 2's count.

**Will NOT change in this plan:**

- `backend/app/dependencies/auth.py` — gets touched by #322's implementation, not this plan
- `backend/app/services/attack_day.py` — gets touched by #323's implementation; this plan only specifies the architecture (outbox writes + drainer), not the code changes themselves

## Reuse

- **`BotClient`** (`backend/app/services/bot_client.py`) — already centralizes all sidecar calls.
- **Existing Pydantic models in `bot/app/http_api.py`** — lifted into `INTERFACE.md` post-cleanup.
- **`bot/tests/test_http_api.py` (26 tests)** and **`backend/tests/test_bot_client.py` (9 tests)** — keep as-is.
- **Existing alembic migration tooling** — outbox table introduction is a standard `alembic revision --autogenerate` migration (per backend conventions in CLAUDE.md).
- **Existing `httpx.AsyncClient` patterns in `BotClient`** — reuse for the outbox drainer's outbound calls.
- **docker-compose profile mechanism** — standard Compose feature, no plumbing to invent.
- **Bicep conditional resources** — standard Bicep pattern (see `azure` skill / Microsoft docs for `if (...)` resource conditions).

## Verification

End-to-end test plan once Steps 1–4 land:

1. **Wart cleanup is consistent end-to-end**:
   ```powershell
   docker-compose up -d
   cd backend
   .\.venv\Scripts\python.exe -m pytest tests/test_bot_client.py tests/integration/sidecar/ tests/test_version.py -v
   ```
   Expected: all green. `BotClient.post_image()` sends `channel_name` in form body. `/api/version` (not `/version`) returns the version string. `backend/app/api/version.py` reaches the bot at the new path.

2. **Default-profile / non-`useExternalSidecar` deployment unchanged for adopters**:
   ```powershell
   docker-compose up
   ```
   Backend, frontend, bot all start. Login, board view, image generation, DM all work. No new env vars required.

3. **Sidecar-external profile excludes bundled bot locally**:
   ```powershell
   docker-compose --profile sidecar-external up
   ```
   Stack starts without bot container. Backend's `/api/health` reports unhealthy bot dependency until operator points `DISCORD_BOT_API_URL` at their alternate sidecar.

4. **`useExternalSidecar=true` Bicep deployment excludes bundled-bot Container App in prod**:
   ```powershell
   az deployment group what-if --resource-group siege-web-dev `
     --template-file infra/main.bicep `
     --parameters useExternalSidecar=true
   ```
   `what-if` output shows bundled-bot Container App resource as "not deployed." With `useExternalSidecar=false` (default), it deploys normally.

5. **Integration tests run in CI**: push a no-op PR; CI shows the new sidecar-integration job alongside existing backend / frontend / bot jobs. All green. Body-shape assertions are non-trivial (verify by deliberately breaking one shape on a throwaway branch and confirming the test fails).

6. **Singleton-token constraint enforced, not just documented**: `grep -rn "useExternalSidecar" infra/ README.md bot/INTERFACE.md` returns hits in all three.

7. **Outbox correctness** (specified here, implemented in #323):
   - `apply_attack_day` writes outbox rows in the same DB transaction as `SiegeMember` updates (verified by deliberately raising mid-write and confirming neither lands).
   - Drainer fires webhooks for undelivered rows, marks `delivered_at`.
   - Receiver discards out-of-order events: send two events for same `(siege_id, member_id)` with `applied_at` reversed; receiver applies the newer, ignores the older.

8. **Mom-bot plan amendment merged**: separate PR in `glitchwerks/mom-bot` updates Epic 4 Step 6 framing, fixes endpoint count to seven, references siege-web's `useExternalSidecar` parameter. Linked from this plan's umbrella issue.

## Issue tracking

Per CLAUDE.md (`# Issue Tracking`), implementation begins by filing an umbrella GitHub Issue in `glitchwerks/siege-web`:

- **Title**: *"design: harden the siege-web ↔ bot HTTP seam; document via bot/INTERFACE.md; enable enforced sidecar replacement via Bicep + compose profiles"*
- **Description**: links to this plan; lists Steps 1–4 as the implementation sequence; cross-references #322 and #323 as siblings whose implementation depends on Steps 5–6 reframing; references the mom-bot repo PR that amends Epic 4 Step 6.
- **Milestone**: assign or create at issue-filing time (likely v1.2 or a new "sidecar-hardening" milestone).
- **Labels**: `enhancement`, `backend`, `infrastructure`, `documentation`.

The umbrella issue is filed **after** this plan is approved (exit plan mode) and **before** any implementation work begins. Filing the issue is not authorization to start work; await explicit go.

## Open Questions

- **Outbox drainer scaling path**: the plan starts with an in-process asyncio drainer in the backend. If event volume grows or backend restart latency becomes a delivery-SLA concern, migrate to a dedicated worker process. **Not in scope for this plan**; flag as a follow-up if telemetry shows pressure.
- **`BotClient` exception-swallowing tightening**: Step 3's body-shape integration tests are the first-line defense against contract regressions appearing as silent `None` returns. If they prove insufficient over the first few months, file a follow-up issue to make `BotClient` distinguish 4xx contract failures from transient 5xx outages and surface them differently.
