# Getting Started

Get a populated local instance of RSL Siege Manager running in under 5 minutes. No Discord account needed — the default dev profile runs in demo mode with pre-seeded data and authentication disabled.

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

> **Auth note:** when running with real Discord OAuth (`AUTH_DISABLED=false`), only clan members who hold the configured Discord role (default: `Clan Deputies`) can log in. Set `DISCORD_REQUIRED_ROLE` in your `.env` to match the role name used in your server.
