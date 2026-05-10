# RSL Siege Manager

A comprehensive web utility for coordinating Raid Shadow Legends clan siege assignments — validated, automated, and Discord-native.

Clan leaders and planners use RSL Siege Manager to build, validate, and publish siege building assignments without leaving a browser. The app handles validation, auto-fill, attack-day logic, and Discord delivery end to end. Self-hostable, MIT licensed, and free to run.

## What it does

| Feature | What it does |
|---|---|
| **Validated assignments** | 16 rule checks catch overlaps, misplacements, and capacity errors before posting. |
| **Auto-fill** | Preview and commit assignments for empty positions in one click; what you see is exactly what gets saved. |
| **Attack-day logic** | Pinned members count toward Day 2 thresholds automatically; no manual bookkeeping. |
| **Discord-native** | OAuth2 sign-in, role-gated access, DM notifications, and assignment-image posts to your siege channels. |
| **Generated assignment images** | Server-rendered PNGs of the full board, posted directly to Discord (no screenshots, no manual cropping). |
| **Self-hostable** | Runs on any Docker host or a managed Azure stack. Open source, MIT licensed, no SaaS dependency. |

## Who this is for

Clan leaders and planners who coordinate siege building assignments for their guild — anyone who wants validated, automated, Discord-native tooling for the weekly siege cycle. Developers curious about the stack (React + FastAPI + a Discord bot sidecar) will find the codebase approachable too.

## Start here

- **Want to try it locally in 5 minutes?** [Getting Started](Getting-Started)
- **Ready to self-host for your clan?** Pick a path:
  - [Self-Host on Any VPS](Self-Host-on-Any-VPS) — any Linux host that runs Docker. No cloud account.
  - [Self-Host on Azure](Self-Host-on-Azure) — managed Container Apps, Key Vault, PostgreSQL Flexible Server.
- **Run into something unexpected?** [FAQ](FAQ)

## About this wiki

This wiki is mirrored from the `wiki/` folder in the [main repo](https://github.com/glitchwerks/siege-web). To edit a page, open a PR against `wiki/<Page-Name>.md` — direct edits through the wiki web UI will be overwritten on the next publish. Pull requests are reviewed, merged to `main`, and auto-published by a GitHub Action within a minute or two.
