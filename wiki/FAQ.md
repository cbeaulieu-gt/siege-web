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
