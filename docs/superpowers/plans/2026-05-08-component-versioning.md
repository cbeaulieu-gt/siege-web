# Component Versioning Plan (Issue #311)

> Refs: https://github.com/glitchwerks/siege-web/issues/311
> Drafted: 2026-05-08
> Status: draft — pending 2× inquisitor critique

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

The frontend has *no external embedding consumers* — there is no public component library — so the breaking-change surface is narrow on purpose. UX redesigns that preserve routes and shortcuts are MINOR or PATCH.

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

**Rationale:**

- Per-PR-only is too noisy: a typo fix in a Pydantic `Field(description=...)` doesn't need a bump, and forcing one creates merge conflicts on `VERSION` files.
- At-release-only loses the per-PR provenance that makes "what broke for this consumer" easy to answer.
- Hybrid means the bump is a checkbox on the PRs that *need* it, and silent on the rest. CI enforcement (Q4) makes the checkbox hard to forget.

**Alternatives considered:**
- Strict per-PR (every PR bumps something): rejected, churn ratio too high.
- Strict at-release (one bump per cycle in release PR): rejected, loses signal.

### Q4: CI enforcement — warn or block

**Decision:** **Block** PRs that touch a component's external surface without bumping that component's version. Implementation: a GitHub Actions job that:

1. Computes the diff vs `main` for the PR.
2. For each component, applies a path-based heuristic:
   - **api external surface:** changes under `backend/app/api/**`, `backend/app/schemas/**`, `backend/app/main.py` (route registration), `backend/app/auth/**`.
   - **bot external surface:** changes under `bot/app/http_api.py`, `bot/app/discord_client.py` (slash commands), `bot/app/__init__.py`.
   - **frontend external surface:** changes under `frontend/src/App.tsx` (routes), `frontend/src/pages/**` (page components), changes that add/remove a `VITE_*` env var.
3. If any external-surface path changed AND the component's `VERSION` (or `package.json#version` for frontend) did not change vs `main`, fail the check.
4. Add a `skip-version-bump` label as the documented escape hatch (e.g. for pure-rename refactors that touch the surface but preserve behavior). The label requires reviewer to acknowledge in the PR body.

**Rationale:**

- "Warn" is ignored. CI checks that don't gate merge get tuned out within a sprint.
- Blocking with a labeled escape hatch keeps the rule strict but not adversarial.
- Path-based heuristic is imperfect (will false-positive on internal-only changes that happen to live in those folders) but *cheap*; a proper AST-diff check is over-engineering for v1 of this discipline. The label is the release valve.

**Implementation surface:** new `.github/workflows/version-bump-check.yml`, runs on `pull_request`. ~50 lines of bash + `gh pr diff`. **Does not** touch `deploy.yml`.

**Alternatives considered:**
- AST-diff of OpenAPI spec (proper API-break detection): out of scope for v1; track as a follow-up.
- PR-template checkbox without CI: not enforcement, just hope.

### Q5: Runtime surfacing

**Decision:** Already implemented for all three components. **Phase 1 only adds**: include `frontend_version` reliably (currently it depends on `FRONTEND_VERSION` env var being injected at deploy time — verify the deploy workflow injects it, or add a build-time inject from `package.json#version`).

Specifically:
- `/api/version` — keep as-is (already returns all four fields).
- Bot `GET /version` — keep as-is.
- SystemPage — keep as-is.
- **Add:** an end-to-end test that hits `/api/version` in CI smoke-test stage and asserts all three component versions are non-null and parse as semver.

**Rationale:** the runtime side is the cheap win the issue advertises. Don't redesign what works; just close the `frontend_version: null` gap and add a regression test.

### Q6: Changelog format

**Decision:** **Per-component sub-sections within each `## [v.x.y]` release entry**, replacing today's `Added` / `Fixed` / `Infrastructure` flat structure. Format:

```markdown
## [1.1.0] - 2026-05-XX

### siege-api 1.1.0
- Added: ...
- Fixed: ...

### siege-frontend 1.0.5
- Added: ...

### siege-bot 1.0.1
(no changes this release — version unchanged)

### Infrastructure / repo
- ...
```

**Rationale:**

