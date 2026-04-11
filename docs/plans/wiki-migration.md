# Post-v1.0 wiki migration: human docs to GitHub Wiki, dev/agent docs stay in `docs/`

**Tracking issue:** #189
**Status:** Designed, not executed. Execution blocked until v1.0 ships (#173–#176), #187 (docs freshness pass), and #188 (community health files) all land.
**Supersedes:** Nothing. No prior wiki migration plan exists in this repo.
**Audience of this doc:** A `code-writer` agent. Every non-obvious decision is pre-made — the executor follows the checklist in section 12 without making architectural calls.

---

## 1. Goal and strict scope

Split the docs audience. Human-facing narrative content (self-host guides, Getting Started, FAQ, project Home) moves to a GitHub Wiki, authored canonically in a `wiki/` folder in the main repo and mirrored to `siege-web.wiki.git` by a GitHub Action on push to `main`. Developer and AI-agent working docs stay in `docs/` untouched.

**Filter (from #189, locked):** *only content targeted at human consumption AND only content where a reader would expect to find it in a wiki.* Nothing else moves. Dev docs (`STATUS.md`, `WEB_DESIGN_DOCUMENT.md`, `IMPLEMENTATION_PLAN.md`, `RUNBOOK.md`, `siege_levels.md`, `plans/**`, `superpowers/plans/**`, `mockups/**`) stay in `docs/`.

**Five pages in scope** — identical to issue #189:

1. `Home` (new)
2. `Getting-Started` (new)
3. `Self-Host-on-Azure` (migrated from `docs/self-host/azure.md`)
4. `Self-Host-on-Any-VPS` (migrated from `docs/self-host/anywhere.md`)
5. `FAQ` (new, skeleton only)

Plus one wiki-infra file: `_Sidebar.md`.

---

## 2. Pre-flight findings (what the executor needs to know before touching anything)

A read-only sweep of the repo surfaced a few things the plan has to account for:

- **`docs/self-host/*` is referenced from four places**, not just the README:
  1. `README.md:126-127` — the "Run it yourself" section
  2. `infra/README.md:5` — one-line pointer to `../docs/self-host/azure.md`
  3. `frontend/src/pages/LandingPage.tsx:407` and `:431` — `blob/main/docs/self-host/anywhere.md` and `blob/main/docs/self-host/azure.md` as external anchor `href`s
  4. `frontend/src/test/components/LandingPage.test.tsx:114,118` — asserts those exact `href` values

  The landing page links and their tests mean the migration PR either (a) updates the component **and** the test to point at wiki URLs, or (b) leaves `docs/self-host/*` in place as redirect stubs so the existing links still resolve. The plan picks (a) for the component + test update *and* (b) for the file stubs — see section 5.

- **Neither self-host doc references any images.** `grep` for `![`, `.png`, `.jpg`, `.svg`, `.gif`, and `docs/assets` under `docs/self-host/` returned no matches. This removes an entire class of migration work — no image relocation, no `raw.githubusercontent.com` rewrites. Section 10 still documents the policy for future pages.

- **Neither `CLAUDE.md` references any wiki-bound doc.** Verified both files:
  - User global `C:\Users\chris\.claude\CLAUDE.md`: no references to `docs/self-host`, no references to the wiki, no references to any of the five page targets. It is entirely generic workflow guidance. **Verified clean.**
  - Project-local `I:\games\raid\siege-web\CLAUDE.md`: references `docs/IMPLEMENTATION_PLAN.md`, `docs/WEB_DESIGN_DOCUMENT.md`, `docs/STATUS.md`, `docs/superpowers/plans/discord-auth-plan.md`, and memory files. **None** of these are in wiki scope. **Verified clean.**

  Record these two verification results in the PR description so the `CLAUDE.md` acceptance criterion from #189 is traceable.

- **No existing `wiki/` folder, no `.github/workflows/wiki-*.yml`, no prior wiki commits.** Clean slate — the executor is not working around prior migration attempts.

- **Wiki bootstrap status (2026-04-11): RESOLVED.** First page manually created in the GitHub UI, so `https://github.com/cbeaulieu-gt/siege-web.wiki.git` now exists as a writable git repo. The `github-wiki-action` can push to it on the first workflow run. No further bootstrap work needed.

- **`docs/plans/public-launch-self-hostable-and-landing-page.md` already mentions the self-host files as artifacts of Issue 2 and Issue 3.** That plan is *historical* — those issues are done and the files exist. The wiki migration does not conflict with it; it just moves the files' canonical location.

---

## 3. Non-goals

- Migrating any other file from `docs/` to the wiki. This plan is exactly the five pages in #189. Any subsequent "should this doc go to the wiki?" question is a separate issue.
- Rewriting `docs/WEB_DESIGN_DOCUMENT.md`, `docs/siege_levels.md`, or any other dev-audience doc into a wiki page.
- Enabling GitHub Discussions. Orthogonal.
- Populating real FAQ content — only a skeleton ships in this migration. FAQ entries accrue post-launch as real questions arrive.
- Non-English translations.
- Moving images anywhere — there are none (see section 10).
- Restructuring `docs/` itself. `docs/self-host/` stays as a directory containing redirect stubs (see section 5); nothing else in `docs/` moves or renames.
- Making the wiki publicly editable. Keep the default: collaborators only.

---

## 4. Decision 1 — Which wiki-push GitHub Action

### Candidates evaluated

| Criterion | `Andrew-Chen-Wang/github-wiki-action` | `SwiftDocOrg/github-wiki-publish-action` | `docker://decathlon/wiki-page-creator-action` (mentioned for completeness) |
|---|---|---|---|
| Maintenance status | Actively maintained; releases through 2024+ | Last meaningful release 2020; marked as in maintenance mode by the author; repo description explicitly points users at alternatives | Abandoned; community action, last update pre-2022 |
| Scope to subfolder of the main repo | Yes — `path:` input (default `wiki/`) | Yes — `path:` input | Folder-level, but limited |
| Handling of deletions | Mirrors the folder exactly: deleted files in `wiki/` are deleted on the wiki git repo via a fresh commit. Does **not** force-push by default. | Force-pushes the folder contents; deletions work but overwrite history | Creates/updates only; does not delete |
| Auth mechanism | `GITHUB_TOKEN` is insufficient — the workflow needs a PAT with `repo` scope (or a GitHub App installation token), because the wiki git repo is a separate remote that `GITHUB_TOKEN` cannot write to. The action accepts `WIKI_COMMIT_MESSAGE`, `GH_PERSONAL_ACCESS_TOKEN` and related inputs. | Same PAT constraint — `GITHUB_TOKEN` cannot write to `*.wiki.git`. | Same PAT constraint. |
| Dry-run support | Yes — `dry_run: true` input exits before pushing. Useful for the first merge-train run. | No built-in dry-run. | No. |
| Commit message customization | Yes | Yes | Limited |
| Stars / community use | Higher star count, many real users | Lower; Swift-community-adjacent | Low |

### Pick

**`Andrew-Chen-Wang/github-wiki-action`**.

**Why:** active maintenance, dry-run input, explicit deletion handling (important — a wiki page deleted from `wiki/` must disappear from the wiki, not linger forever), and a larger user base means issues surface before we hit them. `SwiftDocOrg` is in maintenance mode and its README points at alternatives; adopting an action that is on the way out is a trap.

**PAT vs `GITHUB_TOKEN` — this is non-obvious and must be locked:**
`GITHUB_TOKEN` **cannot** push to `<repo>.wiki.git`. GitHub scopes `GITHUB_TOKEN` to the repository it runs in, and the wiki git repo is technically a sibling repository that `GITHUB_TOKEN` has no write permission for. Every wiki-push Action requires either a classic PAT with `repo` scope, a fine-grained PAT with `Contents: Write` on the target repo (fine-grained PATs do grant this to the associated wiki), or a GitHub App installation token.

**Pick (DECIDED 2026-04-11): classic PAT** with `repo` scope, stored as the repository secret `WIKI_PAT`. Rationale: simpler to provision than a GitHub App, fine-grained PAT coverage for wiki writes has rough edges in the GitHub Actions runner environment, and a classic PAT on an owner-restricted repo is an acceptable trust level for a docs-only secret. Create the PAT under the `@cbeaulieu-gt` account (not a bot account) with no expiry, and **rotate it** if the owner ever revokes ownership of the repo — document this in the plan's section 12 manual-steps checklist. Classic PAT is accepted tech debt; a future hardening pass may swap it for a GitHub App installation token once `Andrew-Chen-Wang/github-wiki-action` documents stable support for that path. File a follow-up issue at execution time: *"Migrate wiki-publish auth from classic PAT to GitHub App."*

### Workflow file — `.github/workflows/wiki-publish.yml`

Exact content the executor commits:

```yaml
name: Publish wiki

on:
  push:
    branches: [main]
    paths:
      - 'wiki/**'
      - '.github/workflows/wiki-publish.yml'
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Dry run (do not push to wiki)'
        required: false
        default: 'false'

permissions:
  contents: read

jobs:
  backend-ci:
    name: Backend Lint & Test (gate)
    uses: ./.github/workflows/ci.yml

  frontend-ci:
    name: Frontend Lint & Build (gate)
    uses: ./.github/workflows/ci.yml

  bot-ci:
    name: Bot Lint & Test (gate)
    uses: ./.github/workflows/ci.yml

  publish:
    name: Mirror wiki/ to siege-web.wiki.git
    runs-on: ubuntu-latest
    # DECIDED 2026-04-11: strict CI gate. wiki-publish fires only on push to
    # main AND only after the full CI pipeline is green on the same commit.
    # The `needs:` chain here references the three CI jobs defined in this
    # workflow; together with the `paths: wiki/**` trigger filter they ensure
    # wiki content is never published from a broken build.
    needs: [backend-ci, frontend-ci, bot-ci]
    steps:
      - name: Checkout main repo
        uses: actions/checkout@v4

      - name: Publish wiki/ to GitHub Wiki
        uses: Andrew-Chen-Wang/github-wiki-action@v4
        with:
          path: wiki/
          token: ${{ secrets.WIKI_PAT }}
          dry-run: ${{ github.event.inputs.dry_run || 'false' }}
          ignore: |
            .DS_Store
            *.bak
```

**Notes the executor must not second-guess:**

- **CI gate is load-bearing (DECIDED 2026-04-11).** The `needs: [backend-ci, frontend-ci, bot-ci]` chain in the `publish` job is the primary gate — the wiki-publish step will not run unless the full CI pipeline passes on the same commit. The `paths: wiki/**` trigger filter is an *additional* optimization to avoid unnecessary runs when only non-wiki files change, but the `needs:` chain is the correctness guarantee. Job names `backend-ci`, `frontend-ci`, `bot-ci` match the actual job names in `.github/workflows/ci.yml` (verified at plan-write time).
- `permissions: contents: read` is the only permission needed on the main repo — the wiki write is authenticated by `WIKI_PAT`, not by `GITHUB_TOKEN`.
- Pin the action to `@v4` (not `@main`), so a breaking change to the action cannot silently break the wiki publish. Bump the version in a follow-up PR when needed.
- Do not add a `schedule:` trigger. The wiki should only ever update from `main` branch pushes, so a drift between the repo `wiki/` folder and the actual wiki is always self-healing.
- `dry_run` as a `workflow_dispatch` input lets the executor validate the workflow without publishing during the first test run (see section 11).

---

## 5. Decision 2 — `wiki/` folder structure and file names

GitHub Wiki uses `Page-Name.md` with hyphens where the page title has spaces. Sidebar file is `_Sidebar.md`, footer file is `_Footer.md`. Home page is `Home.md`.

### Files in `wiki/` after execution

```
wiki/
├── Home.md
├── Getting-Started.md
├── Self-Host-on-Azure.md
├── Self-Host-on-Any-VPS.md
├── FAQ.md
└── _Sidebar.md
```

**No `_Footer.md` for now.** Footer is optional; adding one creates a maintenance burden without clear reader value at five pages. Revisit if the wiki grows.

**Page name rationale:**

- `Self-Host-on-Azure` and `Self-Host-on-Any-VPS` (not `Self-Host-Azure` / `Self-Host-Anywhere`) — the "on" preposition matches the README section voice ("Any VPS / Docker Compose"), and "Any-VPS" is discoverable via GitHub's page search box.
- `Getting-Started` (not `Getting-started` or `Quick-Start`) — matches the conventional wiki page name across hundreds of other OSS projects, maximizing the chance a stranger types the right URL.
- `FAQ` (not `FAQ-Troubleshooting` or `Frequently-Asked-Questions`) — short, memorable, fits in the sidebar.

### `_Sidebar.md` content

```markdown
**Siege Assignments**

- [Home](Home)
- [Getting Started](Getting-Started)

**Self-hosting**

- [Self-Host on Azure](Self-Host-on-Azure)
- [Self-Host on Any VPS](Self-Host-on-Any-VPS)

**Help**

- [FAQ](FAQ)

---

[GitHub repo](https://github.com/cbeaulieu-gt/siege-web) · [Issues](https://github.com/cbeaulieu-gt/siege-web/issues)
```

Use relative wiki links (`[Home](Home)`) in the sidebar — GitHub wiki resolves these. Use absolute GitHub URLs for main-repo links and external links.

---

## 6. Decision 3 — `docs/self-host/*` disposition: stubs (DECIDED 2026-04-11)

**Decision locked:** replace `docs/self-host/azure.md` and `docs/self-host/anywhere.md` with one-line redirect stubs pointing at the wiki URLs. Deletion is not on the table.

### Pick: redirect stubs

Reasons, in order of importance:

1. **Four external references already point at `blob/main/docs/self-host/*.md`.** `README.md`, `infra/README.md`, `frontend/src/pages/LandingPage.tsx`, and its test suite all link at those exact paths. Section 2 enumerates them. The executor *will* update README, infra/README, and LandingPage.tsx + its test as part of this migration. But there may be *external* stale links — bookmarks, old PR descriptions, old Discord messages — that are outside the repo's control. A 404 on a bookmark is a worse user experience than a one-line stub that redirects in the reader's head ("oh, the doc moved to the wiki").
2. **Stubs are free.** Two two-line files. They impose no maintenance cost and no search-index noise because GitHub does not index markdown files inside `docs/` the way it indexes `README.md` and wiki pages.
3. **Stubs preserve escape hatches.** Self-host docs are semi-version-locked to the codebase; a break-glass revert to `docs/` is easier if the directory still exists.
4. **The `grep` search for references to `docs/self-host/*` in this repo is conclusive but cannot prove the absence of external references.** The conservative call is "leave a tombstone."

### Exact stub content

Both files become identical two-line redirects. The stubs are not pretty, but they are unambiguous:

**`docs/self-host/azure.md`**:

```markdown
# Self-Host on Azure

This page has moved to the project wiki: **https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure**
```

**`docs/self-host/anywhere.md`**:

```markdown
# Self-Host on Any VPS

This page has moved to the project wiki: **https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Any-VPS**
```

That is the entire content of each file post-migration. No sub-headings, no table of contents, no explanatory prose, no "here's why we moved this" — those belong in the PR description, not the stub.

### The `docs/self-host/` directory stays

Do not delete the directory. Do not add a `README.md` inside `docs/self-host/` explaining the move — the two stubs are enough.

---

## 7. Decision 4 — README.md updates: exact diff

The README "Run it yourself" section currently lives at lines 124–127. Replace those lines with the following, keeping the same heading:

**Current (`README.md:124-127`):**

```markdown
## Run it yourself

- **Azure (managed path)** — Container Apps + Key Vault + PostgreSQL Flexible Server. See [docs/self-host/azure.md](docs/self-host/azure.md).
- **Any VPS / Docker Compose** — any Linux host that runs Docker, with Caddy for free TLS and optional Cloudflare Tunnel if you can't open ports. See [docs/self-host/anywhere.md](docs/self-host/anywhere.md).
```

**After migration:**

```markdown
## Run it yourself

Full self-host guides live in the [project wiki](https://github.com/cbeaulieu-gt/siege-web/wiki):

- **[Self-Host on Any VPS](https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Any-VPS)** — any Linux host that runs Docker, with Caddy for free TLS and an optional Cloudflare Tunnel path if you can't open ports. The portable path — no cloud account required.
- **[Self-Host on Azure](https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure)** — Container Apps + Key Vault + PostgreSQL Flexible Server, with a GitHub Actions deploy pipeline. The managed, hands-off path.

New to the project? Start at **[Getting Started](https://github.com/cbeaulieu-gt/siege-web/wiki/Getting-Started)** in the wiki.
```

**Rationale for the voice change:**

- Reorders to put "Any VPS" first (matches `anywhere.md`'s framing as the default path — Azure is a specialization).
- Adds the wiki umbrella link at the top so a reader sees the wiki exists at all before they see page-specific links.
- Adds the "Getting Started" pointer at the bottom, which is the landing zone for the wiki's newest audience.
- Uses `wiki/<Page-Name>` URL form (not `wiki/<Page-Name>.md`) — this is the canonical GitHub wiki URL shape.

No other README sections change.

---

## 8. Decision 5 — Other in-repo references

### `infra/README.md:5`

**Current:**

```markdown
> For a complete end-to-end deployment walkthrough (prerequisites, resource-group setup, secret population, GitHub Actions wiring, DNS, and smoke test), see [docs/self-host/azure.md](../docs/self-host/azure.md).
```

**After migration:**

```markdown
> For a complete end-to-end deployment walkthrough (prerequisites, resource-group setup, secret population, GitHub Actions wiring, DNS, and smoke test), see the [Self-Host on Azure wiki page](https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure).
```

### `frontend/src/pages/LandingPage.tsx` (lines 407 and 431)

Both `href` values change to wiki URLs. Current values (verified in the source):

- `https://github.com/cbeaulieu-gt/siege-web/blob/main/docs/self-host/anywhere.md` → `https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Any-VPS`
- `https://github.com/cbeaulieu-gt/siege-web/blob/main/docs/self-host/azure.md` → `https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure`

No other props or behavior change. Card layout, `data-testid`, `target="_blank"`, and `rel="noopener noreferrer"` all stay.

### `frontend/src/test/components/LandingPage.test.tsx` (lines 114 and 118)

The two `expect` assertions that currently assert `blob/main/docs/self-host/anywhere.md` and `blob/main/docs/self-host/azure.md` get their expected URLs updated to the two wiki URLs above. This is a mechanical replacement — one string swap per test line.

### Everything else in the repo

Confirmed via grep: no other source file, config file, or documentation file references `docs/self-host/*`. `docs/plans/public-launch-self-hostable-and-landing-page.md` mentions the paths as historical artifacts of the Issue 2/Issue 3 sequence; those are narrative references in a plan doc and do **not** need updating. Plans are frozen records of what was intended at the time — do not edit them.

---

## 9. Decision 6 — Wiki bootstrapping: manual click-path

GitHub does not create `siege-web.wiki.git` until the Wiki feature is enabled **and** the first page is created via the web UI. Until both steps are done, `git clone https://github.com/cbeaulieu-gt/siege-web.wiki.git` returns 404 and the wiki-publish Action will fail on its first run.

**Manual steps (the executor must instruct the repo owner to do these before the first merge to `main` that includes `wiki/` files):**

1. Go to `https://github.com/cbeaulieu-gt/siege-web` → **Settings** → **General** → scroll to **Features** → ensure **Wikis** is checked. *(Confirm also that "Restrict editing to collaborators only" is checked — this should be the default for private-ish project wikis and matches the #189 direction.)*
2. Back on the main repo page, click the **Wiki** tab → click **Create the first page** → title it **Home** → paste any placeholder content (literally "bootstrap" is fine — it will be overwritten on the first Action run) → click **Save Page**. This is the step that actually creates `siege-web.wiki.git` under the hood.
3. Generate the `WIKI_PAT` classic PAT: `https://github.com/settings/tokens` → **Generate new token (classic)** → scopes `repo` (full) → no expiry → copy the token.
4. In the repo: **Settings** → **Secrets and variables** → **Actions** → **New repository secret** → name `WIKI_PAT` → value: the token from step 3.

**What the Action handles automatically once bootstrapped:**

- Cloning the wiki git repo, copying `wiki/*` contents, committing with a message derived from the main-repo commit, and pushing to `siege-web.wiki.git`.
- Deleting pages whose files disappeared from `wiki/` since the last push.
- Writing `_Sidebar.md` as an ordinary wiki file.

**What the Action does NOT handle:**

- Enabling the Wiki feature.
- Creating the first page.
- Rotating the PAT.
- Merging conflicting edits made directly through the wiki web UI by a collaborator. Because canonical authorship is in `wiki/`, any direct-wiki-UI edit will be silently overwritten on the next push to `main` that touches `wiki/`. Document this in the wiki's Home page ("edit these pages by opening a PR against `wiki/` in the main repo") so collaborators do not lose work.

---

## 10. Decision 7 — Content rewrites: verdict per page

### `Self-Host-on-Azure.md` (from `docs/self-host/azure.md`)

**Verdict: publish verbatim, with exactly one edit.**

Read-through of the full 456-line `docs/self-host/azure.md` confirms:

- Voice is already human-oriented, not agent-oriented. No `@` citations, no grep pointers, no "TODO" blocks, no agent conventions.
- The opening paragraph already self-describes as a wiki-appropriate narrative ("managed, hands-off path"). No framing rewrite needed.
- The one relative link in the file, `[anywhere.md](./anywhere.md)` at line 3, breaks in the wiki because wiki pages have no relative-file concept. **This is the one edit:** replace `[anywhere.md](./anywhere.md)` with `[Self-Host on Any VPS](Self-Host-on-Any-VPS)` (wiki-relative link), and replace `[docs/RUNBOOK.md](../RUNBOOK.md)` at line 396 with `[RUNBOOK.md in the main repo](https://github.com/cbeaulieu-gt/siege-web/blob/main/docs/RUNBOOK.md)` (absolute link, because RUNBOOK stays in `docs/`).
- The table of contents anchor links (`#1-prerequisites` etc.) work in GitHub wiki unchanged — wiki pages auto-generate the same slugified anchors that GitHub-flavored markdown does in regular files. Do not touch them.
- No images referenced, no broken cross-doc pointers other than the two links above.

**That is the entire rewrite.** Two links. Do not restructure sections, do not rewrite prose, do not "wiki-ify" the tone — it's already there.

### `Self-Host-on-Any-VPS.md` (from `docs/self-host/anywhere.md`)

**Verdict: publish verbatim, with four edits (not three — corrected count).**

Read-through of the full 571-line `docs/self-host/anywhere.md` confirms the same story as `azure.md`:

- Wiki-appropriate voice throughout.
- Same anchor-link compatibility (no action needed).
- Four relative links break and must be rewritten:
  1. Line 3: `[azure.md](./azure.md)` → `[Self-Host on Azure](Self-Host-on-Azure)`
  2. Line 82: `[Section 3 of azure.md](./azure.md#3-register-a-discord-application)` → `[Section 3 of the Azure guide](Self-Host-on-Azure#3-register-a-discord-application)`
  3. Line 535: `[docs/RUNBOOK.md](../RUNBOOK.md)` → `[RUNBOOK.md in the main repo](https://github.com/cbeaulieu-gt/siege-web/blob/main/docs/RUNBOOK.md)`
  4. Line 570: `[azure.md](./azure.md)` → `[Self-Host on Azure](Self-Host-on-Azure)`

Do each by hand to avoid edit-tool over-match on shared substrings.

### Shared verdict rationale

Intentionally decided against a tone rewrite. The existing self-host docs were already written for a human audience during the Issue 2 and Issue 3 work in the public-launch milestone — that plan explicitly targeted "a Raid clan leader who finds the repo" as audience. They are wiki-ready because they were written wiki-ready. A tone-rewrite pass would create pointless diff noise and would risk introducing bugs in a 400+ line `az deployment group create` walkthrough. Move them as-is, fix the links, ship.

### `Home.md` (new)

Skeleton — the executor expands this during execution into 2–4 paragraphs matching README voice.

```markdown
# Siege Assignments

A web app for managing Raid Shadow Legends clan siege assignments. Replaces the Discord-plus-Excel workflow with a unified web UI backed by a relational database. Open source, self-hostable, and free.

## Who this is for

Clan leaders and planners who coordinate siege building assignments for their guild, plus developers curious about the stack (React + FastAPI + a Discord bot sidecar).

## Start here

- **Want to try it locally in 5 minutes?** [Getting Started](Getting-Started)
- **Ready to self-host for your clan?** Pick a path:
  - [Self-Host on Any VPS](Self-Host-on-Any-VPS) — any Linux host that runs Docker. No cloud account.
  - [Self-Host on Azure](Self-Host-on-Azure) — managed Container Apps, Key Vault, PostgreSQL Flexible Server.
- **Run into something unexpected?** [FAQ](FAQ)

## About this wiki

This wiki is mirrored from the `wiki/` folder in the [main repo](https://github.com/cbeaulieu-gt/siege-web). To edit a page, open a PR against `wiki/<Page-Name>.md` — direct edits through the wiki web UI will be overwritten on the next publish. Pull requests are reviewed, merged to `main`, and auto-published by a GitHub Action within a minute or two.
```

### `Getting-Started.md` (new)

Skeleton — the executor expands to ~200 words matching README Quick Start voice.

````markdown
# Getting Started

Get a populated local instance of Siege Assignments running in under 5 minutes. No Discord account needed — the default dev profile runs in demo mode with pre-seeded data and authentication disabled.

## What you need

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- A terminal

That is the entire dependency list. Python, Node.js, and a Discord bot token are only needed if you want to run services outside Docker or try the real OAuth flow.

## Clone, configure, run

```bash
git clone https://github.com/cbeaulieu-gt/siege-web.git
cd siege-web
cp .env.example .env
docker-compose up --build
```

When the logs settle, open http://localhost:5173. The app loads with 25 demo members and an active siege already populated. A thin amber banner at the top confirms you are in demo mode.

## What's next?

- **Host it for your clan:** [Self-Host on Any VPS](Self-Host-on-Any-VPS) (start here — no cloud account needed) or [Self-Host on Azure](Self-Host-on-Azure) (managed path).
- **Something unexpected?** Check the [FAQ](FAQ).
- **Want to contribute?** The [main repo's README](https://github.com/cbeaulieu-gt/siege-web#readme) has the dev loop, test commands, and linting setup.
````

### `FAQ.md` (new, skeleton only)

Intentionally tiny. Real FAQ entries land post-launch as real questions arrive. Do not invent questions nobody has asked.

```markdown
# FAQ

Common questions and troubleshooting tips. Most real troubleshooting content for self-hosters lives in [Self-Host on Any VPS → Troubleshooting](Self-Host-on-Any-VPS#9-troubleshooting) — start there for Discord OAuth, Postgres, session secret, and Playwright issues.

## General

### Is this project affiliated with Plarium or Raid Shadow Legends?

No. This is an unaffiliated open-source community tool. It reads clan data that you provide (Discord user IDs, siege assignments) and talks to your own Discord server via a bot you register yourself. It does not connect to Plarium game servers and does not touch any proprietary game data.

### Can I use this without Discord?

Not currently. The app is built around Discord OAuth2 for sign-in and a Discord bot for notifications. Removing that dependency is a significant refactor and is not on the roadmap.

### How do I report a bug or ask for a feature?

Open a [GitHub Issue](https://github.com/cbeaulieu-gt/siege-web/issues) on the main repo.

## Self-hosting

### Which self-host path should I pick?

If you already have a VPS or a home server that runs Docker, pick **[Self-Host on Any VPS](Self-Host-on-Any-VPS)**. It's the faster path and costs nothing beyond your existing hosting. Pick **[Self-Host on Azure](Self-Host-on-Azure)** only if you want Azure to manage TLS, backups, secrets, and scaling for you.

### Where do Discord bot tokens and other secrets live?

Never in `.env` files committed to git. On a VPS deployment, secrets live in `.env.production` (chmod 600). On Azure, secrets live in Key Vault and are injected into Container Apps via managed identity — see the Azure guide.

---

*Have a question that isn't covered here? Open an issue on the main repo and it will probably land in this FAQ.*
```

---

## 11. Decision 8 — Images and assets

**Verdict: no images move. Policy documented for future.**

Neither self-host doc references any image, screenshot, diagram, or binary asset. Confirmed by grep for `![`, `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`, and `docs/assets` under `docs/self-host/`. The new Home, Getting Started, and FAQ skeletons also do not reference any image.

**Policy for any future wiki page that needs images:**

1. Image file lives in `docs/assets/wiki/<page-slug>/<filename>.png` in the main repo. Commit the binary there.
2. In the wiki markdown, reference it via the absolute `raw.githubusercontent.com` URL: `![alt text](https://raw.githubusercontent.com/cbeaulieu-gt/siege-web/main/docs/assets/wiki/<page-slug>/<filename>.png)`.
3. Do **not** upload images as wiki attachments through the wiki web UI. Attachments are not mirrored by the `wiki/` folder, they live in `.wiki.git` history only, and they will be silently deleted the next time the action publishes. If someone uploads an attachment through the UI, open an issue and migrate it to `docs/assets/wiki/` before it gets overwritten.

Add this policy to the `Home.md` "About this wiki" paragraph in a follow-up if the first image-needing page arrives — not now, because YAGNI.

---

## 12. Decision 9 — Execution ordering (step-by-step)

**Branch:** `docs/wiki-migration`. Cut from `main` *after* v1.0 has shipped and #187 and #188 have merged. Do not cut this branch before those land — it touches `README.md` and will conflict.

The ordering below is designed so that a pause between any two steps leaves the repository in a valid state. The executor does not have to run steps atomically.

**Step 0 — manual prerequisites (repo owner, not the executor):**

- [ ] v1.0 has shipped (#173–#176 closed)
- [ ] #187 (docs freshness pass) merged
- [ ] #188 (community health files) merged
- [ ] Wiki feature enabled and first page manually created (section 9)
- [ ] `WIKI_PAT` secret added to repository secrets (section 9)

The executor confirms these before starting and stops if any are unsatisfied.

**Step 1 — branch and working directory:**

- [ ] `git pull origin main`
- [ ] `git checkout -b docs/wiki-migration`
- [ ] Confirm the worktree is clean.

**Step 2 — create the `wiki/` folder and populate it:**

- [ ] `mkdir wiki/`
- [ ] Create `wiki/Self-Host-on-Azure.md` as a copy of `docs/self-host/azure.md`, then apply the two link fixes from section 10.
- [ ] Create `wiki/Self-Host-on-Any-VPS.md` as a copy of `docs/self-host/anywhere.md`, then apply the four link fixes from section 10.
- [ ] Create `wiki/Home.md` using the skeleton from section 10. Expand to 2–4 paragraphs in the executor's voice matching the README. Cap at ~300 words.
- [ ] Create `wiki/Getting-Started.md` using the skeleton from section 10. Expand to ~200 words.
- [ ] Create `wiki/FAQ.md` using the skeleton from section 10 verbatim. Do not invent FAQ questions.
- [ ] Create `wiki/_Sidebar.md` using the content from section 5 verbatim.
- [ ] `git add wiki/` and `git commit -m "docs(wiki): add canonical wiki content in wiki/"`

**Step 3 — add the publish workflow:**

- [ ] Create `.github/workflows/wiki-publish.yml` using the YAML from section 4 verbatim.
- [ ] `git add .github/workflows/wiki-publish.yml` and `git commit -m "ci: add wiki publish workflow"`

**Step 4 — replace `docs/self-host/*` with redirect stubs:**

- [ ] Overwrite `docs/self-host/azure.md` with the two-line stub from section 6.
- [ ] Overwrite `docs/self-host/anywhere.md` with the two-line stub from section 6.
- [ ] `git add docs/self-host/` and `git commit -m "docs: replace self-host docs with wiki redirect stubs"`

**Step 5 — update README.md:**

- [ ] Apply the "Run it yourself" section change from section 7 verbatim.
- [ ] `git add README.md` and `git commit -m "docs: point README self-host section at wiki"`

**Step 6 — update `infra/README.md`:**

- [ ] Apply the line-5 change from section 8.
- [ ] `git add infra/README.md` and `git commit -m "docs: point infra README at Azure wiki page"`

**Step 7 — update the landing page:**

- [ ] Edit `frontend/src/pages/LandingPage.tsx` lines 407 and 431 to the two wiki URLs from section 8.
- [ ] Edit `frontend/src/test/components/LandingPage.test.tsx` lines 114 and 118 to match.
- [ ] Run the frontend test suite locally: `cd frontend && npm test -- LandingPage`. The two updated tests must pass.
- [ ] `git add frontend/` and `git commit -m "feat(frontend): point landing page self-host cards at wiki"`

**Step 8 — push and open PR:**

- [ ] `git push -u origin docs/wiki-migration`
- [ ] Open PR against `main`. Title: `Migrate human-facing docs to GitHub Wiki`. Body: summary, reference to #189, the two CLAUDE.md verification lines from section 2, and a note that the `wiki-publish.yml` first run will be triggered manually in dry-run mode after merge.

**Step 9 — CI verification on the PR:**

- [ ] Existing CI (backend, frontend, infra-ci) passes.
- [ ] The new `wiki-publish.yml` workflow does **not** run on the PR because its trigger is `push: branches: [main]`, not `pull_request:`. This is intentional — we do not want wiki pushes to happen from a PR branch.
- [ ] Reviewer checks: wiki folder file names match `_Sidebar.md`, no dangling `../docs/self-host` links, README section reads cleanly.

**Step 10 — merge and first real publish:**

- [ ] Merge the PR with a merge commit (not a squash) so the individual file-class commits from steps 2–7 are preserved in history.
- [ ] After the merge lands on `main`, the `wiki-publish.yml` workflow fires automatically (because `paths: wiki/**` matches the merged diff).
- [ ] Watch the workflow run in the Actions tab. Expected result: green, with log output showing X files mirrored to the wiki.
- [ ] If the first run fails, see section 13 for the recovery procedure.

**Step 11 — delete the branch** (locally and on the remote) once merged.

**Do NOT do these things:**

- Do not squash-merge. The five-commit history is useful for future archaeology.
- Do not force-push to `docs/wiki-migration` after the first push unless you are fixing a review comment.
- Do not manually push to `siege-web.wiki.git` from your laptop to "pre-bootstrap" the wiki beyond the manual Home-page step in section 9. The Action expects to be the only author.

---

## 13. Decision 10 — Testing and verification

The migration is successful if and only if all of the following are observable post-merge:

**Wiki pages reachable at the expected URLs:**

- [ ] `https://github.com/cbeaulieu-gt/siege-web/wiki/Home` loads, renders markdown, and shows the sidebar.
- [ ] `https://github.com/cbeaulieu-gt/siege-web/wiki/Getting-Started` loads.
- [ ] `https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Azure` loads. All internal anchor links (`#1-prerequisites`, `#2-fork-the-repo-and-configure-github`, ...) work. The link to "Self-Host on Any VPS" at the top goes to the wiki page, not a 404.
- [ ] `https://github.com/cbeaulieu-gt/siege-web/wiki/Self-Host-on-Any-VPS` loads. All four external/cross-wiki links work. The link to "Section 3 of the Azure guide" resolves to the right section.
- [ ] `https://github.com/cbeaulieu-gt/siege-web/wiki/FAQ` loads.
- [ ] The sidebar is visible on every page, not just `Home`.

**Main-repo link integrity:**

- [ ] `README.md` "Run it yourself" links click through to the wiki without a 404.
- [ ] `infra/README.md` line 5 link works.
- [ ] `docs/self-host/azure.md` and `docs/self-host/anywhere.md` both exist, both are exactly two lines of markdown, and both name the correct wiki URL.
- [ ] The deployed landing page's two "Self-host guide" buttons link to the wiki URLs. (Verified by hitting the deployed frontend — not just the unit test.)

**CI and Action health:**

- [ ] The backend, frontend, and infra-ci workflows all pass on the merge commit.
- [ ] The first run of `wiki-publish.yml` on `main` after merge is green.
- [ ] The second test: the executor makes a trivial edit to `wiki/FAQ.md` (add and immediately remove a period), opens a PR, merges it, and confirms that the second run of `wiki-publish.yml` is also green. This is the "does it work twice" check that catches PAT auth failures that look OK on the first run.

**Direct editing protection:**

- [ ] The executor logs in to the wiki web UI, edits `Home` through the UI with a "TEST — will be overwritten" line, and saves. Then makes any trivial commit touching `wiki/` on `main`. Confirms: on the next `wiki-publish.yml` run, the UI edit is silently overwritten by the `wiki/Home.md` content from the repo. This validates the "canonical authorship in repo" invariant and provides empirical evidence to show anyone who asks "can't I just edit the wiki directly?"

**CLAUDE.md verification:**

- [ ] Re-run the grep from section 2 after merge. Both files still contain zero references to any wiki-bound doc. Record the result in the PR's closing comment.

### Recovery: what if the first wiki-publish run fails?

Most likely failure modes and fixes:

1. **`fatal: could not read Username for 'https://github.com': No such device or address`** — PAT not configured or not passed to the action. Re-check the `WIKI_PAT` secret, confirm the workflow input name matches `token:` (not `github_token:`), re-trigger via `workflow_dispatch`.
2. **`fatal: repository 'https://github.com/cbeaulieu-gt/siege-web.wiki.git/' not found`** — Wiki not bootstrapped. Go through section 9 steps 1–2 again. Then re-trigger the workflow.
3. **`refusing to update checked out branch: refs/heads/master`** — `Andrew-Chen-Wang/github-wiki-action` has historically used `master` as the wiki repo default branch. If you see this, check the action's current docs and supply the correct branch input.
4. **Action runs green but wiki pages do not update** — cache-layer weirdness on GitHub's wiki renderer. Hard-refresh the wiki page and wait ~60 seconds. If still stale, inspect the action's logs for the actual commit SHA it pushed and verify that commit appears in `siege-web.wiki.git` history (accessible via `git clone` to your laptop for a one-off check).
5. **Workflow did not trigger at all on merge** — verify the `paths: wiki/**` filter is correct in the trigger config and that the merge commit actually touched files under `wiki/`. A merge that did not touch `wiki/` will legitimately skip the workflow.

---

## 14. Owner decisions — RESOLVED 2026-04-11

All five open questions from the original draft have been answered by the owner. Decisions are locked. The executor follows these without re-opening them.

---

**Q1 — Auth mechanism for `WIKI_PAT`**

> *Original question:* Classic PAT vs. fine-grained PAT vs. GitHub App installation token?

**DECIDED: classic PAT.** Accepted as tech debt. A future hardening pass may swap it for a GitHub App installation token; file a follow-up issue at execution time titled *"Migrate wiki-publish auth from classic PAT to GitHub App."* See section 4 for the full PAT rationale and provisioning instructions.

---

**Q2 — CI gating on the `wiki-publish` workflow**

> *Original question:* Is the `paths: wiki/**` trigger filter a sufficient gate, or does the executor want the strict `needs:` chain that #189 called out?

**DECIDED: strict CI gate.** The `wiki-publish` job must run only on push to `main` AND must chain behind the full CI pipeline via `needs: [backend-ci, frontend-ci, bot-ci]` (the actual job names from `.github/workflows/ci.yml`, verified at plan-write time). A `paths: wiki/**` filter is also applied to reduce unnecessary runs, but the `needs:` chain is the load-bearing gate. See section 4 for the updated workflow YAML.

---

**Q3 — `docs/self-host/*` disposition**

> *Original question:* Delete the files outright, or replace with redirect stubs?

**DECIDED: stubs.** `docs/self-host/azure.md` and `docs/self-host/anywhere.md` become one-line redirect stubs pointing at the wiki. Deletion is not on the table. See section 6 for the exact stub content.

---

**Q4 — Page count at launch**

> *Original question:* Five pages, or does the owner want a sixth page (Roadmap, Architecture, Contributing, etc.) in scope for the first migration PR?

**DECIDED: five pages at launch.** Home, Getting Started, Self-Host on Azure, Self-Host on Any VPS, FAQ. No additional pages in this migration. Any further wiki pages are separate post-launch issues.

---

**Q5 — `Home.md` vs. README voice**

> *Original question:* Should `Home.md` mirror the README voice (developer-first), or should it be user-facing with a deliberate split from the README?

**DECIDED: split.** README stays developer-facing ("clone, run, contribute"). `Home.md` stays user-facing ("what is this, how do I use it"). Do not mirror README content into Home. The two documents serve different audiences and intentional drift between them is acceptable.

---

**Standing risks (informational — not re-opened)**

**Risk 1 — classic PAT lifecycle.** Classic PATs with `repo` scope are long-lived, unscoped secrets tied to the owner's account. If the owner's account is compromised or the PAT is leaked, the blast radius is "everything in every repo the owner has write access to," not just the wiki. Q1 above accepted this as tech debt; the mitigation path is the follow-up GitHub App issue.

**Risk 2 — `_Sidebar.md` relative wiki links are GitHub-wiki-specific syntax.** Previewing `wiki/_Sidebar.md` in the main repo (via the GitHub file viewer or a local markdown preview) will render the link as broken. That is expected — the file is authored for the wiki rendering context. Do not "fix" this by converting to absolute URLs.

**Risk 3 — external stale links.** Section 6 picked redirect stubs over deletion exactly because this risk is real. There is no way to measure it from inside the repo; the conservative default stands.

**Risk 4 — Getting-Started skeleton duplicates README content.** Intentional. The README Quick Start targets developers who cloned the repo; the wiki Getting Started targets strangers who haven't cloned yet. Drift between the two is self-correcting.

---

## 15. Out of scope for this migration (re-listed to prevent scope creep)

- Adding Roadmap, Contributing, Architecture, or any wiki page beyond the five in #189.
- Writing real FAQ content beyond the two skeleton questions.
- Replacing Discord OAuth with any other auth mechanism.
- Moving RUNBOOK.md into the wiki. RUNBOOK is an operational doc for an authenticated operator, not a wiki-appropriate narrative.
- Moving `WEB_DESIGN_DOCUMENT.md` into the wiki. Agent-context dev doc.
- Rewriting any existing section 2 Discord Developer Portal walkthrough into a standalone "Register a Discord App" wiki page that both self-host pages can share. The current cross-reference from `anywhere.md` to `azure.md` (section 2 → section 3) works fine as a wiki-internal link after the one-line fix in section 10.
- Non-English translations.
- Opening up wiki write permissions to non-collaborators.
