# Component Versioning Plan (Issue #311)

> Refs: https://github.com/glitchwerks/rsl-siege-manager/issues/311
> Drafted: 2026-05-08
> Status: greenlit — 2× inquisitor passes resolved; ready for Phase 1 implementation

## Goal

Establish a documented, CI-enforced per-component semantic-versioning discipline for `siege-api`, `siege-frontend`, and `siege-bot` while preserving the existing single repo-level `v*` release tag, so that future component split-out becomes a sequencing problem rather than an archaeological one.

## Non-Goals

Lifted from issue #311 "Out of Scope", plus explicit additions:

- **Splitting the repo.** Lockstep release stays. This plan only adds the *labels* a future split would need.
- **Replacing the `v*` tag model.** No mono-tag-per-component, no `siege-api/v1.2.3` style tags.
- **API path versioning** (`/api/v1/*`). Out of scope; tracked separately if it ever becomes needed.
- **Database schema versioning** beyond Alembic. Alembic revision IDs remain the truth for DB shape; surfacing them at runtime is not part of this plan.
- **Rewriting `deploy.yml`.** Minimal touch only (env-var injection for runtime version surfacing if needed). The build/promote model stays.
- **Backporting changelog history.** Existing `## [1.0.x]` entries stay as-is; per-component sub-sections start with the next entry.
- **Inter-component compatibility contracts** (named in the "Inter-Component Compatibility" subsection below). The three prerequisites for split — declared compatibility, deploy refusing incompatible combinations, deprecation policy — are tracked in follow-on issue **#315**, deferred to v2.x discipline. This plan does NOT deliver them.

## Current State (verified 2026-05-08)

Despite the issue's framing as "missing," the runtime plumbing already exists:

| Surface                     | State today                                                    |
|-----------------------------|---------------------------------------------------------------|
| `backend/VERSION`           | ✅ exists, contents `1.0.1` (text file, read by `/api/version`) |
| `bot/VERSION`               | ✅ exists, contents `1.0.1` (text file, read by bot `/version`) |
| `frontend/package.json`     | ✅ `version: "1.0.0"` — **drifted from backend/bot**           |
| `/api/version`              | ✅ returns `{backend, bot, frontend, git_sha}`                  |
| Bot `GET /version`          | ✅ unauthenticated, proxied by backend                          |
| `SystemPage.tsx`            | ✅ renders all three component versions + git SHA              |
| `CHANGELOG.md`              | ✅ Keep-a-Changelog format, single-stream (no per-component)   |
| Bump discipline             | ❌ Not documented, not enforced, not consistent                |
| Breaking-change definitions | ❌ Not defined per component                                   |
| CI enforcement              | ❌ No PR-touches-component-without-bump check                  |
| Contributor docs            | ❌ `CONTRIBUTING.md` does not mention versions                 |

**Implication for sequencing:** the "foundation" tier of the issue is mostly done. The real work is *discipline + documentation + enforcement*. This is good news — it means Phase 1 can be lighter than the issue implies, and the high-leverage work is in Phases 2–3.

## Design Decisions

### Q1: Where do component versions live?

**Decision:** Keep the existing `backend/VERSION` and `bot/VERSION` plain-text files as the canonical version files for those components. Keep `frontend/package.json#version` for frontend. Do **not** introduce `__version__.py` files.

**Rationale:**

- The plumbing already reads these files — switching to `__version__.py` would be churn for no behavior change, and would break `backend/VERSION` references in Dockerfiles / CI.
- A plain text file is trivially read from any language (Python, shell, GitHub Actions, container build args) — `__version__.py` requires Python import.
- `package.json#version` is the JS ecosystem standard; replacing it would break tooling expectations.

**Alternatives considered:**

- `backend/app/__version__.py` (per issue suggestion) — rejected; pure churn, breaks existing readers.
- A single root-level `versions.json` — rejected; couples component bumps to a shared file, defeating the "prepare for split" goal.

### Q2: What constitutes "breaking" per component?

**Decision:** Per-component MAJOR-bump rules:

**`siege-api` (MAJOR):**
- Removing or renaming an existing `/api/*` route.
- Removing or renaming a field in any `response_model` returned by an existing route.
- Changing a field's type or making an optional response field disappear.
- Changing auth requirements on an existing route (e.g. previously cookie-only → now requires header).
- Changing the meaning of an existing field (semantic break, not shape break).