- Sub-sections per component are the closest thing to "what would the per-component changelog look like" without actually maintaining three files. When the split happens, each section becomes its own `CHANGELOG.md`.
- Keeping `Infrastructure / repo` as a non-component bucket prevents bicep/CI/docs changes from being awkwardly assigned to a component.
- Existing `## [1.0.x]` entries are NOT backfilled (per Non-Goals).

**Alternatives considered:**
- Component versions in a footer/preface only: rejected — losing the per-section grouping makes it harder to extract a per-component history later.
- Three separate changelog files now: rejected — premature; the components don't release independently yet.

### Q7: Contributor documentation

**Decision:** Three documentation surfaces, all updated together in Phase 1:

1. **`CONTRIBUTING.md`** — new section "Versioning" with: the per-component MAJOR rules from Q2, the hybrid cadence rule from Q3, and a pointer to the CI check.
2. **PR template** (`.github/pull_request_template.md`) — add a "Version bumps" line with three checkboxes (siege-api / siege-frontend / siege-bot) and a "N/A — no external surface change" option.
3. **`CLAUDE.md`** — short addition under a new "Component versioning" section pointing AI agents at the rule. This is load-bearing because Claude Code is a frequent contributor here and the path-based CI heuristic from Q4 will block its PRs without guidance.

**Rationale:** documenting in only one place creates the "but I read CONTRIBUTING and didn't see it" gap. PR template is the just-in-time reminder; CONTRIBUTING is the reference; CLAUDE.md is the agent-facing pointer.

## Phasing

### Phase 1: Foundation (low-risk, leaves the project better off even if Phases 2–3 stall)

- [ ] Reconcile current versions: bump `frontend/package.json#version` from `1.0.0` to `1.0.1` to match backend/bot (one-time alignment so the v1.1 release starts from a consistent floor).
- [ ] Verify `FRONTEND_VERSION` env var is injected at deploy time; if not, wire it from `package.json#version` in the frontend Dockerfile build arg.
- [ ] Add CI smoke-test assertion that `/api/version` returns three non-null semver-parseable strings post-deploy (extends an existing smoke test, does not add a new workflow).
- [ ] Write the Q2 breaking-change rules into `CONTRIBUTING.md` under a new "Versioning" section.
- [ ] Update `.github/pull_request_template.md` with the three-component bump checklist.
- [ ] Update `CLAUDE.md` with a short "Component versioning" section.
- [ ] Update `CHANGELOG.md` `## [Unreleased]` entry to use the new per-component structure (Q6) — this is a documentation change only; no code.

**Exit criteria:** all three component versions match, `/api/version` returns non-null for all four fields in dev and prod, CONTRIBUTING + PR template + CLAUDE.md all reference the rule.

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
| Frontend version drift recurs (devs forget to bump `package.json`) | Medium | Low | CI check from Phase 2 catches it; PR template prompts it. |
| `FRONTEND_VERSION` env-var injection silently breaks in prod | Medium | Medium | Smoke-test assertion in Phase 1 catches it before merge to main, not just in production. |
| Per-component changelog format adds friction at release time | Medium | Low | Format is *additive* — releasers can leave a component section as `(no changes this release)`; it's documentation, not a gate. |
| Breaking-change rule for frontend is too loose (real consumers emerge) | Low | Medium | Revisit Q2 if the frontend ever becomes embeddable; written narrowly on purpose for *today's* reality. |
| The `skip-version-bump` label becomes a rubber stamp | Medium | Medium | Require reviewer acknowledgment in PR body when label is applied; periodic audit of label uses. |
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
- **Initial version assignments at v1.2 cut:**
  - `siege-api`: `1.2.0` (or `1.1.0` if no api changes since 1.0.x, etc. — driven by what Q2 says about the changes since last bump).
  - `siege-frontend`: `1.1.0` (new minor; first cycle under new rule).
  - `siege-bot`: `1.0.x` likely PATCH unless an HTTP route changed.
- **Verification:** after first v1.2-track PR merges with a version bump, hit dev `/api/version` and confirm new value reflects. After v1.2 release, hit prod.
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
6. **PR-template checkboxes** are the kind of thing contributors check without thinking. Is there value in a more substantive prompt, or does the CI block from Phase 2 make the checkbox redundant once Phase 2 lands? (If yes, drop the checkbox in Phase 2.)

🤖 *Generated by Claude Code on behalf of @cbeaulieu-gt*
