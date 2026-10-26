# Two Telegram Technical Digests — Morning Cambodia Delivery

This is the **replacement** for the uploaded inactive n8n *Crypto News & Sentiment* workflow. That JSON responds to inbound Telegram messages and contains no schedule. The replacement runs from GitHub Actions, with no n8n deployment, Hermes provider login, paid model, or always-on Mac required.

## Destinations and editorial filters

| Channel | Telegram | Subjects |
| --- | --- | --- |
| IT Support Engineer 24/7 Daily Tips | [@botsupportive](https://t.me/botsupportive) | Cybersecurity, patching, incidents, server operations, cloud, DNS, VPN, troubleshooting |
| Software-Engineer work-life Daily Digest | [@sedev2027](https://t.me/sedev2027) | Frontend and full-stack tools, Java/Spring Boot, APIs, databases, dev tools, AI coding and engineering reliability |

Both are in `config/channels.json`. The publisher only selects articles with relevant category terms in the **headline**, not merely a generic mention in the article description. Stories are ranked for relevance and freshness, limited to five per channel, and deduplicated by normalized URL and similar headlines.

Each post gives a source, publication timestamp in Cambodia time, a short RSS synopsis (if available), and the source article link. These are **not independent fact checks**. If feeds were reachable but no matching new headlines were found, the channel gets a truthful "No fresh matching headlines" message; if all sources for a channel are unavailable, that channel does not receive a misleading digest and the workflow fails.

## 1. Activate the GitHub Actions workflow

After the pull request is reviewed, merge it to `main`. It adds:

- `.github/workflows/channel-digests.yml`
- `channel_digest.py`
- `config/channels.json`
- `state/channel_seen.json`
- `tests/test_channel_digest.py`

The primary schedule is `11 1 * * *` **UTC**, meaning approximately **08:11 Asia/Phnom_Penh (UTC+7)**, with a recovery attempt at `41 1 * * *` (08:41). Both channels use delivery-state markers keyed by the Cambodia date, so a second successful run avoids duplicate posts. GitHub Actions scheduling is **best effort**, not exact to the minute, and both starts can still be delayed. GitHub-hosted runners operate even while your Mac is off.

The separate three-hour technology radar and 09:09 all-topic trending briefing are restored on this branch and publish to [@dailynewsagents](https://t.me/dailynewsagents). They do **not** publish to these two technical digest channels. The daily trending briefing also has backup schedules and a per-ICT-date delivery marker.

## 2. Confirm Telegram credentials in GitHub, not just on your Mac

Set repository Actions secret `TELEGRAM_BOT_TOKEN` to the token for **@HermesNewsRadarBot** (from BotFather). Do **not** paste that token into a repository file or a chat. The token on your local Mac is *not automatically available* to GitHub Actions.

The bot must be an administrator with **Post Messages** permission in both public channels and in **@dailynewsagents** for the separately scheduled radar and trending reports. You already verified direct posts to these channel usernames on your Mac; verify the GitHub secret belongs to the same bot.

Optional: repository Actions secret `TELEGRAM_CHAT_ID` should target a private admin chat to receive **failure-only** alerts. Do not use either public channel for operational alerts.

In repository **Settings → Actions → General → Workflow permissions**, allow the workflow to write repository contents, so it can persist per-channel deduplication state. Branch protection also must permit bot state updates or an alternative state store will be needed.

## 3. Preview safely, then publish a test

1. GitHub **Actions → Two Telegram Digests - 8 AM Cambodia → Run workflow**.
2. First use `test_mode=true`, `dry_run=true`: check the generated digest artifact without posting.
3. If previews look good, run with `test_mode=true`, `dry_run=false`: send clearly labelled test messages to both channels without modifying state.
4. Confirm both Telegram posts and the workflow logs.
5. For a production rehearsal, run `test_mode=false`, `dry_run=false`; this publishes and writes the date and article IDs into `state/channel_seen.json`. A second normal run that same Cambodia calendar day skips channels already marked delivered.

Scheduled runs are always **production** (not test mode).

## 4. Avoid duplicate schedulers

Your local Hermes jobs previously used:

- `0d377c4c3f88` → @botsupportive
- `acc2da83ad18` → @sedev2027

Once GitHub Actions publishing is verified, **disable any overlapping Hermes schedules**, including any Hermes job posting to @dailynewsagents, using `hermes cron --help` and the supported command for your installed Hermes version. Otherwise Hermes and GitHub may each post the same day's content. Do not delete them until the new scheduled workflow has been verified.

## 5. Failure and duplicate handling

- Feed parsing uses the existing `news_radar.py` RSS helper and is independent of Nous Portal/OpenRouter credentials.
- A failed feed is logged and skipped. Each channel must have at least one reachable configured feed.
- Failed Telegram posts are not marked delivered. If channel 1 succeeds and channel 2 fails, the script immediately records channel 1's success and tries channel 2 independently.
- The Actions workflow persists the successful part of a partially failed run, **even though the job is marked failed**, and retries Git conflicts.
- Exact-once delivery is **best effort**, not guaranteed: Telegram delivery and Git state commits are not one atomic transaction. If Git cannot commit after Telegram sends, a repeated post is still possible; inspect Actions logs before retrying.
- Inactive public repositories can have scheduled GitHub Actions workflows disabled after long periods without activity. Check scheduled runs periodically.

## Local tests (without network or Telegram)

```bash
python3 -m unittest discover -s tests -v
```

For a preview with current RSS sources:

```bash
python3 channel_digest.py --dry-run --test-mode
```

No pip packages are required; Python 3.12 standard library is sufficient.

## Editorial configuration

Edit `config/channels.json` to add, remove or refine categories and RSS sources. The configuration maps each feed to one or both channels, and each channel has independent topic keyword arrays. Avoid keywords such as `news`, `update`, or `today` by themselves: they make the filter overly broad. Confirm feed URLs work before adding them.

There is no crypto market-sentiment classification in this replacement because it is not part of either channel's scope.