Adding new routes, adding optional response fields, adding new request fields with server-side defaults are MINOR.

**`siege-frontend` (MAJOR):**
- Removing or renaming a top-level route in `App.tsx`.
- Removing a feature flag / environment variable that was previously consumed (e.g. `VITE_API_URL` rename).
- Breaking change to any public-facing URL the operator might bookmark or link to from Discord (siege detail pages, SystemPage, etc.).

The frontend's external surface is **operator-facing, not machine-facing**: bookmarked URLs, Discord-embedded links, browser histories. The breaking-change rule treats any change to URL shape, route names, or feature-flag environment variables as MAJOR — exactly because operators *are* consumers, they just consume URLs rather than APIs. UX redesigns that preserve URL shape and route names are MINOR or PATCH. The "no external embedding consumers" framing in earlier drafts was misleading: it implied a narrower consumer surface than actually exists, and would have left an edge case like `/sieges/:id → /sieges/:slug` ambiguous (the rule says MAJOR, the old rationale implied MINOR).

**`siege-bot` (MAJOR):**
- Removing or renaming any HTTP sidecar endpoint (`POST /api/notify`, `/api/post-image`, `/api/members`, etc.).
- Changing the request schema of an existing endpoint in a non-additive way.
- Removing or renaming any Discord slash command the bot exposes.
- Changing the `Authorization` model on an existing endpoint.

**Rationale:** the bot has *two* surfaces (HTTP + Discord) and both have real consumers (backend + clan members). The api has only the frontend as a real consumer today, but treating it strictly future-proofs the eventual split. The frontend has the loosest definition because there is no machine consumer of its surface — only humans.

**Alternatives considered:** "MAJOR = anything user-visible" for the frontend was rejected as too aggressive — UX is iterative, and a 5.x frontend by year-end is a smell, not a feature.

### Q3: Bump cadence — per-PR vs at-release vs hybrid

**Decision:** **Hybrid, leaning per-PR**:

