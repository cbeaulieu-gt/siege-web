# Demo Mode — Sandboxed Per-Session Demo Sieges (Option A+, Revision 2)

## Context

**Why this is being built — adoption.** Today the app is gated behind Discord OAuth + the `Clan Deputies` role, so a prospective clan deputy evaluating the tool cannot feel the actual workflow without being granted access by an existing user. That friction kills the top-of-funnel. A real demo mode lets a curious visitor land on `/demo`, get dropped into a sandboxed, pre-seeded clan with full read+write capabilities, and experience the product end-to-end without touching real data or Discord side-effects.

**Why Option A+ over multi-tenancy primitives.** A previous draft (Option C) introduced a `Tenant` abstraction on the theory that the primitives would be reusable for future multi-tenancy. Inquisitor pass 1 found that 5 of 12 charges existed *only because of* the Tenant abstraction. With "no immediate plans for real multi-tenancy" being the user's stated forecast, the upfront tax was the wrong trade. Option A+ uses simple per-table demo flags + a triple-layer discipline mechanism that prevents the workaround trap. § Migration-to-Tenancy Appendix documents the upgrade path if multi-tenancy demand ever arises.

**Pass-2 corrections.** Inquisitor pass 2 found 15 further charges against the Option A+ draft — most importantly that the plan's enumeration of demo/real boundary sites was wrong (write endpoints span 12+ router files, not 4) and that a read endpoint (`compare`) silently fetches a second siege not named in the URL. This revision (R2) addresses all 15 with explicit per-route discipline, a Phase 0 enumeration task, and operational corrections (Redis-backed cap, Container Apps Job janitor, JWT cross-check, namespaced demo Members, read-only Member fields in demo).

