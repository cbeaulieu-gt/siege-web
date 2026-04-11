# Public launch: self-hostable + landing page

**Milestone:** `Public launch: self-hostable + landing page`
**Status:** In Progress — Issues 1 and 4 shipped; Issues 2, 3, and 5 not yet started
**Supersedes:** The previously-planned `UX Polish` milestone. The scope grew beyond polish once the three-audience framing landed, so the milestone is being renamed rather than UX-polish work being added onto an existing milestone. No other plan docs conflict with this one.

---

## Pre-flight findings (updated to reflect current state)

A quick sweep of the repo surfaced a few things worth calling out before the work starts. **Several of the original findings have since shipped as part of the v1.0 RC work** — those are noted below.

- **~~`frontend/src/pages/HomePage.tsx` is confirmed dead code.~~** *(Shipped — Issue 4 is complete.)* `frontend/src/pages/LandingPage.tsx` now exists and is live at `/`. The `LandingOrSieges` component in `App.tsx` handles the authenticated-user redirect to `/sieges`. The original dead `HomePage.tsx` has been removed. No remaining action needed for the routing concern.
- **~~`.env.example` has `AUTH_DISABLED=true` commented out at the bottom with a scary warning.~~** *(Shipped — Issue 1 is complete.)* `.env.example` is now organized into three clearly-labeled tiers. `AUTH_DISABLED=true` is uncommented and is the dev default, with an inline comment explaining demo/dev mode. `SESSION_SECRET` has an inline comment stating the backend refuses to start without it. The three-tier grouping (required for any run / real OAuth only / Azure-only) is in place.
- **~~There is no seed script anywhere in `backend/`.~~** *(Shipped — Issue 1 is complete.)* `backend/scripts/seed_demo.py` exists and can be run on boot to populate demo data.
- **`docs/plans/` did not exist before this doc.** I created it as part of writing this. *(Still true — `docs/plans/` now exists and this file is in it.)*
- **No existing competing plan.** `docs/IMPLEMENTATION_PLAN.md` covers the original app build (phases 0–9) and does not speak to public launch. `docs/STATUS.md` is a running status file, not a plan. Nothing needs to be superseded other than the `UX Polish` milestone rename. *(Still accurate.)*

**Remaining open issues for this milestone:** Issues 2, 3, and 5 are not yet started. Issue 4 (landing page) and Issue 1 (local dev onboarding) are shipped.

---

## 1. Overview

This initiative turns Siege Assignments from "higgsbp's clan's internal tool that happens to be open source" into a public-facing, credibly self-hostable project. The work has three halves that stay in sync: (a) make the local dev experience so smooth that a stranger who clones the repo is clicking around a populated demo UI inside five minutes, (b) write cloud-agnostic self-host docs so other clan leaders can realistically run it on a $5 VPS without touching Azure, and (c) ship a landing page at `/` that reframes the project as both a portfolio artifact and a tool other people can pick up.

## 2. Goals

- **Portfolio advertisement.** The deployed instance at `higgsbp`'s URL presents the project well enough to recruiters and other developers that it reads as a finished product, not a work-in-progress.
- **Credible self-host story.** A Raid clan leader who finds the repo can stand up their own instance — on a VPS, a home server, or Azure — without asking a single question of the maintainer and without any cloud-specific lock-in.
- **Clan member sign-in that still feels like home.** Existing Master's Of Magicka members sign in on the canonical instance with the same Discord OAuth flow they already know, and the landing page makes it obvious which button is theirs.
- **Low-friction local evaluation.** Anyone — recruiter, clan leader, curious developer — can evaluate the tool in under five minutes with zero external account setup.

## 3. Non-goals

