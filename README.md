# AI Tech News Radar — Cloud-Scheduled Telegram Intelligence

An automated RSS-based news collector running on **GitHub Actions**, including a three-hour technology radar, a daily all-topic trending briefing and two independent technical digests. A VPS or continuously running laptop is **not** required for these Python workflows.

> **Hermes note:** This repository uses Python scripts and GitHub Actions. It does not launch or host the Hermes Agent gateway. If Hermes is also publishing to these destinations, disable the overlapping Hermes cron jobs to avoid duplicate Telegram messages. Hosting a true 24/7 Hermes Agent requires a separate always-on runtime.

## Production destinations and cadence

All times below are **Cambodia ICT (UTC+7)**.

| Workflow | Planned cadence (ICT) | Telegram destination | Content |
| --- | --- | --- | --- |
| [AI Tech Radar](.github/workflows/daily-news.yml) | Every 3 hours, at 06:37, 09:37, 12:37, 15:37, 18:37, 21:37, 00:37, 03:37, plus a recovery scan 40 minutes later | [@dailynewsagents](https://t.me/dailynewsagents) | AI, cloud, software, DevOps and security; up to 5 fresh stories |
| [Cambodia Morning / Afternoon / Evening Brief](.github/workflows/cambodia-brief.yml) | **07:23 AM, 12:23 PM and 06:13 PM**, with recovery runs at 07:53, 12:53 and 18:43 | [@dailynewsagents](https://t.me/dailynewsagents) and optional private chat | Up to 6 curated Cambodia headlines from approved publishers, including Khmer-language news when indexed |
| [Daily Trending Intelligence](.github/workflows/daily-trending.yml) | 09:09, with backup attempts 09:49 and 10:29 | [@dailynewsagents](https://t.me/dailynewsagents) | World, Cambodia, technology, business, science, sports and culture; up to 7 stories |
| [Two Telegram Digests](.github/workflows/channel-digests.yml) | 08:11, with backup attempt 08:41 | [@botsupportive](https://t.me/botsupportive) and [@sedev2027](https://t.me/sedev2027) | Two separately filtered, daily five-story technical digests |

The schedules are **best effort**. GitHub Actions may delay or occasionally skip cron jobs, even for public repositories; these are not precise or guaranteed execution times. Backup runs reduce the risk of missed daily delivery, but cannot guarantee exactly 08:00 or 09:00. Run history and real Telegram delivery should both be monitored.

## Khmer visual news posters — original publisher RSS (opt-in)

The [visual news publisher](visual_news.py) creates **1080×1350 PNG posters**
and a full source-linked Telegram report from **LIVE original publisher RSS
feeds**. Google News redirects, synthetic headlines and fictional demo stories
are **not accepted** in visual editions. Every selected story retains its
original publisher, article URL, feed URL and publication timestamp.

| Edition | Planned Cambodia publication | Direct original RSS sources |
| --- | --- | --- |
| 🇰🇭 Cambodia visual | 09:05, 13:05, 19:05 daily | Khmer: Koh Santepheap, Kampuchea Thmey. English: CamboJA News; other publisher endpoints temporarily disabled after live RSS failures |
| 🌍 Global visual | 10:25 daily | BBC, Guardian, DW, CNA |
| 💻 AI & Software visual | 16:25 daily | Official OpenAI, GitHub, Kubernetes, Google AI, Cloudflare, Spring, Python, Hugging Face, NCSC feeds |
| 📱 Gadget Friday | Friday 17:15 | MacRumors, Android Authority, GSMArena |

The [visual publishing workflow](.github/workflows/visual-news.yml) has a
private-only live RSS delivery option: `dry_run=false`, `test_private=true`.
That input name is retained for compatibility; it **sends real source-backed
news** to your private Telegram chat without artificial “TEST ONLY” or “DEMO”
labels. For no-send review, use `dry_run=true` and inspect the poster and
`<edition>-sources.json` artifact. The font-only CI job is not a news feed.

Public visual publishing remains **off** unless both repository Actions
variables `VISUAL_NEWS_ENABLED=true` and
`VISUAL_PUBLICATION_REVIEWED=true` are configured **and** all headlines
and summaries have human review bound to their exact source articles in
`config/visual_editorial_approvals.json`.

Native Khmer source headlines and publisher-provided Khmer RSS excerpts are
preferred. Optional AI translation produces only an editorial draft when
`VISUAL_AI_TRANSLATION_DRAFT=true`, not a fabricated or automatically approved
report. External RSS outages are visible in workflow logs; **no fabricated
replacement stories** are sent.

Read [direct RSS sources and real-news validation](docs/VISUAL_LIVE_RSS.md),
[Khmer poster editorial and typography QA](docs/VISUAL_POSTER_EDITORIAL_QA.md),
and [visual workflow operations](docs/VISUAL_NEWS_OPERATIONS.md).

## Trusted sources and news quality

- **World / business / culture:** BBC News, The Guardian and Deutsche Welle (direct publisher feeds).
- **Cambodia:** Google News indexing restricted to reviewed publishers (Cambodianess, CamboJA News, Phnom Penh Post, Khmer Times, Reuters and AP). Direct Khmer Times RSS returns HTTP 403 from GitHub-hosted runners, so it is not configured as an active feed.
- **Science:** BBC Science and The Guardian Science. Nature was excluded after its RSS endpoint failed XML parsing in the cloud runner.
- **Technology / security:** GitHub, Kubernetes, Cloudflare, Python, Google AI, OpenAI, Hugging Face, Spring, and the UK's National Cyber Security Centre (NCSC) official news feed. CISA's official RSS endpoint returned HTTP 403 from the cloud runner and is not an active source.
- Hacker News community-ranked posts are excluded from automated production publication because a popular link is not confirmation of accuracy. Google News is treated as an *index*, never as the original reporter; unknown or missing Google publisher metadata is filtered out.
- Source curation does **not** verify each article's claims, and vendor posts are primary statements about their own products. Each report retains the original or aggregator URL, timestamp and outlet attribution.
- The three-hour technology radar limits production articles to the previous **24 hours** and normally uses no more than two stories per publisher when enough alternatives exist. The additional 40-minute scan also catches late-arriving stories and recovers from a missed initial scan.
- A published story must be dated within the production freshness window. An unavailable feed cannot produce invented or stale stories. Dry-run PR checks exercise real RSS retrieval.

## Cambodia news without scrolling Facebook

The dedicated `cambodia_brief.py` publisher collects recent **Cambodia news**, including Khmer and English headlines, and sends compact Telegram reports three times a day. It does **not** scrape, log in to, or impersonate Facebook pages; it follows the original publishers' website coverage indexed by Google News. The reports offer the feel of a short newsfeed: headline, topic, publisher, Cambodia publication time and a link.

**Reviewed publisher list** includes Cambodianess, CamboJA News, Phnom Penh Post, Khmer Times, Kiripost, Khmer language publishers Kampuchea Thmey and Koh Santepheap, plus Reuters, AP, BBC, RFI, VOA Khmer and official Cambodian news agency AKP. Coverage depends on current index availability. Official/state-agency reporting is labeled as such, not presented as independent verification.

**Get the briefing directly in your private Telegram:**

1. Open the chat with [@HermesNewsRadarBot](https://t.me/HermesNewsRadarBot) and send `/start` so Telegram permits the bot to message you.
2. In repository **Settings → Secrets and variables → Actions**, set `TELEGRAM_NEWS_CHAT_ID` to your **private** Telegram chat ID (not a channel username). Do not commit or paste credentials into source files.
3. If that secret is absent, the workflow falls back to `TELEGRAM_CHAT_ID` when configured. That existing secret was previously for private operational alerts; set the dedicated secret if you want a different recipient.
4. The bot must have **Post Messages** permission in [@dailynewsagents](https://t.me/dailynewsagents); otherwise the public channel delivery fails. The private DM is optional, and successful delivery is recorded separately from public delivery.
5. Run [Cambodia News Brief Actions](https://github.com/Dapravith/ai-tech-news-radar/actions/workflows/cambodia-brief.yml) with `test_mode=true`, `dry_run=true` for a **no-send preview**. After reviewing, run a labeled Telegram test (`test_mode=true`, `dry_run=false`). Then observe a real scheduled run.

The publisher classifies notifications by the **actual** Cambodia clock time: Morning (05:00–11:59), Afternoon (12:00–17:59), Evening (18:00–23:59), or Overnight (00:00–04:59). This defines **news reporting periods**, not Cambodia labor-law shift entitlements. The deployment corrects earlier misclassified saved delivery slots using their recorded send timestamps. When a scheduled job starts over 30 minutes late, the report displays the original planned start and the execution delay instead of claiming on-time delivery.

On October 27, 2026, GitHub started the 07:23/07:53 ICT morning jobs around 12:16/12:40 ICT: a multi-hour scheduling delay, separate from the period-classification bug. **No GitHub cron configuration can guarantee exact minutes**. For a real delivery-time SLA, use a managed external scheduler/always-on worker with monitoring and an explicit late-run policy.

Daily runs use Cambodia ICT and have recovery attempts, but **GitHub Actions cron is best-effort**: they are not guaranteed to begin exactly on schedule. A source outage is never filled with invented headlines. Repeated per-slot runs do not resend confirmed destinations. Green CI preview does not prove that Telegram accepted a production message.

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
