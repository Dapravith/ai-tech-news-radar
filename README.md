# AI Tech News Radar — Cloud-Scheduled Telegram Intelligence

An automated RSS-based news collector running on **GitHub Actions**, including a three-hour technology radar, a daily all-topic trending briefing and two independent technical digests. A VPS or continuously running laptop is **not** required for these Python workflows.

> **Hermes note:** This repository uses Python scripts and GitHub Actions. It does not launch or host the Hermes Agent gateway. If Hermes is also publishing to these destinations, disable the overlapping Hermes cron jobs to avoid duplicate Telegram messages. Hosting a true 24/7 Hermes Agent requires a separate always-on runtime.

## Production destinations and cadence

All times below are **Cambodia ICT (UTC+7)**.

| Workflow | Planned cadence (ICT) | Telegram destination | Content |
| --- | --- | --- | --- |
| [AI Tech Radar](.github/workflows/daily-news.yml) | Every 3 hours, at 06:37, 09:37, 12:37, 15:37, 18:37, 21:37, 00:37, 03:37 | [@dailynewsagents](https://t.me/dailynewsagents) | AI, cloud, software, DevOps and security; up to 5 fresh stories |
| [Daily Trending Intelligence](.github/workflows/daily-trending.yml) | 09:09, with backup attempts 09:49 and 10:29 | [@dailynewsagents](https://t.me/dailynewsagents) | World, Cambodia, technology, business, science, sports and culture; up to 7 stories |
| [Two Telegram Digests](.github/workflows/channel-digests.yml) | 08:11, with backup attempt 08:41 | [@botsupportive](https://t.me/botsupportive) and [@sedev2027](https://t.me/sedev2027) | Two separately filtered, daily five-story technical digests |

The schedules are **best effort**. GitHub Actions may delay or occasionally skip cron jobs, even for public repositories; these are not precise or guaranteed execution times. Backup runs reduce the risk of missed daily delivery, but cannot guarantee exactly 08:00 or 09:00. Run history and real Telegram delivery should both be monitored.

## Delivery and editorial safeguards

- News comes from publicly available RSS/Atom feeds, not paid API subscriptions.
- Freshness, relevance, source reliability and topic diversity influence editorial ranking. **Trending** describes an editorial ranking proxy, **not measured social-media virality**.
- Production stories include the original link and source timestamp in ICT. Feed summaries are not independent fact checking.
- Technical and all-topic feeds check each other's delivered-article IDs where applicable to limit repeated stories on @dailynewsagents.
- On successful Telegram API acknowledgement, delivered IDs are written to `state/seen.json`, `state/trending_seen.json` or `state/channel_seen.json`, then committed to `main`.
- Daily trending backup runs use an ICT-calendar-day delivery marker. The two technical digest backups use their existing per-channel date markers. Production reruns skip completed daily posts.
- A source failure does not necessarily block all other sources. When all sources fail, publication fails instead of inventing headlines. Workflow failures alert a private chat when configured.
- Telegram publication and Git state commits are **not atomic**: if the state commit fails after a successful message, replay may duplicate a post. Inspect logs before replaying a production run.

## Required setup

1. Add the GitHub Actions repository secret `TELEGRAM_BOT_TOKEN` for `@HermesNewsRadarBot`. The bot must be an administrator with **Post Messages** permission in `@dailynewsagents`, `@botsupportive` and `@sedev2027`.
2. Optionally add `TELEGRAM_CHAT_ID` as a **private admin chat** for failed workflow alerts; never put secrets in committed files.
3. Permit **contents: write** in GitHub Actions for the publisher jobs to save delivery state on `main`. Confirm branch protection allows bot state commits, or use another persistent state store.
4. Review whether any local Hermes cron job also posts to those same channels. Keep one publisher per channel/cadence.
5. Merge the reviewed branch to `main`. Scheduled runs execute only from the default branch. Before merge, PR workflows run unit tests and RSS preview checks, **not** production Telegram delivery.

## Verify safely

Run locally (no Telegram delivery):

```bash
python3 -m unittest discover -s tests -v
python3 news_radar.py --dry-run --test-mode
python3 trending_radar.py --dry-run --test-mode
python3 channel_digest.py --dry-run --test-mode
```

Or open [GitHub Actions](https://github.com/Dapravith/ai-tech-news-radar/actions) and run the relevant workflow with `test_mode=true`. For the two-channel publisher choose `dry_run=true` as well to avoid test posts. The three-hour and trending scripts accept `--dry-run` locally; their workflow-dispatch tests send clearly labelled TEST posts.

Check the successful **publish job**, log line confirming Telegram acceptance, and updated delivery state. A green test job or a green workflow with no qualifying headlines is not proof that a new message reached Telegram.

The GitHub cloud schedule does not require Hermes or your Mac to stay online, but it cannot provide second-level scheduling guarantees. For strict timing or an independently operating Hermes reasoning agent, use a hosted scheduler/worker or always-on Hermes deployment and configure a single authoritative Telegram publisher.

For channel filters and operational details, see [CHANNEL_DIGESTS.md](CHANNEL_DIGESTS.md).
