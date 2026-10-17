# AI Tech News Radar — Two Telegram Channels

Cloud-hosted **8:00 AM Cambodia time** daily digests, separated by editorial category, delivered with [GitHub Actions](https://github.com/Dapravith/ai-tech-news-radar/actions). No VPS, locally running Hermes gateway, n8n server or paid model is required.

| Channel | Destination | Focus |
| --- | --- | --- |
| IT Support Engineer 24/7 Daily Tips | [@botsupportive](https://t.me/botsupportive) | Security, network, server, cloud and support operations |
| Software-Engineer work-life Daily Digest | [@sedev2027](https://t.me/sedev2027) | Full-stack coding, frontend/backend, data, developer tools and engineering reliability |

**[Complete setup, testing, and troubleshooting instructions →](CHANNEL_DIGESTS.md)**

## Current architecture

```text
GitHub Actions (daily 01:00 UTC = 08:00 Cambodia)
  └─ channel_digest.py
      ├─ fetch RSS feeds defined in config/channels.json
      ├─ filter and rank IT Support articles
      ├─ filter and rank Software Engineering articles
      ├─ deduplicate per-channel, per-day
      ├─ publish independently to @botsupportive and @sedev2027
      └─ persist state/channel_seen.json
```

This replacement adapts the RSS aggregation idea from the supplied n8n crypto workflow. The supplied JSON is an **inactive Telegram-triggered crypto workflow**, not a daily scheduler, so it is not imported directly.

## Required configuration

- GitHub repository Actions secret `TELEGRAM_BOT_TOKEN` for `@HermesNewsRadarBot`, which must be an admin with **Post Messages** enabled in both channels.
- GitHub Actions workflow permissions allow `contents: write` to commit deduplication state.
- Optional Actions secret `TELEGRAM_CHAT_ID` for **private** failure-only notifications.

## Schedule, previews and tests

The active publishing workflow is `.github/workflows/channel-digests.yml`, triggered by `0 1 * * *` UTC. GitHub scheduled starts can be delayed and are not guaranteed to run at exactly 08:00.

Open **Actions → Two Telegram Digests - 8 AM Cambodia → Run workflow**. For a nonposting preview use `test_mode=true` and `dry_run=true`; then send labelled test messages using `test_mode=true`, `dry_run=false`. Both are separate from production delivery state.

Run offline unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Local network-backed preview:

```bash
python3 channel_digest.py --dry-run --test-mode
```

The older `daily-news.yml` and `daily-trending.yml` schedules are retired but those workflows and scripts remain for manual use. Turn off **local Hermes cron jobs** posting to these same channels after verifying GitHub delivery, or duplicate digests can occur. Per-channel delivery is best effort; Telegram and git commits are not atomic.

## Legacy tools

- `news_radar.py`: three-hour AI/tech radar collector and shared RSS/Telegram helpers (manual mode)
- `trending_radar.py`: broad trending brief collector (manual mode)
- `tests/`: offline tests for the new and legacy systems

See [CHANNEL_DIGESTS.md](CHANNEL_DIGESTS.md) for editorial category configuration and operational details.