- **Mobile-optimizing the main application.** The board, post list, and member management screens remain desktop-first. The login page gets a mobile warning banner (Issue 5); that's the extent of mobile work in this milestone.
- **Kubernetes / Helm / Nomad / ECS / Fly.io / Render deploy paths.** Only two host profiles are documented: generic Docker Compose (Issue 2) and Azure Container Apps (Issue 3). Other runtimes can be added later if demand appears.
- **Multi-tenant hosting.** Each self-hosted instance is a single clan. No work toward tenant isolation, per-clan subdomains, or a hosted "sign up and get a clan" SaaS mode.
- **i18n.** English-only.
- **Landing page A/B testing, analytics, or email capture.** Ship a static marketing page, not a growth funnel.
- **Rewriting the Discord OAuth flow.** Issue 5 is a polish pass on the login page, not a redesign of the auth mechanism.
- **Blog, changelog, or docs site.** Markdown in `docs/` remains the only documentation surface.

## 4. Work breakdown

### Issue 1 — Local dev onboarding polish ✓ SHIPPED

**Summary.** Make `git clone && cp .env.example .env && docker-compose up` produce a working, populated demo UI inside five minutes with zero Discord setup. This is the foundation for every other issue in the milestone — the landing page, the self-host docs, and the login polish all assume a dev can get to a running instance fast.

**Acceptance criteria.**
- [ ] `.env.example` has `AUTH_DISABLED=true` uncommented as the default for the dev profile, with a short inline comment explaining that this is the demo/dev mode and that real deployments must set it to `false` (or remove it).
- [ ] `.env.example` is reorganized into three clearly-labeled tiers: (1) required for any run (DB URL, session secret, auth flag), (2) required only when running with real Discord OAuth (client ID/secret/redirect, bot token, guild ID, channels), (3) Azure/deploy-only (anything used by Bicep or the deploy workflow).
- [ ] `SESSION_SECRET` has an inline comment stating that the backend refuses to start without it and giving a one-line command to generate a secure value.
- [ ] A backend seed script exists (e.g. `backend/scripts/seed_demo.py`) that idempotently creates a demo clan's worth of members, one demo siege with members assigned to most building positions, and a handful of post priority examples. Running it twice does not create duplicates.
- [ ] The seed script runs automatically on `docker-compose up` for the default dev profile — either via an entrypoint hook, a dedicated one-shot service in the compose file, or an `alembic upgrade head && python scripts/seed_demo.py` chain. Decide which during implementation.
- [ ] Frontend shows a persistent "Demo mode — authentication disabled" banner (non-dismissible, small, top-of-viewport or in the nav) whenever the backend reports `AUTH_DISABLED=true`. Backend exposes this via an existing or new config endpoint.
- [ ] README Quick Start section rewritten to reflect reality: clone, copy env, compose up, open browser, click around. No mention of Discord setup in Quick Start — that moves to the self-host docs.
- [ ] A new dev following *only* the rewritten Quick Start on a clean machine reaches a populated UI in under 5 minutes. Owner validates this on a fresh VM or a teammate's machine before closing.

