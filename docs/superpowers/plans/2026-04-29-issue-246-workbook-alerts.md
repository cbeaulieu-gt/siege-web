# Issue #246 — Application Health Workbook + Alerts on App Insights

**Issue:** [#246](https://github.com/cbeaulieu-gt/siege-web/issues/246)
**Branch (when implementation starts):** `feature/246-workbook-alerts`
**Worktree (when implementation starts):** `.worktrees/feature-246-workbook-alerts`
**Prerequisite:** #245 (telemetry with `cloud_RoleName` labels) — closed/merged 2026-04-28.
**Plan author date:** 2026-04-29

---

## 0. Context & Goal

Application Insights now ingests telemetry from `siege-api` and `siege-bot` Container Apps with proper `cloud_RoleName` labels. This work delivers:

1. A single **Application Health workbook** with one tab per environment (dev, prod), surfacing the operational vitals an on-call human needs to assess health at a glance.
2. **Five alerts** wired to an email-only action group, each verified by synthetic trigger in dev.
3. **Documentation** updates so the next on-call can find, interpret, and silence the alerts without hunting.

Everything is provisioned via Bicep so the workbook + alerts ride the existing `infra-deploy.yml` GitHub Actions workflow. No portal-only artifacts are accepted as the source of truth — the portal is used **once**, as an authoring aid, and the result is exported into `infra/`.

---

## 1. In Scope vs Out of Scope

### IN SCOPE

- One Azure Workbook resource (`Microsoft.Insights/workbooks`) deployed per environment, containing the six tile groups listed in the issue body.
- Five alert rules (`Microsoft.Insights/scheduledQueryRules`) defined in Bicep, each with a KQL query specific to this app's `cloud_RoleName` values.
- One email action group (`Microsoft.Insights/actionGroups`) per environment, with the user's email as the sole receiver.
- KQL queries pinned in this plan as the load-bearing artifact.
- Synthetic-trigger procedures for each alert, runnable in dev.
- RUNBOOK Section 6 ("Alerts & Workbook"), `infra/README.md` update, and a one-line link from root `CLAUDE.md`.

### OUT OF SCOPE (do not add without explicit user approval)

The issue body explicitly defers these. Listing them here so future drift is obvious:

- **Discord routing for alerts** — email-only at v1. Discord webhook action groups are a separate issue.
- **Multi-team escalation / on-call rotation** — single-recipient action group only.
- **SLO/SLA dashboards** — workbook is operational-vitals only, not a service-level objective tracker.
- **Grafana parity / external observability tools** — App Insights workbook is the single surface.
- **Custom metrics / metric alerts** — all five alerts are log-search alerts on App Insights tables. No `customMetrics` ingestion work.
- **Auto-remediation runbooks / Logic Apps** — alert fires → email → human acts.
- **Cost alerts, security alerts, infra-level alerts (Container App restarts via Azure Monitor platform metrics)** — bot restart is detected via App Insights `traces` / availability heartbeats, not platform metrics.

> **YAGNI guard:** if implementation reveals an attractive sixth tile or sixth alert, stop and ask. Scope additions need explicit justification tied to a real on-call pain point, not "while we're in there."

---

## 2. Phases

Six phases. Phase 3 contains the **one manual portal step**. Everything else is code + Bicep + docs.

---

### Phase 1 — Branch & Module Skeleton ✅ (2026-04-29, commit c8c5715)

- [x] Pull latest `main` and confirm clean working tree
- [x] Create worktree: `git worktree add .worktrees/feature-246-workbook-alerts -b feature/246-workbook-alerts`
- [x] Create `infra/modules/monitoring.bicep` with parameter signature only (no resource bodies yet): `location`, `environment`, `appPrefix`, `appInsightsId`, `appInsightsName`, `alertEmail`
- [x] Wire `monitoring.bicep` into `infra/main.bicep` as a new `module monitoring` after `appInsights`, passing `appInsights.outputs.appInsightsId` and `appInsights.outputs.appInsightsName`
- [x] Add `alertEmail` parameter to `infra/main.bicep` (string, no default — must be set per env)
- [x] Set `alertEmail` in `infra/main.dev.bicepparam` and `infra/main.prod.bicepparam` (both set to `cmb_dev@outlook.com` per user decision)
- [x] Run `az bicep build --file infra/main.bicep` locally to confirm the empty module compiles

**Files touched:**
- `infra/modules/monitoring.bicep` (new)
- `infra/main.bicep`
- `infra/main.dev.bicepparam`
- `infra/main.prod.bicepparam`

**Exit criteria:** `az bicep build` succeeds — PASSED (clean, no errors, no warnings after `#disable-next-line no-unused-params` suppression on `appInsightsName` which is reserved for Phase 3 workbook resource).

---

### Phase 2 — Action Group & Alerts (Bicep) ✅ (2026-04-29, commit 2ab4da9)

- [x] Add `Microsoft.Insights/actionGroups@2023-01-01` resource in `monitoring.bicep`: `groupShortName` ≤ 12 chars (`siege-${environment}`), `enabled: true`, one `emailReceivers` entry pointing at `alertEmail`, `useCommonAlertSchema: true`.
- [x] Add five `Microsoft.Insights/scheduledQueryRules@2023-12-01` resources (API version **upgraded** from plan's `2023-03-15-preview` to stable GA `2023-12-01`, confirmed via Microsoft Learn docs 2026-04-29). Each with:
  - `scopes: [appInsightsId]`
  - `evaluationFrequency: PT1M` for all five alerts
  - `windowSize: PT5M` (PT1M for bot-restart so a single restart fires immediately)
  - `severity: 2` for "page-worthy", `3` for warnings (per-alert table in §4)
  - `criteria.allOf[0]`: `query`, `timeAggregation: Count`, `operator: GreaterThan`, `threshold: 0`
  - `actions.actionGroups: [actionGroup.id]`
  - `autoMitigate: true`
  - `muteActionsDuration: PT15M` to prevent self-spam during incidents
- [x] ~~Add a Bicep `var alertRules = [...]` driven loop~~ — **decision: individual named resources preferred** over a loop. Loop would require `batchSize` decorator and makes individual resource symbolic references awkward. Five discrete resources is more legible and easier to diff per Phase 5 KQL edits.
- [x] Alert 5 uses `requests` table filtered by `name has "generate-images"` per user decision (route confirmed: `POST /sieges/{siege_id}/generate-images` in `backend/app/api/images.py`). No `customEvents` dependency.
- [x] Alert 3 ships with `TODO(#246-phase5)` placeholder predicate: `has_any ("Logged in as", "ready")`.
- [ ] Run `az deployment group what-if -g <dev-rg> -f infra/main.bicep -p infra/main.dev.bicepparam` — **skipped: no Azure credentials in current session**.

**Files touched:**
- `infra/modules/monitoring.bicep`

**Exit criteria:** `az bicep build` PASSED (clean). `what-if` skipped (no creds) — to be run by user before Phase 4 deploy trigger.

---

### Phase 3 — Workbook (portal-authored, Bicep-exported)

> **The one manual portal step.** Hand-authoring `serializedData` for `Microsoft.Insights/workbooks` is brittle — a stray quote breaks the whole workbook with no good error message. The supported workflow is to compose visually in the portal, then export to Bicep/ARM and commit the export.

- [x] In the **dev** App Insights blade → **Workbooks** → **+ New** → build the workbook with the six tile groups below. Use parameterized `cloud_RoleName` (text param, default `siege-api`) where it makes sense so one tile set serves both services without duplication.
  - **Request volume + latency** — `requests | summarize count(), p50=percentile(duration,50), p95=percentile(duration,95) by bin(timestamp,5m), cloud_RoleName | render timechart`
  - **5xx / 4xx rates** — `requests | summarize total=count(), errs5xx=countif(toint(resultCode) >= 500), errs4xx=countif(toint(resultCode) between (400 .. 499)) by bin(timestamp,5m), cloud_RoleName | extend rate5xx=todouble(errs5xx)/total, rate4xx=todouble(errs4xx)/total`
  - **Top 10 exceptions** — `exceptions | summarize count() by type, cloud_RoleName | top 10 by count_`
  - **Bot restart count** — `traces | where cloud_RoleName == "siege-bot" and message has "Bot starting" or message has "Connected to gateway" | summarize count() by bin(timestamp,1h)` (final predicate confirmed in Phase 5 by checking what the bot actually emits at startup)
  - ~~**DB dependency duration p95** — `dependencies | where type == "PostgreSQL" or target contains ".postgres.database.azure.com" | summarize p95=percentile(duration,95) by bin(timestamp,5m), cloud_RoleName`~~ — **DROPPED in v1, blocked by #257** (backend OTel pipeline missing SQLAlchemy + asyncpg instrumentors; `dependencies | where cloud_RoleName == "siege-api"` returns only `InProc` rows — no PostgreSQL spans exist yet)
  - **Image generation duration** — `customEvents | where name == "image_generation" or (name == "Playwright" or operation_Name contains "generate_image") | summarize p50=percentile(toreal(customMeasurements.duration_ms),50), p95=percentile(toreal(customMeasurements.duration_ms),95) by bin(timestamp,15m)` *(the exact event name needs confirmation in Phase 5 — see Open Questions)*
- [x] Save workbook to dev App Insights, then **Workbook → Edit → Advanced Editor → ARM Template → Bicep**, copy the export (workbook authored and exported by user prior to this dispatch; JSON saved at `infra/modules/workbook.template.json`)
- [x] Wrap in `Microsoft.Insights/workbooks@2023-06-01` resource in `monitoring.bicep`. Name uses `guid(resourceGroup().id, 'siege-app-health')` for stable GUID. `kind: 'shared'`, `sourceId: appInsightsId`. Gallery Template JSON loaded via `loadJsonContent('workbook.template.json')` with chained `replace()` to rewrite embedded dev subscription/RG/AI-resource IDs for environment portability. Bicep build: exit 0, clean. (Phase 3b, commit TBD)
- [ ] `what-if` again — should now show one additional resource (the workbook). *(deferred to user; no Azure credentials in this session)*

**Files touched:**
- `infra/modules/monitoring.bicep`
- `infra/modules/workbook-app-health.json` (new — extracted serialized payload)

**Exit criteria:** Bicep deploys cleanly to dev. Workbook shows up in the dev App Insights → Workbooks list with all six tile groups rendering live data.

---

### Phase 4 — Deploy to dev & Verify

- [ ] Trigger `infra-deploy.yml` (workflow_dispatch) targeting dev
- [ ] Confirm in portal: action group exists with the email receiver verified (Azure sends a "confirm subscription" email — click it)
- [ ] Confirm the five alert rules show **Enabled** and **Healthy** in Azure Monitor → Alerts → Alert rules
- [ ] Open the workbook in the dev tab and confirm tiles populate (some will be empty if no traffic — that's fine)
- [ ] Run synthetic triggers per §5; confirm an email arrives for each

**Files touched:** none (deploy + verify only)

**Exit criteria:** five alerts each fire at least once in dev and each delivers an email.

---

### Phase 5 — Verify telemetry assumptions & adjust queries

The KQL queries in §4 and §3 make assumptions about what telemetry the apps actually emit (e.g., bot-restart trace messages, image-generation custom event name). Some of these need ground-truthing **with real logs in dev** before promoting to prod.

- [ ] ~~Run `traces | where cloud_RoleName == "siege-bot" | order by timestamp desc | take 50` and confirm the actual startup log line — adjust the bot-restart query if needed~~ — **DONE EARLY (during portal workbook authoring, 2026-04-29).** Actual startup string: `"FastAPI HTTP sidecar instrumented for OpenTelemetry tracing."` — emitted once per boot by `bot/app/telemetry.py`. Alert 3 KQL updated to `message has "FastAPI HTTP sidecar instrumented"` in the same commit that notes this finding.
- [ ] Run `customEvents | where cloud_RoleName == "siege-api" | summarize count() by name | order by count_ desc` to confirm the image-generation event name (and `customMeasurements` field)
- [ ] Run `dependencies | where cloud_RoleName == "siege-api" | summarize count() by type, target | order by count_ desc` to confirm how PostgreSQL dependencies are tagged (the SQLAlchemy/asyncpg auto-instrumentation tag varies)
- [ ] Update the KQL in `monitoring.bicep` and the workbook JSON to match observed reality
- [ ] Re-deploy dev and re-verify (Phase 4 abbreviated)

**Files touched:**
- `infra/modules/monitoring.bicep` (KQL bodies)
- `infra/modules/workbook-app-health.json` (tile queries)

**Exit criteria:** every query in the workbook and every alert query returns expected data when run by hand against the dev workspace; no `does-not-exist` column errors.

---

### Phase 6 — Promote to prod & Document

- [ ] Trigger `infra-deploy.yml` targeting prod
- [ ] Confirm action group email receiver in prod (email confirmation again)
- [ ] Confirm five alert rules are Enabled in prod
- [ ] Update `docs/RUNBOOK.md` — new **Section 6: Alerts & Workbook** containing:
  - The five alerts, their thresholds, what they mean, first-look diagnostic queries
  - Workbook URL pattern (portal deep link)
  - How to silence/snooze (action group `enabled: false` via portal — emergency only)
- [ ] Update `infra/README.md` with a paragraph: monitoring module purpose, why workbook is portal-authored-then-exported, where the JSON lives
- [ ] Add a one-line link in root `CLAUDE.md` pointing on-call readers at `docs/RUNBOOK.md#6-alerts--workbook`
- [ ] Update `docs/STATUS.md` to reflect operational health monitoring is live
- [ ] Open PR with `Closes #246` in the body (plain text, no backticks)

**Files touched:**
- `docs/RUNBOOK.md`
- `infra/README.md`
- `CLAUDE.md`
- `docs/STATUS.md`

**Exit criteria:** PR merged, #246 closed automatically, on-call colleague (or rubber-duck self) can answer "where do I look when I get paged?" in under 30 seconds using only the runbook.

---

## 3. File Inventory

| File | Status | Purpose |
|---|---|---|
| `infra/modules/monitoring.bicep` | new | Action group, 5 alert rules, workbook resource |
| `infra/modules/workbook-app-health.json` | new | Workbook `serializedData` payload (loaded via `loadTextContent`) |
| `infra/main.bicep` | edit | Wire `monitoring` module + add `alertEmail` param |
| `infra/main.dev.bicepparam` | edit | Set `alertEmail` for dev |
| `infra/main.prod.bicepparam` | edit | Set `alertEmail` for prod |
| `docs/RUNBOOK.md` | edit | New Section 6: Alerts & Workbook |
| `infra/README.md` | edit | Document monitoring module |
| `CLAUDE.md` | edit | One-line link to RUNBOOK §6 |
| `docs/STATUS.md` | edit | Reflect new monitoring capability |

---

## 4. Alert KQL Queries (load-bearing)

All queries scope to `cloud_RoleName in ("siege-api","siege-bot")` to ignore any infra/system telemetry that lands in the same workspace. Each is designed to return zero rows in the steady state and ≥1 row when the condition is breached, so the trigger condition `count > 0` works uniformly.

### Alert 1 — API 5xx rate > 1% over 5m

- **Severity:** 2
- **Window / frequency:** PT5M / PT1M
- **Threshold:** count > 0 (the query itself does the rate math; rows are emitted only when threshold breached)

```kql
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "siege-api"
| summarize total = count(), errors = countif(toint(resultCode) >= 500)
| where total >= 20  // suppress alert when traffic is too low to be statistically meaningful
| extend errorRate = todouble(errors) / total
| where errorRate > 0.01
| project errorRate, errors, total
```

### Alert 2 — API request latency p95 > 3s

- **Severity:** 3
- **Window / frequency:** PT5M / PT1M

```kql
requests
| where timestamp > ago(5m)
| where cloud_RoleName == "siege-api"
| summarize p95 = percentile(duration, 95), sampleCount = count()
| where sampleCount >= 20
| where p95 > 3000  // duration is milliseconds in App Insights
| project p95, sampleCount
```

### Alert 3 — Bot restart (any restart in window)

- **Severity:** 2
- **Window / frequency:** PT1M / PT1M (fast trigger — one restart pages immediately)

```kql
traces
| where timestamp > ago(1m)
| where cloud_RoleName == "siege-bot"
| where message has_any ("Bot starting", "Connected to gateway", "Logged in as")
| summarize restartEvents = count()
| where restartEvents > 0
| project restartEvents
```

> *Phase 5 confirms which startup string the bot actually emits — adjust `has_any` list before promoting to prod.*

### Alert 4 — DB connection error (any in 5m)

- **Severity:** 2
- **Window / frequency:** PT5M / PT1M

```kql
union
  (exceptions
    | where cloud_RoleName == "siege-api"
    | where timestamp > ago(5m)
    | where type has_any ("OperationalError", "InterfaceError", "ConnectionDoesNotExistError", "asyncpg")
        or outerMessage has_any ("could not connect", "connection refused", "connection reset", "server closed the connection")),
  (dependencies
    | where cloud_RoleName == "siege-api"
    | where timestamp > ago(5m)
    | where (type == "PostgreSQL" or target contains ".postgres.database.azure.com") and success == false)
| summarize errors = count()
| where errors > 0
| project errors
```

### Alert 5 — Image generation > 10s

- **Severity:** 3
- **Window / frequency:** PT5M / PT1M

```kql
customEvents
| where timestamp > ago(5m)
| where cloud_RoleName == "siege-api"
| where name == "image_generation"  // confirm exact name in Phase 5
| extend durationMs = toreal(customMeasurements["duration_ms"])
| where durationMs > 10000
| summarize slowRenders = count(), maxMs = max(durationMs)
| where slowRenders > 0
| project slowRenders, maxMs
```

> *If the API does not currently emit a `customEvents` row for image generation, Phase 5 surfaces that — at which point either (a) instrumentation is added in a separate small PR before this alert ships, or (b) the alert is replaced with a `requests` query on the `/api/.../image` route's `duration`. Recommend (a); don't expand scope of this PR for it.*

---

## 5. Synthetic Triggers (dev verification)

Every alert needs to fire **at least once** in dev to satisfy the issue's "Alerts verified by synthetic trigger in dev" acceptance item. Each trigger should be the cheapest, least invasive way to produce the condition.

| Alert | Synthetic trigger |
|---|---|
| 1 — 5xx > 1% | Hit a deliberate 500 endpoint or temporarily add `@router.get("/api/_alert-test/500")` returning `raise HTTPException(500)`, then loop-curl it 30 times. Remove after verification. |
| 2 — p95 > 3s | Add a temporary `@router.get("/api/_alert-test/slow")` that `await asyncio.sleep(4)` then 200s. Curl 30 times. Remove. |
| 3 — Bot restart | `az containerapp revision restart -g <dev-rg> -n siege-bot --revision <current>` — Azure-native, no code change. |
| 4 — DB connection error | Temporarily set the dev API's DB connection string to a bogus host via Container App env override, wait one window, restore. (Or stop the dev Postgres flexible server briefly — simpler but slower to recover.) |
| 5 — Image generation > 10s | Temporary endpoint that `await asyncio.sleep(11); generate_image(...)`, or wrap the existing image route's Playwright launch with a `sleep(11)` behind a feature flag. Hit once. Remove. |

For each: confirm (a) the alert rule status flips to **Fired** in Azure Monitor → Alerts, (b) an email arrives, (c) the rule auto-mitigates back to **Resolved** within ~15 minutes once the condition clears.

**Synthetic-trigger code MUST NOT ship to prod.** Add it on a verification commit, document the reverts in the PR, then revert before the prod deploy step in Phase 6. Alternatively, gate every test endpoint with `if settings.environment != "dev": raise 404`.

---

## 6. Workbook Authoring Approach (justification)

**Recommendation: portal-first, then export to Bicep.** One manual portal step in Phase 3.

**Why not hand-author `serializedData`?**
- The workbook payload is a deeply nested JSON string with portal-specific schema versioning. A typo produces an unhelpful "workbook failed to load" with no line number.
- The portal exposes live preview while editing. KQL is iterative; tiles need tweaking until they render usefully.
- Microsoft's documented authoring flow *is* "build in portal, export ARM/Bicep." Fighting that is friction without payoff.

**Why not leave it portal-only?**
- Portal-only workbooks aren't versioned, aren't reproducible across environments, and disappear if the App Insights resource is recreated. Source-of-truth must be in `infra/`.

**The compromise:** author once in portal → export → paste serialized JSON into `infra/modules/workbook-app-health.json` → reference via `loadTextContent('workbook-app-health.json')` in `monitoring.bicep`. Future edits *can* be made by re-authoring in portal and re-exporting (acceptable), or directly in the JSON for small tweaks (faster for KQL string changes).

This is a **one-time** manual step. Document it in `infra/README.md` so future maintainers know the source-of-truth path.

---

## 7. Open Questions (block implementation)

1. **Alert email recipient — same address for dev and prod?** If different, both `alertEmail` values are needed before Phase 1 can finish.
2. **Image generation telemetry — does `siege-api` currently emit a `customEvents` row for each image render with a `duration_ms` measurement?** Phase 5 verifies, but if the answer is "no instrumentation exists," Alert 5 needs either a quick instrumentation add or a fallback to `requests` filtering on the image route. Decide before Phase 2 finalizes Alert 5's KQL.
3. **Bot startup log line — what string does `SiegeBot` actually log on connect?** Affects the `has_any` predicate in Alert 3 and the bot-restart workbook tile. Verifiable in Phase 5; not strictly blocking, but cleaner if confirmed up front via a quick `traces` query.
4. **`siege-frontend` Container App** — issue mentions only `siege-api` and `siege-bot`. Frontend is also a Container App emitting telemetry. Confirm: is frontend explicitly excluded from this workbook/alerts? (Recommendation: yes, exclude — frontend is a static-asset server with negligible operational risk surface. Document the exclusion in RUNBOOK §6.)

---

## 8. Blockers & Deferrals (updated post-diagnostics 2026-04-29)

**v1 ships with 4 alerts (was 5) and 5 workbook tiles (was 6).** One alert and one tile were dropped based on early Phase-5 ground-truthing against live dev telemetry:

| Item | Status | Reason |
|---|---|---|
| Alert 4 — DB connection error | **DEFERRED** — see #257 | `dependencies | where cloud_RoleName == "siege-api" | summarize by type` returns only `InProc \| 180`. SQLAlchemy + asyncpg OTel instrumentors are not wired into the backend — no PostgreSQL dependency spans exist in App Insights. Adding those instrumentors is tracked in **#257** (milestone #6). Alert 4 will be re-added in the follow-up PR after #257 ships. |
| Tile 5 — DB dependency p95 | **DEFERRED** — blocked by same #257 | Same root cause: no `dependencies` rows for PostgreSQL. Tile would render empty/errored. |

All other items proceed on the original timeline. Bot restart predicate was updated early (see Phase 5 note above). Image generation route confirmed correct — tile is empty only due to zero traffic, no code change needed.

---

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Workbook JSON drift between portal and committed file | Document the portal-export workflow in `infra/README.md`; re-export and commit on every workbook change. CI does **not** detect drift. |
| Alert query references a column that doesn't exist (e.g. wrong custom event name) | Phase 5 ground-truths every query against real dev data before prod promotion. |
| Action group email never confirmed by recipient → alerts silently never deliver | Phase 4 explicitly confirms a real test email arrives, not just that the rule fires. |
| Synthetic trigger code accidentally ships to prod | Test endpoints gated by `environment != "dev"` check; reverts called out in PR description. |
| `scheduledQueryRules` API version drift | Plan used `2023-03-15-preview`; code-writer upgraded to stable GA `2023-12-01` (verified via Microsoft Learn 2026-04-29). If Azure introduces breaking changes, `what-if` will surface them before deploy. |
| Alert noise in early days (false positives during low-traffic dev windows) | Every alert query has a `sampleCount >= 20` or equivalent floor where rates are involved; `muteActionsDuration: PT15M` prevents storms. |

---

## 10. Definition of Done

- [ ] All checkboxes in Phases 1–6 ticked
- [ ] Workbook visible and rendering in both dev and prod App Insights (5 tiles; Tile 5/DB deferred to #257)
- [ ] Four alerts Enabled in both environments (Alert 4/DB deferred to #257)
- [ ] All four v1 alerts confirmed firing + emailing in dev (Phase 4)
- [ ] RUNBOOK §6 written; `infra/README.md` and `CLAUDE.md` updated
- [ ] PR merged via `Closes #246`
- [ ] #246 auto-closed on merge

---

## 11. Recommended Next Agent

**`code-writer` with `azure` + `bicep` skills passed.** Implementation is mostly Bicep authoring with one synchronous portal interaction (Phase 3) the user must run themselves. Code-writer can drive everything else; pause at Phase 3 to hand the portal step back to the user.