- Every PR that materially changes a component's *external* surface (per Q2) MUST bump that component's version in the same commit. This includes any MAJOR change.
- PRs touching only internal implementation, tests, or non-shipping files (docs/, scripts/, README, CONTRIBUTING, alembic migrations that don't change response shapes) MUST NOT bump.
- At release time (when cutting a `v*` tag), the release-cutter verifies all three component versions are >= the version recorded at the previous release. If any did not change, that's fine — it just means that component had no external-surface changes this cycle.

**Drift between component versions is expected and desired** under per-component semver. Ceremonial alignment ("they look drifted, let's match them up") is **forbidden** — it re-introduces the lockstep mental model this plan is leaving behind.

**Multi-PR features:** for features spanning multiple PRs, the PR that merges the user-visible change bumps. In-between PRs ship behind a feature flag or do not merge to main. Bumping each PR in a multi-PR feature is wrong — it manufactures three releases for one logical change. Bumping only the last PR (and merging PRs 1–2 unbumped) evades the gate on those PRs; ship them flagged or hold them.

**Edge case: a migration PR that also changes a `response_model` follows the schema rule, not the migration carveout.** Migrations alone do not bump; schema changes do, regardless of whether a migration accompanies them. The "alembic migrations don't bump" line is about the *common* case where a migration adds an internal column or index that doesn't surface to the api response — not a blanket exemption for migration-touching PRs.

**Version numbers are forward-only.** A revert PR that undoes an external-surface change bumps forward — typically PATCH for the revert itself, never reusing the previously-published version number. The CI gate (Q4) sees the `VERSION` line *change* vs `main` (the revert restores prior content), but the bump direction is forward, not backward. **Revert PRs that mechanically reverse a previous bump line fail the gate** because the version they end up at matches `main`'s previous value. Revert PRs use the `version-bump-bypass` label with the revert reason in the auto-filed issue's "why bypass" field. If reverts become common, the queue review (Charge 4 mechanism) will surface the pattern and the rule can be revisited.

**Rationale:**

- Per-PR-only is too noisy: a typo fix in a Pydantic `Field(description=...)` doesn't need a bump, and forcing one creates merge conflicts on `VERSION` files.
- At-release-only loses the per-PR provenance that makes "what broke for this consumer" easy to answer.
- Hybrid means the bump is a checkbox on the PRs that *need* it, and silent on the rest. CI enforcement (Q4) makes the checkbox hard to forget.

**Alternatives considered:**
- Strict per-PR (every PR bumps something): rejected, churn ratio too high.
- Strict at-release (one bump per cycle in release PR): rejected, loses signal.

**Edge cases (pre-releases and hotfixes):**

- **Pre-release versions** (`1.2.0-alpha.1`, `1.2.0-rc.1`, etc.) are **NOT allowed** in `backend/VERSION`, `bot/VERSION`, or `frontend/package.json#version` for v1 of this discipline. Releases ship at clean semver. If pre-release support becomes necessary (e.g. for staged rollouts to dev-only environments), file a follow-on issue rather than improvising in a PR.

- **Hotfix branches** that ship from a release branch (e.g. `release/v1.2.x` for a security fix) bump the relevant component's version forward from the *release-tag baseline*, not the `main` baseline. The CI gate's comparison must be configured to compare against the release tag (`v1.2.0`), not `main` — otherwise the gate sees `main`'s in-flight bumps as the reference and produces nonsense diffs. Until the hotfix workflow is built, hotfix PRs use the `version-bump-bypass` label with the hotfix reason documented; the auto-filed issue surfaces the gap so the workflow can be designed when the first hotfix occurs.

### Q4: CI enforcement — warn or block

**Decision:** **Block** PRs that touch a component's external surface without bumping that component's version. Implementation: a GitHub Actions job that:

1. Computes the diff vs `main` for the PR.
2. For each component, applies a path-based heuristic:
   - **api external surface:** changes under `backend/app/api/**`, `backend/app/schemas/**`, `backend/app/main.py` (route registration), `backend/app/auth/**`.
   - **bot external surface:** changes under `bot/app/http_api.py`, `bot/app/discord_client.py` (slash commands), `bot/app/__init__.py`.
   - **frontend external surface:** changes under `frontend/src/App.tsx` (routes), `frontend/src/pages/**` (page components), changes that add/remove a `VITE_*` env var.
3. If any external-surface path changed AND the component's `VERSION` (or `package.json#version` for frontend) did not change vs `main`, fail the check.
4. Add a `skip-version-bump` label as the documented escape hatch (e.g. for pure-rename refactors that touch the surface but preserve behavior). **Label use auto-files a tracking issue** tagged `version-bump-bypass`, with: PR number, surface paths the gate flagged, and a required "why bypass?" field copied from the PR body. The auto-filing is implemented as a step in the version-bump-check workflow when the label is detected. The `version-bump-bypass` issue queue is owned by **@cbeaulieu-gt** (named owner; updated via PR if ownership transfers). Review cadence: every 5th issue filed in the queue auto-comments on the most recent issue tagging the named owner — converting "we'll remember quarterly" into a queue-self-enforced ping cycle. The named owner can also process the queue ad-hoc at any time. The auto-comment trigger is implemented as a step in the version-bump-check workflow when the label is detected: it counts open `version-bump-bypass` issues, and on every Nth filing (N=5 to start, tunable), posts a `@cbeaulieu-gt review needed` comment on the newly-filed issue.

**Rationale:**

- "Warn" is ignored. CI checks that don't gate merge get tuned out within a sprint.
- Blocking with a labeled escape hatch keeps the rule strict but not adversarial.
- Path-based heuristic is imperfect (will false-positive on internal-only changes that happen to live in those folders) but *cheap*; a proper AST-diff check is over-engineering for v1 of this discipline. The label is the release valve.
- The heuristic fails open in one important case: a breaking change to a service-layer return shape that flows through an unchanged `app/api/*.py` thin shim does not trigger the gate. **The gate produces a green check on a real break.** This is the FN failure mode, and it's worse than the FP one. The mitigation is honest framing in CONTRIBUTING.md, not wider path matching — see Risk Register.

**Implementation surface:** new `.github/workflows/version-bump-check.yml`, runs on `pull_request`. ~50 lines of bash + `gh pr diff`. **Does not** touch `deploy.yml`. Plus a CONTRIBUTING.md section explicitly stating what the gate catches and does not catch — reviewer judgment is the second line of defense.

**Alternatives considered:**
- AST-diff of OpenAPI spec (proper API-break detection): out of scope for v1; track as a follow-up.
- PR-template checkbox without CI: not enforcement, just hope.

### Q5: Runtime surfacing

**Decision:** Already implemented for all three components. **Phase 1 only adds**: include `frontend_version` reliably (currently it depends on `FRONTEND_VERSION` env var being injected at deploy time — verify the deploy workflow injects it, or add a build-time inject from `package.json#version`).

Specifically:
- `/api/version` — keep as-is (already returns all four fields).
- Bot `GET /version` — keep as-is.
- SystemPage — keep as-is.
- **Add:** an end-to-end test that hits `/api/version` in CI smoke-test stage and asserts all three component versions match expected values. Expected `frontend_version` is read from `package.json#version` at deploy time and passed to the smoke check as `EXPECTED_FRONTEND_VERSION`; expected `backend_version` and `bot_version` are read from `backend/VERSION` and `bot/VERSION` similarly. "Parses as semver" is insufficient — that assertion would pass on a frontend bundle stuck at `1.0.0` while the deployed image is `v1.2.0`, which is exactly the drift mode the test is named against.

**Rationale:** the runtime side is the cheap win the issue advertises. Don't redesign what works; just close the `frontend_version: null` gap and add a regression test.

### Q6: Changelog format

**Decision:** **Per-component sub-sections within each `## [v.x.y]` release entry**, replacing today's `Added` / `Fixed` / `Infrastructure` flat structure. Format:

```markdown
## [1.1.0] - 2026-05-XX

Components changed: siege-api, siege-frontend.

### siege-api 1.1.0
- Added: ...
- Fixed: ...

### siege-frontend 1.0.5
- Added: ...

### Infrastructure / repo
- ...
```

**Rationale:**

- Sub-sections per component are the closest thing to "what would the per-component changelog look like" without actually maintaining three files. When the split happens, each section becomes its own `CHANGELOG.md`.
- **Empty per-component sections are omitted entirely** — the "Components changed:" line at the top of each release entry tells the reader which components actually moved. **Verified consumer behavior.** The in-app changelog dropdown shipped in v1.1 (#298) reads `CHANGELOG.md` via the Vite plugin at `frontend/src/build/changelog-plugin.ts`, which calls into the parser at `frontend/src/build/changelog-parser.ts`. The parser extracts `## [version]` lines as release entries and `### Heading` lines as section keys, with bullet content collected into the value array of a `Record<string, string[]>`. The `### siege-api 1.1.0` format renders cleanly: each `### Heading` becomes a section header in the dropdown UI; omitting empty per-component sections produces no orphan headings (the parser sees nothing to extract for the omitted component). The format decision is verified against actual consumer code, not assumption.
- Keeping `Infrastructure / repo` as a non-component bucket prevents bicep/CI/docs changes from being awkwardly assigned to a component.
- Existing `## [1.0.x]` entries are NOT backfilled (per Non-Goals).

**Authoring rule.** The `Components changed:` line is **hand-authored at release time** by the release-cutter. The rule, lifted into CONTRIBUTING.md as part of Phase 1: *"The 'Components changed:' summary line must list exactly the components with `###` sub-sections in this entry — no more, no less. Drift between the summary line and the sub-sections is a release-time error and must be fixed before the tag is cut."* Auto-generation is deferred to Phase 3 as an optional follow-up if drift becomes a real problem; for now, manual sanity-check by the release-cutter is sufficient given the small release cadence.

**Alternatives considered:**
- Component versions in a footer/preface only: rejected — losing the per-section grouping makes it harder to extract a per-component history later.
- Three separate changelog files now: rejected — premature; the components don't release independently yet.

### Q7: Contributor documentation

**Decision:** Three documentation surfaces, all updated together in Phase 1:

1. **`CONTRIBUTING.md`** — new section "Versioning" with: the per-component MAJOR rules from Q2, the hybrid cadence rule from Q3, and a pointer to the CI check.
2. **PR template** (`.github/pull_request_template.md`) — add a "Version bumps" line with three checkboxes (siege-api / siege-frontend / siege-bot) and a "N/A — no external surface change" option. **The checkbox stays even after the Phase 2 CI gate lands** — its value is surfacing the bump decision *during PR authoring*, before the contributor opens the PR and gets blocked. Without it, the contributor opens the PR, gets blocked by CI, goes back to bump, re-pushes — a friction loop the checkbox prevents. Phase 2's CI gate is correctness; the checkbox is UX. They're complementary.
3. **`CLAUDE.md`** — short addition under a new "Component versioning" section pointing AI agents at the rule. This is load-bearing because Claude Code is a frequent contributor here and the path-based CI heuristic from Q4 will block its PRs without guidance.

**Rationale:** documenting in only one place creates the "but I read CONTRIBUTING and didn't see it" gap. PR template is the just-in-time reminder; CONTRIBUTING is the reference; CLAUDE.md is the agent-facing pointer.

## Inter-Component Compatibility (named non-goal for v1; hard prerequisite for split)

This plan establishes per-component semver but **does not** define how `siege-api 2.x` interoperates with `siege-frontend 1.x`, or any other cross-component compatibility contract. That is *the* point of independent component versions — without a compatibility contract, the versions are decorative.

Why this is deferred:

- Today, all three components ship together at the same `v*` tag, so compatibility is **implicit at the tag level**: whatever combination of component versions ride together in a tagged release is the only combination that's been validated.
- Defining a real compatibility contract requires consumer pinning (e.g. `frontend` declares `requires siege-api >=1.0,<2.0`), pre-release matrix testing, and a deprecation policy. None of that machinery exists today and building it would dwarf the rest of this plan.

What this means for the eventual split:

Before any actual repo split can occur, this gap **must** be closed. At minimum:

1. Each component declares the api/bot/frontend versions it has been tested against.
2. The deploy pipeline refuses combinations that violate declared compatibility.
3. A deprecation policy says how long an api MAJOR remains supported.

This is named here so that "prepare for split" cannot be confused with "ready to split." The plan delivers the labels; it does not deliver the contract.

**Tracked as follow-on:** issue #315 (`design: inter-component compatibility contracts (deferred follow-on to #311)`) carries the deferred work. Closing the gap is a hard prerequisite for any actual repo split — that's the issue's done state, not this plan's.

## Phasing

### Phase 1: Foundation (soft-guideline window — Phase 2 must close it by v1.3 cut)

Phase 1 establishes the discipline as a **soft guideline**: the rule is documented, the runtime surface is verified, but no CI gate exists. Reviewers can cite the rule but it is not enforced. **This window is bounded.** Phase 2 must land by the v1.3 release cut. If Phase 2 stalls past v1.3, the discipline rolls back: Phase 1's docs are explicitly downgraded to "informal practice" rather than allowed to remain as un-enforced citation surface. (See Risk Register for the rollback condition.)

**Enforcement surface for the deadline:**

1. **Release runbook checklist** — `RUNBOOK.md`'s release section (or equivalent pre-tag-cut checklist) gains a new line: *"Before tagging `v1.3.0`, verify `.github/workflows/version-bump-check.yml` exists. If absent, follow the rollback procedure (downgrade Phase 1 docs to 'informal practice' banner) before cutting the tag."*

2. **Tracking issue with milestone** — at v1.2 cut, file a tracking issue titled "Phase 2 deadline: v1.3 cut" with milestone `v1.3` and label `version-discipline`. The issue closes either by Phase 2 landing (auto-close via the Phase 2 PR's `Closes` keyword) or by rollback execution (manual close with rollback-summary comment). The `v1.3` milestone surfaces the issue in the v1.3 release planning view.

Both surfaces fail loudly: the runbook checklist blocks the tag cut on missing workflow file; the tracking issue surfaces in the milestone planning view. "We'll remember" is replaced by two independent enforcement paths.

- [ ] Verify `FRONTEND_VERSION` env var is injected at deploy time; if not, wire it from `package.json#version` in the frontend Dockerfile build arg.
- [ ] Add CI smoke-test assertion that `/api/version` returns all three component versions matching expected values (per Q5 — extends an existing smoke test, does not add a new workflow).
- [ ] Write the Q2 breaking-change rules into `CONTRIBUTING.md` under a new "Versioning" section.
- [ ] CONTRIBUTING.md adds the `Components changed:` summary-line rule alongside the Versioning section.
- [ ] CONTRIBUTING.md's "Versioning" section presents the bump-or-not decision as a **decision table or flowchart**, not a wall of paragraphs. Six logical clauses in Q3 prose form is too many for a contributor to hold in mind during a PR; the table is the contributor's actual reference. (Plan does not specify the table's content — Phase 1 implementation work delivers it.)
- [ ] Update `.github/pull_request_template.md` with the three-component bump checklist.
- [ ] Update `CLAUDE.md` with a short "Component versioning" section.
- [ ] Update `CHANGELOG.md` `## [Unreleased]` entry to use the new per-component structure (Q6) — this is a documentation change only; no code.

**Exit criteria:** `/api/version` returns non-null for all four fields in dev and prod, CONTRIBUTING + PR template + CLAUDE.md all reference the rule.

### Phase 2: Enforcement

- [ ] New workflow `.github/workflows/version-bump-check.yml` implementing Q4 (block PR if external-surface changed without version bump; `skip-version-bump` label is escape hatch).
- [ ] Document the escape-hatch label in CONTRIBUTING.md (reviewer must acknowledge in PR body when label is applied).
- [ ] Trial: deliberately open a no-bump PR that touches `backend/app/api/**`, confirm the check fails. Open a bumped PR, confirm it passes.

**Exit criteria:** version-bump-check workflow is required for merge to `main` (branch protection updated), trial PR demonstrates both the block path and the bypass path.

### Phase 3: Future-proofing (defer if v1.1 is tight)

- [ ] OpenAPI spec snapshot in CI: dump FastAPI's generated OpenAPI on each build, diff vs `main`, surface as a PR comment (informational, not blocking — this is signal for the bump-check, not a replacement).
- [ ] Bot Discord-command surface snapshot: enumerate registered slash commands, diff vs `main`, same pattern.
- [ ] Per-component CHANGELOG extraction script: parse `CHANGELOG.md` and emit `siege-api-CHANGELOG.md` / etc. — useful precursor to actual repo split.

**Exit criteria:** at least the OpenAPI snapshot is in place and producing useful PR comments. The other two are nice-to-have.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Path-based CI heuristic false-positives on internal-only changes | High | Medium (annoying, not blocking) | `skip-version-bump` label as documented escape hatch; revisit with AST-diff in Phase 3 if pain is real. |
| **Path-based gate produces false negatives — breaking change in `services/` flows through unchanged `app/api/*.py` shim, gate green-checks the merge** | High | High | Document the gap honestly in CONTRIBUTING.md ("the gate is one line of defense, not the only one"). Reviewer judgment is the second line for service-layer changes that back a public API. Do NOT widen the path list to `services/**` — that collapses the FP rate into intolerable territory and forces the bypass label to become the default (see related risks below). |
| Frontend version drift recurs (devs forget to bump `package.json`) | Medium | Low | CI check from Phase 2 catches it; PR template prompts it. |
| `FRONTEND_VERSION` env-var injection silently breaks in prod | Medium | Medium | Smoke-test assertion in Phase 1 catches it before merge to main, not just in production. |
| Per-component changelog format adds friction at release time | Medium | Low | Format is *additive* — releasers can leave a component section as `(no changes this release)`; it's documentation, not a gate. |
| Breaking-change rule for frontend is too loose (real consumers emerge) | Low | Medium | Revisit Q2 if the frontend ever becomes embeddable; written narrowly on purpose for *today's* reality. |
| The `skip-version-bump` label becomes a rubber stamp | Medium | Medium | Auto-filed `version-bump-bypass` issue queue is the audit artifact. Owner is `@cbeaulieu-gt` (named, updated via PR). Cadence is event-driven: every 5th queue filing auto-pings the owner, so the cadence is enforced by the queue itself rather than by a calendar reminder. If quarterly review finds the queue growing without distinct justifications, the bypass mechanism itself is reviewed. |
| **Phase 2 stalls indefinitely; Phase 1's docs become un-enforced citation surface that reviewers selectively cite** | Medium | Medium | Phase 2 has a v1.3 deadline. If Phase 2 has not landed by v1.3 cut, Phase 1's CONTRIBUTING.md and CLAUDE.md sections are downgraded to "informal practice" with a clear banner; the rule is not allowed to live in citation-surface limbo. |
| Inquisitor surfaces "this is all just process for one team" | Medium | Low | Plan explicitly framed as future-proofing for split — accept that present-day ROI is modest. |

## Sequencing relative to v1.1 release

**Recommendation: let v1.1 ship as-is, Phase 1 lands as v1.2 first-iteration.**

Reasoning:

- Phase 1 is documentation + a one-line frontend version bump + a smoke-test assertion. None of it is shippable customer value. Blocking v1.1 on it is process tax.
- The runtime plumbing (`/api/version`, SystemPage) is *already in v1.0.x*. v1.1 does not regress anything by shipping without Phase 1.
- Phase 2 (the enforcement workflow) is where the discipline becomes load-bearing. That's the right gate for v1.2 — by then the rule has been documented for one full release cycle and contributors have seen the PR-template prompt.
- Cutting v1.1 cleanly also gives us a real "before / after" datapoint: were any v1.1 changes that *should* have been MAJOR caught only retroactively? That's evidence for whether Q2's definitions are calibrated.

The alternative — block v1.1 cut on Phase 1 — buys little, since Phase 1 is mostly docs, and risks scope-creep where Phase 2 work sneaks into v1.1 under deadline pressure.

## Rollout

- **Day 0:** This plan merges. Phase 1 PRs land independently against `main` post-v1.1 cut.
- **At v1.2 cut:** components with external-surface changes per Q3 since v1.1 bump per Q2's MAJOR/MINOR/PATCH rules. Components without surface changes stay at their current version. Drift between components is the expected steady state — not a problem to be reconciled.
- **Verification:** runtime version verification is automated via the Q5 smoke-test assertion in CI; no manual `/api/version` check is needed at release time. Operator readout (the SystemPage UI) remains the way operators see the live values.
- **Operator readout:** the SystemPage already renders this — no operator-facing UI changes needed beyond what's in v1.0.x.

## Acceptance Criteria

Lifted from issue #311 and refined:

- [ ] Each component has a documented canonical version file (Q1) — already true; documented in CONTRIBUTING.md (Phase 1).
- [ ] Per-component MAJOR rules documented (Q2) — in CONTRIBUTING.md (Phase 1).
- [ ] Hybrid bump cadence documented (Q3) — in CONTRIBUTING.md (Phase 1).
- [ ] CI workflow blocks PRs that miss required bumps (Q4) — Phase 2.
- [ ] `/api/version` and bot `/version` report all components reliably (Q5) — already true; Phase 1 closes the `frontend_version: null` gap.
- [ ] SystemPage displays all three versions — already true.
- [ ] CHANGELOG.md uses per-component sub-sections (Q6) — Phase 1, starting with `## [Unreleased]`.
- [ ] CONTRIBUTING.md, PR template, and CLAUDE.md all reference the rule (Q7) — Phase 1.
- [ ] Trial release (v1.2) demonstrates the discipline end-to-end — by end of Phase 2.

## Open Questions for the Inquisitor

Where I'm uncertain and want the adversarial pass to push:

1. **Q4 path-based heuristic:** is the false-positive rate going to be tolerable, or will the `skip-version-bump` label become the path of least resistance within two weeks? Is there a way to make the heuristic tighter without going full AST-diff?
2. **Q2 frontend MAJOR rule** is deliberately narrow ("no external embedding consumers"). Is that defensible, or is the human-bookmark / Discord-link surface meaningful enough that route renames warrant MAJOR even today? My read is "no, don't burn through major versions on UX iteration"; I want this challenged.
3. **Q6 changelog format:** does breaking the existing Keep-a-Changelog `Added/Fixed/Infrastructure` flat structure cost us search/release-note tooling that I'm not aware of? I think no, but I haven't audited the changelog-consumer surface.
4. **Phase 1 scope:** I argue the issue's "missing component versions" framing is stale because the plumbing landed already. If that read is wrong — if there's a meaningful surface that's *still* missing — Phase 1 needs to grow. The inquisitor should sanity-check the current-state table.
5. **Sequencing recommendation:** I argue v1.1 should ship without this. A reasonable alternative argues the *first* release after the discipline is announced should be the *first* release that demonstrates it, and that's v1.1 not v1.2. Either is defensible; would value the second opinion.

🤖 *Generated by Claude Code on behalf of @cbeaulieu-gt*