**Dependencies.** None. Must land before Issues 2, 4, and 5 begin (Issue 3 can technically start in parallel since it's just docs consolidation, but sequencing it after 1 is cleaner).

**Effort.** M. Seed script is the biggest chunk of real code; everything else is configuration and docs.

**Risks / open questions.**
- *Seed data realism.* How close should demo members mirror real clan data? Recommend: fully fictional names ("Demo Member 01"…"Demo Member 25") so there's no implication that real MoM members are being exposed in a public demo.
- *Where does the seed script run in the compose flow?* Entrypoint hook vs. dedicated one-shot service. Pick during implementation; document the choice in the issue.
- *Banner styling.* Needs to be visible without being obnoxious. A thin amber strip with text is probably enough — avoid a modal.

---

### Issue 2 — Cloud-agnostic self-host documentation (`docs/self-host/anywhere.md`)

**Summary.** A single doc that takes a developer from "I have a $5 VPS and a domain" to "I have a working Siege Assignments instance my clan can sign in to" in under 60 minutes, without ever mentioning Azure.

**Acceptance criteria.**
- [ ] `docs/self-host/anywhere.md` exists and is linked from the root README's "Run it yourself" section and from the landing page's self-host card (Issue 4).
- [ ] Doc covers: prerequisites (Docker + Docker Compose, a domain, a Discord app registered at discord.com/developers), Discord app registration walkthrough with callback URL guidance, `.env.production` variables (explicitly calling out what differs from `.env.example`), production compose overlay usage, Caddy sidecar for HTTPS termination with a minimal working `Caddyfile`, first-run steps (migrations, optionally running the seed script for testing then wiping it), and smoke-test checklist.
- [ ] A production compose overlay exists — either `docker-compose.prod.yml` applied via `-f docker-compose.yml -f docker-compose.prod.yml`, or a standalone `docker-compose.production.yml`. Decide during implementation and document the choice. The overlay differs from dev in at least: no source bind-mounts, env loaded from `.env.production`, `ENVIRONMENT=prod`, `AUTH_DISABLED` unset/false, `restart: unless-stopped` on every service, and sane resource limits (`mem_limit` or deploy resource reservations).
- [ ] Tunnel-tool alternative section documents the Cloudflare Tunnel path as the recommended alternative for someone who can't or won't open ports, including the exact `cloudflared` config needed to route to the backend on localhost and where to set the OAuth redirect URI. Tailscale Funnel and ngrok are mentioned in one paragraph each as additional options with links to their docs rather than full walkthroughs.
- [ ] Troubleshooting section covers the three most likely failure modes: Discord OAuth redirect URI mismatch, Postgres volume permission issues, and backend failing to start because `SESSION_SECRET` is missing.
- [ ] Doc explicitly states "no Azure account required" in the opening paragraph.
- [ ] Owner (or a willing stand-in) walks through the doc on a fresh $5 VPS before the issue is closed. Timing it is optional but encouraged — the 60-minute claim only goes in the doc if the walkthrough actually hits it.

**Dependencies.** Issue 1 (so the env var story is sane before it's documented).

**Effort.** L. This is a full end-to-end production hosting guide, and the Caddy + Cloudflare Tunnel sections need to be actually tested, not just written from memory.

**Risks / open questions.**
- *Caddy vs. Traefik vs. "bring your own reverse proxy."* Recommend Caddy for the worked example because its config is shortest and automatic HTTPS is the default. Mention the others only in passing.
- *Compose overlay shape.* `docker-compose.prod.yml` as an overlay is the more idiomatic Compose v2 pattern; a standalone file is easier to reason about for someone new to Compose. Slight preference for the overlay, but defer to whoever writes the issue.
- *Does the bot need to be exposed publicly?* No — only the backend's `/api/auth/callback` needs to be reachable. Make this explicit in the doc so self-hosters don't over-expose.

---

### Issue 3 — Azure self-host documentation consolidation (`docs/self-host/azure.md`)

**Summary.** Take the existing deploy workflow, Bicep modules, and Key Vault story and collapse them into one narrative doc at `docs/self-host/azure.md`, clearly framed as the "managed hands-off path" — one of several options, not the only option.

**Acceptance criteria.**
- [ ] `docs/self-host/azure.md` exists and is linked from the root README and the landing page's self-host card.
- [ ] Doc is a single narrative a reader can follow top-to-bottom: prerequisites (Azure subscription, `az` CLI), one-time resource-group setup, `az deployment group create` invocation with the Bicep entry point, secret population in Key Vault, first deploy via the GitHub Actions workflow (or a manual alternative), DNS and custom domain setup, and smoke test.
- [ ] Opening paragraph states explicitly: "This is the managed, hands-off path. If you don't want an Azure subscription, see [anywhere.md](./anywhere.md) instead."
- [ ] Any existing deploy instructions scattered across `infra/` READMEs and `.github/workflows/` comments are either moved into this doc or replaced with a one-line pointer to this doc. Goal: one canonical Azure doc, not three.
- [ ] All Azure-specific env vars are listed with their source (Key Vault secret name, Bicep output, manually set, etc.).
- [ ] A fresh read-through by someone who hasn't touched the infra before reaches a successful first deploy without clicking into workflow YAML or Bicep to figure out missing steps.

**Dependencies.** None. Can run fully in parallel with Issue 2.

**Effort.** M. Almost entirely a documentation-consolidation exercise — the infra already exists and works.

**Risks / open questions.**
- *Should this doc assume the reader has already forked the repo and will use their own GitHub Actions, or should it document a manual `az` deploy path too?* Recommend: lead with the "fork + GitHub Actions" path (matches current reality) and include a short "manual deploy" appendix for readers who want to deploy from their laptop.

---

### Issue 4 — Public landing page at `/` ✓ SHIPPED

**Summary.** Ship a public marketing page at `/` that sells the project to three audiences (recruiters, clan leaders, curious developers) and routes each one where they need to go. Delete the orphaned `HomePage.tsx`. Keep `/sieges` as the destination for authenticated users.

**Acceptance criteria.**
- [ ] The `/` route is moved *out* of the `RequireAuth` layout in `App.tsx` and renders a new `LandingPage` component. Authenticated users hitting `/` are redirected to `/sieges` — either via a guard inside the landing page component or via a sibling authenticated-only route. Pick one approach during implementation and document it.
- [ ] `frontend/src/pages/HomePage.tsx` is deleted. (Confirmed dead: only self-referenced.)
- [ ] Landing page has a top nav with a prominent "Sign in" button in the upper right that links to `/login`.
- [ ] Hero section: portfolio framing headline, open-source tagline, and a "Set it up for your clan ↓" CTA that smooth-scrolls to the self-host section.
- [ ] "What it does" section: 4–6 feature bullets (assignments, validation rules, auto-fill, Discord notifications, comparison view, image generation) plus at least one board screenshot. Screenshots live under `docs/assets/landing/` or `frontend/public/landing/` — pick one and stay consistent.
- [ ] "Under the hood" section: brief three-service architecture blurb (FastAPI + React + Discord bot), with no marketing fluff — this is the section recruiters read.
- [ ] "Run it for your own clan" section: three cards side-by-side (or stacked on narrow viewports) linking to (a) the README Quick Start for local dev, (b) `docs/self-host/anywhere.md`, (c) `docs/self-host/azure.md`. Each card has a one-line "best for …" subtitle.
- [ ] "Contact" section: Discord `higgsbp` and a GitHub repo link.
- [ ] SEO: page has a proper `<title>`, `<meta name="description">`, canonical link, and Open Graph (`og:title`, `og:description`, `og:image`) and Twitter card tags. An OG image lives in the repo and is referenced by absolute URL.
- [ ] Landing page is indexable by search engines — verified by a Lighthouse SEO audit scoring ≥90 and a manual check that meta tags show up in the built HTML (not only after hydration).
- [ ] The authenticated `/sieges` redirect behavior is unchanged from the user's perspective: a logged-in user visiting `/` lands on `/sieges`, exactly as today.
- [ ] Login flow unaffected: clicking "Sign in" from the landing page goes to `/login`, which works as it does today.

**Dependencies.** Depends on Issues 1, 2, and 3 — the landing page links to artifacts those issues produce (Quick Start section in README, the two self-host docs). It can begin drafting in parallel with 2 and 3 as long as it doesn't merge until those land.

**Effort.** L. Not because any single piece is hard, but because the SEO decision, the screenshots, the OG image, and the route restructuring each have their own rabbit holes.

**Risks / open questions.**
- *SEO rendering approach.* Covered in section 6 — needs a decision before implementation starts.
- *Screenshot freshness.* Screenshots in the landing page will drift from the real UI over time. Accept this for now; add a "refresh landing page screenshots" note to the project backlog for the next UX change that touches the board.
- *Route guarding after the move.* Easy to accidentally break the authenticated `/` → `/sieges` redirect while pulling `/` out of `RequireAuth`. Cover with a component test or a manual checklist in the PR description.

---

### Issue 5 — Login page polish

**Summary.** Polish the existing login page so (a) mobile visitors see a clear "use a desktop" warning and (b) the rejection / unauthorized state reframes "you're not in this clan" as "here's how to run your own instance" instead of dead-ending the visitor.

**Acceptance criteria.**
- [ ] A mobile warning banner appears at viewport widths < 768px on the login page, with copy explaining that Siege Assignments is desktop-first and the sign-in will work but the app is not mobile-optimized. Banner does not block the sign-in button.
- [ ] The authorization-failure / rejection state (e.g. user is Discord-authenticated but not a member of the configured guild) shows copy that acknowledges this instance is for one specific clan *and* points the visitor at the landing page's self-host section with a clear call to action ("Run it for your own clan →").
- [ ] The happy-path sign-in flow is byte-identical from the user's perspective — same Discord icon, same button copy, same layout, same redirect behavior. This issue is a polish pass, not a rewrite.
- [ ] Existing login-related tests still pass. New test (unit or component) covers the mobile-viewport banner render condition.
- [ ] Visual review by the owner before close.

**Dependencies.** Depends on Issue 4 (the rejection-state copy links into a section of the landing page that doesn't exist yet), and logically on Issue 1 (the login page is easier to test end-to-end when local dev is smooth). Can be drafted in parallel with 4 but must not merge before 4.

**Effort.** S. Small surface area — two pieces of new copy, one banner, one test.

**Risks / open questions.**
- *What exactly constitutes "rejection"?* The current auth flow — does it return a distinct error state for "authenticated but not in guild" vs. "OAuth cancelled"? Confirm during implementation; the copy may need to fork based on the error type.
- *Banner reappearance on narrow desktop windows.* A 1024-wide browser with devtools open can be < 768. Accept — this is a signal not a lock.

## 5. Sequencing

```
         Issue 1: Local dev onboarding polish
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
   Issue 2: Anywhere docs    Issue 3: Azure docs
           │                         │
           └────────────┬────────────┘
                        ▼
           ┌────────────┴────────────┐
           ▼                         ▼
    Issue 4: Landing page     Issue 5: Login polish
```

- **Issue 1 is strictly first.** Everything else assumes a sane local dev experience. Don't start another issue until 1 is merged.
- **Issues 2 and 3 run in parallel** after 1 lands. They touch different files and have no shared code.
- **Issues 4 and 5 run in parallel** after 2 and 3 land. They both consume the self-host docs and both touch the frontend, but in non-overlapping files (landing page vs. login page). Coordinate on nav links and shared copy if needed.

## 6. Technical decisions to make before Issue 4 starts

These do not need to be resolved in this plan doc, but they must be resolved before the landing page issue begins implementation.

### Decision 6.1 — SEO rendering approach

**Context.** The app is a React Router SPA served by Vite + Nginx with Discord OAuth2 authentication. The landing page needs to be crawlable by Google, with correct `<title>`, meta description, and OG tags present in the initial HTML response (not only after hydration) for reliable indexing.

**Options.**
1. **`vite-plugin-react-ssg` (prerender plugin).** Build-time prerender for a specific list of routes. Uses `@unhead/react` hooks (`useSeoMeta`, `useHead`) inside the page components for per-page meta tags. Non-prerendered routes fall back to normal CSR automatically. Minimal configuration, no change to the dev server workflow, no impact on authenticated routes.
2. **`vite-react-ssg` (full SSG framework).** More feature-complete — supports loaders, data fetching at build time, per-page head management. Bigger footprint: changes how routing is defined, may affect CSR routes, needs care around the `RequireAuth` boundary.
3. **`react-helmet` / `react-helmet-async` (runtime meta tags only).** No build-time HTML generation. Google *does* execute JS during indexing, but runtime-only meta tags are noticeably less reliable than server-rendered ones, and Lighthouse SEO audits ding them. Works, but it's the weakest option for a page whose whole job is to get indexed.
4. **Vite's built-in `transformIndexHtml` with a static HTML template for `/`.** Hand-write the landing page's HTML and meta tags into a custom `index.html` that's served for `/`, with the SPA's own `index.html` serving everything else. Zero new dependencies, but now there are two HTML entry points to maintain.

**Recommendation.** **Option 1 — `vite-plugin-react-ssg`.** It's a drop-in prerender plugin that targets exactly this case (existing Vite + React Router SPAs that need a few static routes prerendered for SEO), the authenticated routes gracefully fall back to CSR without any code changes, and `@unhead/react`'s `useSeoMeta` hook is the cleanest per-page meta-tag API on offer. Options 2 is overkill, option 3 is the weakest for indexing, and option 4 introduces a second HTML entry point that will rot. Flag this recommendation for developer confirmation before Issue 4 starts — the landing page is the only prerendered route for now and the plugin's footprint should stay tiny.

### Decision 6.2 — Where to home the `/` → `/sieges` redirect for authenticated users

**Context.** Currently `/` is inside `RequireAuth` and `Navigate`s to `/sieges`. Pulling `/` out of `RequireAuth` to make it public means that redirect logic has to move somewhere.

**Options.**
1. **Guard inside the new `LandingPage` component.** On mount, if the auth context says the user is logged in, `Navigate` to `/sieges`. Downside: a brief flash of the landing page during auth hydration.
2. **Two separate routes outside/inside `RequireAuth` with the same path.** React Router doesn't love this; order matters and it's error-prone.
3. **A thin wrapper component `LandingOrSieges` at `/` that renders either the landing page or a redirect based on auth state.** Same as option 1 but factored out so the landing page itself stays pure. Slightly cleaner for testing.

**Recommendation.** **Option 3 — a `LandingOrSieges` wrapper.** Keeps the landing page component pure (easy to test, easy for the prerender plugin to handle), puts the auth decision in one small place, and makes it obvious to the next reader what's happening.

### Decision 6.3 — Where landing-page assets live

**Context.** Screenshots and the OG image need to be served as static assets from the frontend bundle.

**Options.**
1. `frontend/public/landing/` — served from the root of the frontend at `/landing/…` paths. Simplest.
2. `frontend/src/assets/landing/` — imported by components, hashed in the build. Good for components, wrong for OG images (OG consumers need a stable URL).
3. `docs/assets/landing/` — checked in but not served. Won't work for OG images.

**Recommendation.** **Option 1 — `frontend/public/landing/`.** OG consumers need stable absolute URLs, and `public/` gives you exactly that with no hashing.

### Decision 6.4 — Production compose overlay file shape

**Context.** Issue 2 needs a production compose definition that differs from dev.

**Options.**
1. **Overlay (`docker-compose.prod.yml` + `-f docker-compose.yml -f docker-compose.prod.yml`).** Idiomatic, small, composable. Harder for compose-first-timers to reason about.
2. **Standalone (`docker-compose.production.yml`).** Self-contained, easier to read. Duplicates a lot of the base compose.

**Recommendation.** **Option 1 — overlay.** Smaller maintenance burden over time. The self-host doc can show the exact `-f … -f …` command so readers don't have to know the Compose override mechanism by heart.

## 7. Success criteria

The milestone is done when all of the following are observable:

- A cold-cache `git clone && cp .env.example .env && docker-compose up` on a fresh machine reaches a populated UI — with visible demo data — in under 5 minutes, with the dev-mode banner showing.
- A developer with no prior context on this project can follow `docs/self-host/anywhere.md` top-to-bottom and end up with a working Siege Assignments instance on their own infrastructure in under 60 minutes, without opening the Azure docs once.
- A developer with an Azure subscription can follow `docs/self-host/azure.md` top-to-bottom to a successful `az deployment group create` without needing to cross-reference the infra README, the GitHub Actions workflow YAML, or this plan doc.
- The public landing page renders at `/` for unauthenticated visitors, redirects authenticated users to `/sieges`, and scores ≥90 on a Lighthouse SEO audit with correct `<title>`, meta description, and OG tags present in the initial HTML response.
- The login page shows a mobile-warning banner at < 768px and, on the authorization-failure state, points rejected visitors at the landing page's self-host section instead of dead-ending them.
- `frontend/src/pages/HomePage.tsx` is deleted from the repo.
- The README Quick Start, when read cold by a stranger, requires zero follow-up questions to get to a running instance.
- (Stretch, not required for milestone close) The landing page is indexed by Google for queries like "raid shadow legends siege tool" within 90 days of ship. Not a blocker — the milestone closes on indexability, not on actual rankings.