**Constraints set by the user:**
- **Shape**: sandboxed read+write demo sandbox.
- **Audience**: primarily prospective deputies; acceptable for public showcase.
- **Discord scope**: UI-only. Bot calls mocked. Image generation OK; image posting suppressed.
- **Discipline**: triple-layer enforcement bounds where `is_demo` may appear.
- **Member semantics**: read-only in demo (chosen to avoid cross-session interference on shared rows).
- **Infrastructure**: Redis-backed concurrency cap + Container Apps Job janitor (chosen for correctness under multi-replica + the user's stated interest in Redis exposure).

**Non-goals:**
- Real multi-tenancy.
- Separate public marketing site.
- Onboarding tour engine.
- Demo users mutating Member rows.

---

## The Bounded `is_demo` Surface

`is_demo` (and its siblings `demo_session_id`, `is_demo_only`) may appear ONLY in these EIGHT sites (one added in R2):

1. **Schema columns** — `Siege.is_demo`, `Siege.demo_session_id`, `Siege.last_active_at`; `Member.is_demo_only`; `NotificationBatch.is_demo`.
2. **Auth dependency** — `AuthenticatedUser.is_demo`, `AuthenticatedUser.demo_session_id`.
3. **Demo-login endpoint and fork service** — `POST /api/auth/demo-login` and `app/services/demo_fork.py`.
4. **Write-scope guard dependency** — `app/dependencies/scope.py:require_demo_scope` AND `app/dependencies/scope.py:require_real_user` (the latter for routes where demo users are blanket-denied — see § Phase 0).
5. **List-endpoint and service-layer filters** — the small enumerated set of routes/services that cross the boundary. Concretely: `GET /api/sieges`, `GET /api/members`, the Discord-sync preview's Member match set, and `comparison_service.get_most_recent_completed`. Phase 0 produces the verified complete list.
6. **Bot client short-circuit wrapper** — the per-request gate reading `_current_user` ContextVar.
7. **Frontend demo UI** — `DemoLandingPage`, `DemoBanner`, `SimulatedAction`, the `useAuth().isDemo` flag, the 401-interceptor demo branch (which decodes the JWT from the cookie, NOT cached AuthContext state).
8. **Operational utilities** — janitor (Container Apps Job), rate limiter / cap middleware (Redis-backed), the CI grep script.

Plus the `docs/demo-boundary.md` reference doc itself. Outside these eight sites: `is_demo` is forbidden.

---

## Design Summary

### Schema (one migration: `0012_add_demo_flags`)

- `Siege.is_demo: bool NOT NULL DEFAULT False`
- `Siege.demo_session_id: UUID NULL UNIQUE`
- `Siege.last_active_at: timestamptz NULL`
- `Member.is_demo_only: bool NOT NULL DEFAULT False`
- `NotificationBatch.is_demo: bool NOT NULL DEFAULT False`
- **Data step (idempotent, per-table natural key)**:
  - 28 demo members with namespaced names `[DEMO] <Name>` (e.g. `[DEMO] Alice`, `[DEMO] Bob`): `INSERT ... ON CONFLICT (name) DO NOTHING` — `Member.name` is the existing global UNIQUE.
  - `BuildingTypeConfig`: `INSERT ... ON CONFLICT (building_type) DO NOTHING` — natural key is the enum-valued `building_type` column.
  - `PostCondition`: `INSERT ... ON CONFLICT (description) DO NOTHING` — `description` is UNIQUE per the existing schema.
  - `PostPriorityConfig`: `INSERT ... ON CONFLICT (post_number) DO NOTHING` — `post_number` is the natural key (1-18).
  - Phase 0 verifies the natural-key columns above by reading the model files; if any has changed since this plan was written, the migration uses the actual UNIQUE column.
  - **The migration now seeds reference data**, removing the manual-script dependency.
- **Reserved-prefix enforcement on real-user writes (resolves Charge NEW-3)**: a service-layer validator in `app/api/members.py` rejects `POST /api/members` and `PUT /api/members/{id}` where the resulting `name` matches `^\[DEMO\] `. Returns 400 with `{"error": "reserved_prefix", "detail": "Member names cannot begin with '[DEMO] ' — that prefix is reserved for demo-mode seed data."}`. Without this guard the namespacing is decorative — a real deputy could create `[DEMO] Alice`, the seed migration's `ON CONFLICT DO NOTHING` would silently skip the demo seed, and demo users would gain visibility into a real Member row.
- Frontend rendering needs auditing to confirm `[DEMO] ` prefix doesn't break image-gen / autofill layout (Phase 0d).

### Member semantics in demo

**Demo users have read-only access to the Member roster.** They CAN see the 28 `[DEMO]` members; they CANNOT mutate Member metadata (rename, change power_level, deactivate, sync Discord identity). All `POST /api/members`, `PUT /api/members/{id}`, `DELETE /api/members/{id}`, `PUT /api/members/{id}/preferences`, and Discord-sync endpoints return 403 for demo users (enforced by `require_real_user` dependency — see Phase 0).

Demo users CAN assign members to positions, run autofill, validate, generate images — the actual workflow. This is the deliberate trade for avoiding cross-session interference on shared Member rows.

### Auth dependency

```python
@dataclass
class AuthenticatedUser:
    member_id: int | None
    name: str
    is_service: bool
    role: str | None = None
    discord_id: str | None = None
    is_demo: bool = False              # NEW
    demo_session_id: str | None = None # NEW
```

Defaults preserve existing call sites (`AUTH_DISABLED` stub, bot-service-token branch, real-user JWT) unchanged.

**JWT decode: mutual-exclusivity cross-check** (resolves Charge 8). At decode time:

```python
payload = jwt.decode(token, settings.session_secret, algorithms=[JWT_ALGORITHM])
is_demo_claim = payload.get("is_demo", False)
has_sub = payload.get("sub") is not None
has_dsid = payload.get("demo_session_id") is not None

if is_demo_claim and (has_sub or not has_dsid):
    log.warning("auth.malformed_jwt", reason="demo_claim_with_sub_or_missing_dsid")
    raise HTTPException(401)
if not is_demo_claim and has_dsid:
    log.warning("auth.malformed_jwt", reason="non_demo_with_dsid")
    raise HTTPException(401)
```

Mismatched claims are 401 + logged security events. Prevents a future copy-paste bug in `auth.py` from silently issuing a real-user JWT that escalates into the demo branch.

**Demo JWT shape**: `{is_demo: true, demo_session_id: "<uuid>", exp: now + 5h}`. No `sub`. 5h = 4h idle window + 1h grace. Aligned with the siege's idle-reap window so JWT credential exposure does not exceed effective session lifetime. Real-user JWT shape: `{sub: "<member_id>", name: "...", iat, exp}`. No `is_demo`, no `demo_session_id`.

### Demo login & fork

`POST /api/auth/demo-login`. Structure is **slot-acquire-then-try-finally-wrapped-transaction** so the Redis slot is always released on any failure path (resolves pass-3 Charge 5 hand-waviness):

```python
async def demo_login(redis: Redis, db: AsyncSession):
    acquired = await acquire_demo_slot(redis)
    if not acquired:
        raise HTTPException(503, {"error": "demo_at_capacity", "retry_after": 60})
    # Explicit Postgres-side timeout: 9s = 1s before asyncio's 10s, giving
    # asyncio the chance to cancel cleanly. Without this, a network-stalled
    # Postgres call could survive past asyncio's signal.
    await db.execute(text("SET LOCAL statement_timeout = '9s'"))
    try:
        async with asyncio.timeout(10.0):
            async with db.begin():  # async transaction; rollback on exception
                demo_session_id = uuid4()
                siege = Siege(is_demo=True, demo_session_id=demo_session_id, last_active_at=now(), status="planning")
                db.add(siege)
                await db.flush()
                await siege_layout.populate(db, siege, is_demo=True)  # buildings/groups/positions
                await siege_layout.attach_demo_members(db, siege)     # 28 SiegeMember rows, round-robin attack_day
            token = _issue_demo_jwt(demo_session_id)
            return {"redirect": "/", "_set_cookie": token}
    except (asyncio.TimeoutError, asyncpg.PostgresError) as exc:
        await release_demo_slot(redis)
        raise HTTPException(503, {"error": "demo_fork_timeout", "retry_after": 5}) from exc
    except Exception:
        await release_demo_slot(redis)
        raise
    # Success path: slot stays acquired; janitor releases it when siege is reaped.
```

Notes on the structure:
- The slot is acquired **before** the transaction so concurrent in-flight forks cannot all pass the cap check.
- The transaction is inside the `asyncio.timeout` (Python 3.11+ idiom; equivalent to `asyncio.wait_for`) so cancellation rolls back via `db.begin()`'s context manager.
- Slot is released on every failure path explicitly. Success path holds the slot until janitor reaping decrements it (the natural session-lifetime tie).
- `release_demo_slot` swallows Redis errors (logs and continues) — the 6h reconcile job is the backstop.
- Postgres `statement_timeout = '9s'` set via `SET LOCAL` before the transaction, 1 second before asyncio's 10s timeout — gives asyncio the chance to cancel cleanly before Postgres times out. Defense in depth against asyncio signal delays on network-stalled DB calls.
- **Resolves Charge 14**: autofill operates on `siege.siege_members` which is now populated by `attach_demo_members`.

**Timeout failure (Charge 12)**: `asyncio.wait_for` triggers `CancelledError` → SQLAlchemy async session's `__aexit__` rolls back. Postgres `statement_timeout` is the backstop if asyncio's signal is delayed. User sees 503 with `{"error": "demo_fork_timeout", "retry_after": 5}` and a frontend toast "Demo couldn't start; try again in a moment." **Timeout failures DO NOT count against the rate limit** — Redis-backed limiter has a rollback hook on this specific error.

**Cascade deletes (Charge — verified during plan write)**: confirm `Siege.buildings` relationship has `cascade="all, delete-orphan"` and `Building.groups` likewise. Audit during Phase 0; fix if missing.

### Reaping & lifetime

- Each demo request updates `siege.last_active_at` via a middleware that runs after auth, before route handlers. One `UPDATE` per request.
- **Janitor → Container Apps Job** running on a cron schedule (every 30 min). Single deployment-wide instance — no parallel-DELETE races. Bicep module at `infra/modules/demo-janitor-job.bicep` follows the existing container-apps patterns. Image is the backend image; entrypoint is `python -m app.jobs.demo_janitor`.
- Janitor SQL: `DELETE FROM siege WHERE is_demo=True AND last_active_at < now() - interval '4 hours'`. Cascade handles buildings/groups/positions/notification_batches.
- **JWT vs reap reconciliation (Charge 6 pass 1 / Charge 7 pass 2)**: when a demo siege is reaped, any outstanding JWT pointing at its `demo_session_id` becomes unusable — the auth dependency's siege-lookup-by-`demo_session_id` returns nothing → raise 401. The frontend interceptor **decodes the JWT from `document.cookie` directly** (not from cached AuthContext state — resolves Charge 7) to decide redirect target.

### Isolation enforcement

Three explicit mechanisms (none of them an auto-filter):

**Write routes (Phase 0 disposition table)**: every backend write endpoint gets one of three dispositions, declared explicitly:

| Disposition | Applied to | Mechanism |
|---|---|---|
| `siege_id`-scoped write | Routes with `siege_id` path param touching `Siege` / `Building` / `BuildingGroup` / `Position` / `NotificationBatch` (sieges, positions, board, lifecycle, autofill, attack_day, post_suggestions, posts, siege_members, buildings, notifications, images, validation) | `Depends(require_demo_scope)` — demo user's `demo_session_id` must match the siege's |
| Demo blanket-deny | Routes mutating Member roster or Discord-sync (`members`, `discord_sync`, `post_priority_config`) | `Depends(require_real_user)` — returns 403 if `is_demo=True` |
| Demo-safe shared | Routes that are read-only or globally-safe (auth/me, health, version, config) | Unchanged |

The Phase 0 task produces a verified per-endpoint disposition table — the plan does NOT assert completeness in prose. **Disposition table is checked into `docs/demo-boundary.md` as the authoritative reference.**

**Read routes — list and search**: explicit filters by `is_demo*`. Phase 0 enumerates the complete set. Initial enumeration (to be verified):
- `GET /api/sieges` → filter by `is_demo = current_user.is_demo` AND for demo users `demo_session_id = current_user.demo_session_id`.
- `GET /api/members` → filter by `is_demo_only = current_user.is_demo`.
- Other endpoints returning siege/member collections — TBD by Phase 0.

**Service-layer multi-siege fetches (Charge 2)**: any function that calls `select(Siege)` or `select(Member)` with criteria OTHER than the URL's path parameter must filter by `is_demo`. Concretely fixes `comparison_service.get_most_recent_completed`. Phase 0 audits via `grep "select(Siege" backend/app/services/` and `grep "select(Member" backend/app/services/`. Adds to disposition table.

### Bot short-circuit

Single `ContextVar[Optional[AuthenticatedUser]]` (`_current_user`), set by FastAPI middleware after auth resolves. `bot_client`'s 5 public methods wrap:

```python
class CurrentUserNotSetError(RuntimeError):
    """ContextVar _current_user was unexpectedly unset inside a bot_client call.

    Fail-closed defense-in-depth: if middleware did not set the ContextVar (a bug),
    we refuse to make the bot call rather than silently proceeding as if the
    request were a real-user request. Background tasks must re-establish the
    ContextVar inside the task body — see _send_dms for the pattern.
    """

async def _maybe_short_circuit(method_name: str) -> CannedResponse | None:
    user = _current_user.get(None)
    if user is None:
        # Fail CLOSED: never proceed with a bot call when we don't know who the
        # caller is. The middleware should always set this; if we hit this branch,
        # there's a bug (probably a background task that forgot to re-establish).
        raise CurrentUserNotSetError(
            f"_current_user ContextVar was unset when bot_client.{method_name} was called. "
            f"In request scope, the FastAPI middleware sets it after auth resolves. "
            f"In background tasks, re-establish it explicitly from row state (see _send_dms)."
        )
    if user.is_demo:
        return _canned_response_for(method_name)
    return None
```

**For background tasks (`_send_dms`)**: explicitly re-establish the ContextVar inside the task body, reading `is_demo` from `NotificationBatch.is_demo`. Documented pattern in `bot_client.py` with a comment block for future copy-paste. Failure to re-establish the ContextVar in a background task will now raise `CurrentUserNotSetError` rather than silently making a real bot call — making the bug loud at first invocation rather than silent on tenant boundaries.

### Frontend

- `/demo` route → `DemoLandingPage` → `POST /api/auth/demo-login` → redirect to `/`.
- `DemoBanner` — persistent header when `isDemo`. Shows session idle window, "Exit demo".
- `SimulatedAction` wrapper — adds "(simulated)" badge + tooltip when `isDemo`. Applied to Notify Members, Post to Discord, Sync Discord buttons.
- `AuthContext` — `isDemo: boolean` from `/api/auth/me`.
- **401 interceptor (Charge 7 resolution)**: the JWT cookie is httponly, so frontend JS cannot decode it directly. On 401 the interceptor calls `/api/auth/me` to learn fresh state (NOT cached `AuthContext`), then redirects: `isDemo: true` → `/demo`, otherwise → `/login`. One extra HTTP call on the rare 401 path — cheap, correct, no side-channel cookies. Resolves pass-2 Charge 7 (stale-state failures from trusting cached AuthContext).

**In-flight guard for the refetch (pass-3 Charge 7 follow-up)**: the 401 interceptor uses a module-level `Promise | null` (or `useRef` in a React Query interceptor) as a singleflight latch. If a `/me` refetch is already in flight when another 401 lands, the second handler awaits the first promise rather than firing a parallel `/me` call. Prevents the rare "two parallel 401s → two `/me` calls → two redirects" race.

---

## Infrastructure (R2 additions)

### Redis-backed concurrency cap + rate limit (resolves Charge 5)

**New Bicep module**: `infra/modules/redis.bicep`. Provisions Azure Cache for Redis Basic SKU (C0, ~$15/mo). One per environment (dev + prod). Connection string injected as `REDIS_CONNECTION_STRING` env var into the API Container App via `kv-role-assignments.bicep`.

> **Accepted availability risk** (review finding): Basic C0 tier has no SLA and no replication. Demo mode is consciously deployed against this tier — demo unavailability does not affect real users (Discord OAuth path is unrelated; failing demo-login returns 503 cleanly without cascading). The trade-off is intentional: the demo's primary value is as an adoption tool, not a high-availability product surface. **App Insights alerting must be added on Redis connectivity failures** (operational follow-up — see Phase 2 telemetry task) so we know when the dependency is degraded. If demo evolves into a load-bearing public surface (e.g. linked from a marketing page receiving sustained traffic), upgrade to Standard C0 (~$55/mo, SLA + replication) at that point.

**Concurrency cap mechanism**:
```python
async def acquire_demo_slot(redis: Redis) -> bool:
    n = await redis.incr("demo:active_sessions")
    if n > settings.demo_max_concurrent_sessions:
        await redis.decr("demo:active_sessions")
        return False
    return True

async def release_demo_slot(redis: Redis) -> None:
    await redis.decr("demo:active_sessions")
```

Janitor calls `release_demo_slot` per deleted siege. Demo-login calls `acquire_demo_slot` before fork; on any failure path (timeout, validation error), calls `release_demo_slot` (see § Demo login & fork code block).

**Drift correction**: every 6h, a Container Apps Job runs `python -m app.jobs.demo_slot_reconcile`. To avoid a TOCTOU race with in-flight demo logins (resolves pass-3 Charge NEW-2), the job uses a **stable-delta sampling** strategy:

```python
async def reconcile():
    # Force-reconcile if we've skipped 3 consecutive times (avoids
    # never-converge under sustained churn).
    consecutive_skips = int(await redis.get("demo:reconcile_consecutive_skips") or 0)
    force = consecutive_skips >= 3

    # Take TWO samples ~2 seconds apart; only act if the delta is stable.
    redis_n1 = await redis.get("demo:active_sessions")
    db_n1 = await fetch_count("SELECT count(*) FROM siege WHERE is_demo")
    await asyncio.sleep(2.0)
    redis_n2 = await redis.get("demo:active_sessions")
    db_n2 = await fetch_count("SELECT count(*) FROM siege WHERE is_demo")

    # If either sample shows churn (a login or reap landed mid-window), abort and re-run in 6h.
    if redis_n1 != redis_n2 or db_n1 != db_n2:
        if not force:
            await redis.incr("demo:reconcile_consecutive_skips")
            log.info("demo_slot_reconcile.churn_detected_skipping", consecutive=consecutive_skips + 1, redis=(redis_n1, redis_n2), db=(db_n1, db_n2))
            return
        log.warning("demo_slot_reconcile.churn_force_reconciling", consecutive=consecutive_skips)
    # Reset skip counter once we proceed
    await redis.set("demo:reconcile_consecutive_skips", 0)
    if redis_n2 == db_n2:
        return  # No drift; done.
    log.warning("demo_slot_reconcile.drift_corrected", from_=redis_n2, to=db_n2, delta=db_n2 - redis_n2)
    await redis.set("demo:active_sessions", db_n2)
```

Stable-delta is preferred over a Redis lock because the job runs only every 6h and brief churn is the common case at scale. The consecutive_skips escape hatch guarantees convergence: at 6h cadence × 3 skips = 18h maximum drift window — acceptable.

**Rate limit mechanism**: `slowapi` with `RedisLimiter` backend. `50/hour` per IP on `POST /api/auth/demo-login`. Bumped from initial 10/hour after review noted NAT scenarios (corporate networks, mobile carriers) routinely share a single egress IP — 10/hour rejected legitimate evaluators. 50/hour is the new ceiling; revisit via Phase 2 telemetry. Timeout failures decrement the rate-limit counter (via slowapi's `rollback` hook).

**Python dependency**: add `redis>=5.0` and `slowapi>=0.1.9` to `backend/requirements.txt`.

### Container Apps Job for janitor

**New Bicep module**: `infra/modules/demo-janitor-job.bicep`. Cron schedule `0,30 * * * *` (every 30 min). Image is the backend image. Entrypoint:

```python
# backend/app/jobs/demo_janitor.py
async def main():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            DELETE FROM siege
            WHERE is_demo = True AND last_active_at < now() - interval '4 hours'
            RETURNING id
        """))
        deleted_ids = [row.id for row in result]
    async with redis_client() as redis:
        for _ in deleted_ids:
            await redis.decr("demo:active_sessions")
    log.info("demo_janitor.done", deleted=len(deleted_ids))
```

Single deployment-wide instance (Container Apps Jobs run as one-shot containers, not replicated).

### Replica config

Unchanged: prod 1→3, dev 0→2. Demo mode is now multi-replica-correct.

---

## Triple-Layer Enforcement (R2 refinements)

### Layer 1 — CI grep tripwire (deterministic, blocking)

- `scripts/check_demo_boundary.py` greps PR diff for `is_demo`, `is_demo_only`, `demo_session_id`, `_current_user`, and alias forms (`isDemo`, `demoMode`, `*_demo`).
- Allowlist baked into the script (`ALLOWED_PATHS`) — 8-site list.
- **Phantom path check (Charge 6)**: at startup, the script verifies every glob in `ALLOWED_PATHS` resolves to at least one extant file. If a glob is empty, the script exits 1 with a clear error. Prevents the "add allowlist entry to a future-file" bypass.
- **Bypass syntax**: `# demo-boundary-ok: <reason>` trailing comment. Bypasses are logged to CI output.
- **CODEOWNERS protection on the allowlist file itself**: `scripts/check_demo_boundary.py` requires the user's explicit review on any modification. `.github/CODEOWNERS` entry: `scripts/check_demo_boundary.py @cbeaulieu-gt`.

### Layer 2 — Claude PR reviewer (advisory globally, blocking on allowlist changes)

- Workflow: `.github/workflows/claude-demo-boundary-review.yml`. Triggers on PR open/sync.
- Uses `anthropic/claude-code-action` (verify availability) or inline `@anthropic-ai/sdk` call with `ANTHROPIC_API_KEY`.
- **Default behavior (most PRs)**: posts a PR review comment with `state: COMMENTED` (advisory, non-blocking) when it finds new `is_demo` references or adjacent patterns. Workflow exits 0 regardless of findings.
- **Allowlist-change behavior (when `scripts/check_demo_boundary.py` is in the diff)**: posts with `state: APPROVED` only if the change is justified by Claude's judgment. Workflow exits 1 if `state: CHANGES_REQUESTED`. **This is the second gate on allowlist escalation.**
- **Failure modes (resolves Charge 10)**:
  - Claude API down / API key missing → workflow exits 0 with comment "Claude review unavailable" (advisory mode); EXCEPT on allowlist-change PRs, where the workflow exits 1 to block merge. Forces a human review of the allowlist change in API-outage cases.
  - False-positive rate > some threshold → manual triage; the CI grep remains authoritative.
  - Workflow disabled → CODEOWNERS still blocks allowlist changes; Layer 3 memory still primes future sessions.

### Layer 3 — Local agent memory

- `C:\Users\chris\.claude\projects\I--games-raid-siege-web\memory\feedback_demo_boundary.md` (new).
- Body: the rule, the rationale, the upgrade trigger, the recipe (§ Demo-User Recipe below).
- Indexed in project `MEMORY.md`.

### Tenancy upgrade triggers

- **Hard trigger**: roadmap item for real multi-clan, demo session persistence across logins, demo with multiple players, or friend-clan beta.
- **Soft trigger**: CI grep bypass used >2× in 90 days, OR Claude reviewer flags adjacent-pattern proliferation in 3+ PRs, OR allowlist entries grow by >2 in a quarter.
- On any trigger: pause feature work, review § Migration-to-Tenancy Appendix, decide.

### Demo-User Recipe (resolves Charge 11)

Published in `docs/demo-boundary.md` for any future feature that touches per-user state. Pre-empts the proliferation impulse:

1. **Is the feature siege-scoped (per-siege state, identified by `siege_id` URL param)?** No new boundary work — the `require_demo_scope` dependency already protects it. Proceed.
2. **Is the feature Discord-specific or requires real-clan context (e.g. role checks, real-member sync)?** Block for demo users via `require_real_user`. Document in the disposition table. Proceed.
3. **Is the feature per-Member-state (where Member is shared and read-only in demo)?** Pick one:
   - (a) Skip the feature for demo users (return empty / degraded UX). Document in disposition table.
   - (b) Trigger tenancy-upgrade discussion. Don't extend the boundary; escalate.
4. **Is the feature inherently per-AuthenticatedUser (e.g. UI preferences)?** Postgres FKs cannot point at one of two tables conditionally, so pick one of these two buildable schemas (resolves pass-3 Charge NEW-4):
   - **Two nullable FKs + CHECK constraint**: `UserPreference(id, member_id NULL FK→member, demo_session_id NULL FK→a new demo_session table, value JSON, CHECK ((member_id IS NULL) <> (demo_session_id IS NULL)))`. Pro: real FK integrity on both sides; demo-session prefs reaped via FK cascade. Con: requires a `demo_session` table (which the current plan does not have — currently `demo_session_id` is just a column on `Siege`). Adding the table is a small migration.
   - **Discriminator-string with no FK**: `UserPreference(id, owner_kind ENUM('member', 'demo'), owner_key TEXT, value JSON, UNIQUE(owner_kind, owner_key))`. Pro: no schema additions beyond the new table. Con: no DB-level integrity; demo-session preferences need application-level cleanup when the siege is reaped (add to janitor's cascade).
   The first approach is preferred when the feature warrants strong integrity; the second when minimizing schema surface matters more. **Do not add `is_demo` checks to the preference table or its routes** — the bounded-surface discipline is the whole point.
5. **None of the above fit?** STOP — bring to design review. This is the tenancy-upgrade soft trigger.

---

## Resolution of All Inquisitor Charges (Pass 1 + Pass 2)

### Pass 1 — 12 charges, 11 resolved by R1's Option A+ pivot

(See R1 plan-file revision history; summary: 6 charges eliminated by removing the Tenant abstraction, 6 addressed explicitly.)

### Pass 2 — 15 charges, all addressed in R2

| # | Severity | Resolution |
|---|---|---|
| 1 | BLOCKING | Phase 0 task produces a verified per-endpoint disposition table. Three dispositions: `require_demo_scope` (siege-scoped writes), `require_real_user` (blanket-deny), demo-safe (read/health). Table checked into `docs/demo-boundary.md`. |
| 2 | BLOCKING | Phase 0 service-layer audit greps `select(Siege)` / `select(Member)` outside URL-path-param call sites. `comparison_service.get_most_recent_completed` gets explicit `is_demo` filter. Recipe in boundary doc: service-layer multi-siege fetches must filter by `current_user.is_demo`. |
| 3 | BLOCKING | Migration `0012` seeds `BuildingTypeConfig` (ON CONFLICT `building_type`), `PostCondition` (ON CONFLICT `description`), `PostPriorityConfig` (ON CONFLICT `post_number`), and demo Members (ON CONFLICT `name`) — each on its actual natural-key column, verified in Phase 0. No reliance on `scripts/seed.py` for fresh deploys. (Pass-3 NEW-1 incorporated.) |
| 4 | HIGH | Demo Members named `[DEMO] Alice` etc. (namespaced). Plus a service-layer validator on `POST/PUT /api/members` rejects names matching `^\[DEMO\] ` from real-user writes (pass-3 NEW-3 — without this, the namespacing is decorative against real-clan griefing). Combined with read-only Member fields in demo, the entire mutation surface is closed. |
| 5 | HIGH | Janitor → Container Apps Job (deployment-global). Cap → Redis-backed atomic counter. Rate limit → slowapi Redis backend. New Bicep modules + Redis Cache Basic provisioned. |
| 6 | HIGH | CODEOWNERS protects `scripts/check_demo_boundary.py` (requires user review). Allowlist changes trigger blocking Claude review (Layer 2 exception). Phantom-path check: script errors on empty globs at startup. |
| 7 | HIGH | 401 interceptor calls `/api/auth/me` to learn fresh state instead of using cached `AuthContext`. One extra HTTP call on the rare 401 path; resolves stale-state failures. |
| 8 | HIGH | JWT decode adds mutual-exclusivity assertion: `is_demo=true ⇒ sub absent AND demo_session_id present`; `is_demo=false/absent ⇒ demo_session_id absent`. Mismatches → 401 + logged security event. |
| 9 | MEDIUM | Read-only Members in demo (decided by user). All `Member.*` mutation endpoints return 403 for demo users via `require_real_user`. No cross-session interference because no demo-user can mutate shared state. |
| 10 | MEDIUM | Layer 2 advisory globally, blocking on allowlist changes. Failure modes documented: API outage → workflow exits 0 (advisory) except on allowlist PRs (exits 1). |
| 11 | MEDIUM | Demo-User Recipe section in `docs/demo-boundary.md` (§ above). Pre-empts the per-feature dilemma with a decision tree. |
| 12 | MEDIUM | Fork wrapped by `asyncio.wait_for(transaction, timeout=10.0)` with Postgres `statement_timeout` as backstop. Rollback guaranteed via async session `__aexit__`. User-visible: 503 + retry message + rate-limit decrement on timeout. |
| 13 | LOW | Migration explicitly uses `INSERT ... ON CONFLICT (<natural-key-col>) DO NOTHING` (Postgres-native), per-table as specified in Charge 3 row. No `WHERE NOT EXISTS` race. |
| 14 | LOW | Fork creates 28 `SiegeMember` rows for the demo Members with round-robin `attack_day` distribution. Autofill now operates on a populated `siege.siege_members`. |
| 15 | LOW | `discord_sync.preview_discord_sync` adds `Member.is_demo_only = current_user.is_demo` filter to its match-set query. Added as the third filter site in the bounded-surface list. |

---

## Phasing

### Phase 0 — Enumeration & audit (NEW in R2)

These tasks produce verified artifacts that the rest of Phase 1 depends on. **Each is a small PR.** Phase 0 deliberately precedes any schema/code work — the planning artifacts gate the implementation.

0a. **Write-endpoint enumeration**: grep `backend/app/api/*.py` for all non-GET routes. Produce `docs/demo-boundary.md § Write Endpoint Disposition Table` mapping each to one of three dispositions. PR includes the table + reviewer sign-off.
  - `backend/tests/test_demo_member_endpoints_403.py` (new test file) walks every route in `backend/app/api/members.py` and `backend/app/api/discord_sync.py` that is `POST/PUT/PATCH/DELETE`, calls each as a demo-authenticated request, and asserts the response is 403. This is the programmatic regression gate against accidental Member-mutation leaks through the boundary.

0b. **Service-layer multi-fetch audit**: grep `backend/app/services/` for `select(Siege)` and `select(Member)` outside URL-parameter paths. Produce `docs/demo-boundary.md § Service-Layer Filter Sites`. PR includes the audited list + reviewer sign-off.

0c. **Cascade FK audit**: read every SQLAlchemy model under `backend/app/models/`. Verify `Siege → Building → BuildingGroup → Position` AND `Siege → NotificationBatch → NotificationBatchResult` cascade-delete correctly. Fix any missing `cascade="all, delete-orphan"`. PR includes verification commands + any model fixes.

0d. **`[DEMO] ` prefix rendering audit**: render-test the image-gen and autofill code paths with realistic worst-case seeded names (e.g. `[DEMO] Sebastian` — the longest in the planned seed list) AND a pathological case (`"[DEMO] " + "X" * 40`) separately; the realistic case validates the intended UX, the pathological case is the regression gate against future longer names. Verify no layout breakage in either case. PR includes screenshots / test outputs.

### Phase 1 — Foundation (gated by Phase 0)

1. **Schema + reference-data seed migration** (`0012_add_demo_flags.py`).
2. **`siege_layout.py` extraction** from `seed_demo.py`.
3. **`AuthenticatedUser` extension + JWT cross-check** in `dependencies/auth.py`.
4. **Redis Bicep module + provisioning** + Python deps.
5. **`POST /api/auth/demo-login` + fork service** (including `SiegeMember` creation + Redis slot acquisition + `asyncio.wait_for` timeout).
6. **`require_demo_scope` + `require_real_user` dependencies + apply per Phase 0a table.**
7. **List/service-layer explicit filters** per Phase 0a/0b table.
8. **`_current_user` ContextVar middleware + `bot_client` short-circuit** + documented bg-task pattern.
9. **`NotificationBatch.is_demo` stamping + `_send_dms` ContextVar re-establishment**.
10. **Container Apps Job for janitor** (new Bicep module) + slot-reconcile job.
11. **Rate limit middleware** (slowapi + Redis backend).
12. **Layer 1 CI grep tripwire + CODEOWNERS** for `scripts/check_demo_boundary.py`.
13. **Layer 2 Claude reviewer workflow** + allowlist-blocking branch.
14. **Layer 3 memory + `docs/demo-boundary.md`** (full content: boundary, disposition table, filter sites, recipe).
15. **Frontend demo flow** — `/demo` route, banner, simulated buttons, `isDemo` context, 401 interceptor with `/me` refetch.

### Phase 2 — Polish

16. Telemetry — App Insights custom events.
17. Welcome content — non-intrusive callout on demo siege.
18. Idle-window tuning based on telemetry.
19. **Load testing** — probe-based concurrency tests against the Redis-backed cap and the fork transaction. Validates: (a) cap rejects 101st concurrent demo-login with 503 not 500 not hang, (b) fork timeout fires reliably at 10s under simulated DB latency, (c) janitor doesn't deadlock with high concurrent in-flight forks, (d) slot-reconcile job stable-delta behaves correctly under sustained churn. Not full production traffic — this is a correctness probe at the boundary, not a soak test.

### Phase 3 — Deferred

20. SEO / og:image / marketing-page link.
21. Multiple demo presets ("clean clan" / "messy clan").

---

## Open Decisions (R2)

Defaults remain, all encoded in `config.py`:

1. **Demo idle window**: 4h default. Tune via telemetry in Phase 2.
2. **Concurrency cap**: 100 globally (Redis-backed; honest semantics now).
3. **Discord-button UX**: option (a) — "(simulated)" badge + mocked path. Locked.
4. **Demo siege starts populated or empty?** Empty positions; 28 SiegeMember rows pre-attached (so autofill works).
5. **Janitor cadence**: every 30 min.
6. **Redis SKU**: Basic C0 ($16/mo). Sufficient for the counter use case; can upgrade if telemetry shows latency issues.

---

## Verification

### Phase 0 deliverables (gating Phase 1 start)

- `docs/demo-boundary.md` exists with: bounded-surface list, write-endpoint disposition table, service-layer filter sites, demo-user recipe.
- Cascade FK audit verified by `pytest backend/tests/test_cascade_delete.py` (new test asserting siege deletion cleans up children).
- `[DEMO] ` prefix renders cleanly in autofill + image-gen.

### Backend integration tests (`backend/tests/test_demo.py`, new)

- Demo login issues a JWT with mutually-exclusive claims (assertion: `sub` absent, `demo_session_id` present).
- A real-user JWT with manually-injected `is_demo=true` claim returns 401 (asserts the cross-check fires).
- Two concurrent demo logins create distinct sieges + each gets 28 SiegeMember rows.
- Demo user calls `PUT /api/members/{id}` → 403.
- Demo user calls `POST /api/members` → 403.
- Demo user calls `POST /api/members/discord-sync/preview` → 403.
- Demo user calls `GET /api/sieges/{their_siege_id}/compare` → second siege selected is also `is_demo` (not real). Asserts Charge-2 fix.
- All 5 `bot_client` methods are short-circuited when current_user is demo.
- `_send_dms` short-circuits bot calls when `NotificationBatch.is_demo=True`.
- Janitor (invoked directly) deletes idle demo sieges + decrements Redis counter; real sieges unchanged.
- Slot-reconcile job corrects a drifted Redis counter.
- Fork timeout: with Postgres `statement_timeout=100ms` injected via fixture, fork returns 503 + rollback verified (no orphan siege).
- **Critical regression**: full existing pytest suite passes unchanged.

### Cap & rate-limit tests

- 101st concurrent demo login → 503 + counter unchanged.
- 11th rate-limited request from same IP within 1h → 429 + counter unchanged.
- Timeout failure decrements rate-limit counter (subsequent request not penalized).
- Redis unavailable → `acquire_demo_slot` fails fast with a clear exception → demo-login endpoint returns 503 with `{"error": "demo_dependency_unavailable"}` cleanly. Asserted by running the test with Redis stopped / `REDIS_CONNECTION_STRING=tcp://invalid:6379`. Must NOT 500, must NOT hang.

### CI-mechanism tests

- `scripts/check_demo_boundary.py` exits 1 on phantom-path glob.
- `scripts/check_demo_boundary.py` exits 1 on `is_demo` reference in non-allowlisted file.
- Claude reviewer workflow on a test PR adding `if user.is_demo` to a non-allowlisted file posts a flag.
- Claude reviewer workflow on a test PR modifying `ALLOWED_PATHS` runs in BLOCKING mode (exits 1 if `state: CHANGES_REQUESTED`).

### Frontend manual smoke

1. `/demo` → "Try the demo" → land on `/` with banner.
2. Drag member → validate → autofill (verify 28 members visible, all named `[DEMO] ...`).
3. Notify Members → no real bot call (assert via logs).
4. Post to Discord → fake CDN URLs, no real post.
5. Second incognito → distinct siege; member edits attempted by either session return 403.
6. Wait 4h idle → reload → 401 → `/api/auth/me` refetch → redirect to `/demo` cleanly.

### Production gates

- `DEMO_MODE_ENABLED=false` fully disables `/demo` (404 frontend + backend).
- Real-user OAuth unaffected.
- CI grep blocks intentional violation PR.
- Claude reviewer blocks intentional allowlist-expansion PR (in blocking mode).
- Slot-reconcile job runs cleanly on prod within first 24h.

---

## Migration-to-Tenancy Appendix

If a tenancy upgrade trigger fires (§ Tenancy Upgrade Triggers), here is the migration path. Inlined here so the plan is self-contained — future-us doesn't rediscover it.

**Step 1 — Schema additions** (single migration):
- Create `Tenant` table: `id`, `name`, `discord_guild_id` (nullable), `is_demo` (bool), `created_at`.
- Add `tenant_id` FK to `Siege`, `Member`, `NotificationBatch`.

**Step 2 — Backfill** (same migration, data step):
- Insert one "default" tenant with `discord_guild_id = <settings.discord_guild_id>`, `is_demo=False`.
- For each existing `Siege` with `is_demo=False`: `tenant_id = default.id`.
- For each existing `Siege` with `is_demo=True`: insert a new `Tenant(is_demo=True)` per distinct `demo_session_id`, set `tenant_id` accordingly.
- For `Member` rows: a shared demo-members tenant (since A+ shares demo members across sessions) plus the default tenant for real members.
- Mirror for `NotificationBatch` based on `is_demo`.

**Step 3 — Code migration**:
- Replace `AuthenticatedUser.is_demo` with `AuthenticatedUser.tenant_id` + a property `is_demo` that reads from `tenant.is_demo`. The eight `is_demo` references in business code become tenant lookups; the CI grep allowlist relaxes.
- Replace `require_demo_scope` with `require_tenant_scope`.
- Replace the enumerated list-endpoint filters with tenant-aware filters (this is also when introducing a SQLAlchemy `with_loader_criteria` auto-filter becomes worth the complexity, since the tenant abstraction is now genuinely load-bearing).

**Step 4 — Drop legacy columns** (separate migration, after a deploy cycle has confirmed the new path is stable):
- Drop `Siege.is_demo`, `Siege.demo_session_id`, `Member.is_demo_only`, `NotificationBatch.is_demo`.

**Estimated effort if triggered**: 3-4 weeks. The painful query-scoping audit (the cost of real multi-tenancy) is the same whether paid now (Option C) or then.

---

## Issues / Milestone

Once approved, file under Milestone "Demo Mode" with:
- Phase 0: 4 issues (enumeration, service audit, cascade audit, prefix rendering).
- Phase 1: 15 issues (one per task).
- Phase 2: 4 issues (telemetry, welcome content, idle-window tuning, load testing).

Phase 0 issues are blocking prerequisites for Phase 1; tag accordingly.
