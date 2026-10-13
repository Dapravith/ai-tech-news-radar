# Cloud AI & Tech News Radar (zero subscription)

A **Telegram tech-news radar running every three hours even when your Mac is off**. GitHub Actions runs the schedule, public RSS/Atom feeds provide news, optional `openrouter/free` selects/summarizes articles, and Telegram sends the message. No desktop browser or VPS is needed. There are no recurring paid services in the default configuration, subject to providers' free-tier limits.

## Contents

```text
.github/workflows/daily-news.yml  Scheduled/manual cloud job
news_radar.py                     Feed parser, keyword ranker, AI fallback, Telegram client
state/seen.json                   Previously delivered URL hashes (committed by the job)
tests/test_news_radar.py           Offline unit tests
```

## 1. Set up a GitHub repository

Create a new **public** repository, for example `ai-tech-news-radar`, at https://github.com/new. A public repository using standard GitHub-hosted runners is free under current GitHub Actions policy. **Never put bot tokens or API keys into the repository or README.** Make the default branch `main` and enable GitHub Actions.

On your Mac, unzip this starter and upload it (including hidden `.github` directory):

```bash
cd ~/Downloads
unzip cloud_ai_tech_radar.zip
cd cloud_ai_tech_radar
git init -b main
git add .
git commit -m 'feat: add cloud AI tech radar'
git remote add origin https://github.com/YOUR_USERNAME/ai-tech-news-radar.git
git push -u origin main
```

If you created the repo with an initial README, clone that repo instead and copy these files into the clone before pushing, to avoid unrelated Git histories. If your default branch is protected or restricted, the workflow won't be able to commit `state/seen.json`; allow the workflow to update the state or replace that mechanism with another store.

## 2. Telegram Bot credentials

Reuse your **existing** AI News Monitor Telegram bot. Obtain its token from @BotFather (do not share it). For a private bot chat, send `/start` to your bot first.

Find your Telegram numeric chat ID (not the bot username). For a one-to-one conversation, it is often the same numeric value as your user ID. For groups/channels, use the corresponding numeric chat ID; channels also require posting permission.

Go to **GitHub repo → Settings → Secrets and variables → Actions → New repository secret** and create:

| Secret | Value |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Existing BotFather token |
| `TELEGRAM_CHAT_ID` | Numeric user/chat/channel ID |
| `OPENROUTER_API_KEY` | Optional API key (see below) |

Do not set `TELEGRAM_CHAT_ID` to `@YourBotName` or your bot token.

## 3. Optional free AI summary

Visit https://openrouter.ai/keys and create an API key under the **free** plan if available on your account. Store it as `OPENROUTER_API_KEY` secret. The Python script uses only the model ID **`openrouter/free`**; it is never configured to use a paid model. Free inference has daily and per-minute limits and can be temporarily unavailable.

**Without an OpenRouter key:** everything still works using keyword filtering plus source-provided descriptions. **With the key:** the AI chooses 3–5 salient articles and writes one-sentence takeaways based only on feed titles and snippets. If the model fails, the script uses the non-AI fallback. Neither mode can independently verify the full text of every article: open the source link for confirmation of important claims.

## 4. Manual cloud test (does not change dedup state)

On GitHub → **Actions → AI Tech Radar - Every 3 Hours → Run workflow**. Leave **Send a TEST message** checked and run it.

Wait for the job to finish; it fetches live feeds and sends a message to Telegram automatically. The phone can receive it even if your Mac is shut down. The test message is labeled TEST RUN, and allows articles from the past week to increase the chance of showing real headlines.

If Telegram receives the message, rerun with `test_mode=false` to exercise the normal deduplication flow. Verify `state/seen.json` changed in the repository after a successful delivery. Check **Actions → workflow run → Logs** and the `ai-tech-radar-digest` artifact for diagnostic information.

## 5. Automatic monitoring every three hours

`.github/workflows/daily-news.yml` contains:

```yaml
on:
  schedule:
    - cron: '0 2,5,8,11,14,17,20,23 * * *'
```

GitHub cron uses UTC. Runs start around **09:00, 12:00, 15:00, 18:00, 21:00, 00:00, 03:00 and 06:00 Cambodia time**. GitHub may start scheduled jobs late or, rarely, skip them during high load; it is not a strict exact-time SLA. The workflow runs on GitHub-hosted Ubuntu whether your Mac is off or on.

Production runs stay silent when there are no new significant stories. The job commits only URL hashes and delivery timestamps to `state/seen.json` to suppress repeat articles. It retries conflicting state pushes three times by merging with the latest `main`, without force-pushing. It records state **after Telegram successfully accepts the message**. The workflow sends one separate Telegram operational alert on job failure, including complete feed outages. If a workflow fails after Telegram sends but before state is committed, a later run can still repeat news: Telegram and Git commits do not share a transaction. The separate GitHub `push` trigger runs a production smoke test on source/workflow changes to `main`; state-only commits do not retrigger the job.

Public GitHub repositories can have their scheduled workflows disabled after **60 days without repository activity**. Check that the schedule stays enabled, especially after periods with no new stories.

## 6. Local offline checks

```bash
python3 -m unittest discover -s tests -v
python3 news_radar.py --dry-run
```

`--dry-run` needs internet to download feeds but does not need a Telegram token or alter dedup state. All runtime code uses the Python standard library (no `pip install`).

## 7. Keep Hermes where it fits

Keep **Hermes + ego (lite)** on your Mac for hands-on interactive research when the Mac is running. The GitHub Actions cloud job is separate; it does not require Hermes and cannot control an offline desktop ego Browser.

For a future always-on Hermes, install Hermes CLI on a Linux VM and use its built-in cron and gateway. Then replace ego Desktop with a supported **headless browser tool** or, preferably, the public feed collector for structured news. An always-free VM is subject to provider quotas and availability, and an AI provider may still impose rate limits or charges. Avoid running two schedules that both post to the same Telegram chat.

**X / Twitter:** This starter does not scrape or script X. X's automation policy restricts non-API website automation. Collect official announcement websites and public articles that link to the original X post instead. Direct API access is an optional, potentially paid extension.

## 8. Troubleshooting

| Symptom | Check |
| --- | --- |
| No notification | Actions run status; secrets exact names; `/start` bot chat; Telegram ID; mute/notifications |
| All feeds failed | News source availability, DNS, internet, rate limits; inspect Actions logs |
| No headlines | Period had no fresh relevant items; inspect sources and scoring threshold |
| OpenRouter 429 or failure | Free quota exhausted; digest falls back to feed snippets |
| No state update | Job was in test mode; no new headlines; workflow push permission |
| Three-hour workflow not running | `.github/workflows` on default branch, Actions enabled, 60-day inactivity, GitHub scheduler delay |
| Too many repeated messages | Verify `state/seen.json` commits succeed and avoid multiple running schedulers |

## Reference documentation

- GitHub Actions scheduling: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- OpenRouter free model router: https://openrouter.ai/openrouter/free
- Telegram Bot API: https://core.telegram.org/bots/api#sendmessage
- Hermes: https://hermes-agent.nousresearch.com/docs/guides/team-telegram-assistant

## 9. Reliability and limitations

- PRs run offline unit tests without accessing Telegram secrets; merging to `main` runs the production collector once, while only RSS/AI changes and workflow changes match the push filter.
- The separate failed-job notification posts an operational Telegram alert. Telegram API outages may prevent that alert; always inspect [GitHub Actions](https://github.com/Dapravith/ai-tech-news-radar/actions).
- Free OpenRouter models are best effort: malformed, non-JSON or empty responses fall back to source-provided summaries. No paid fallback model is configured.
- GitHub scheduled runs can arrive late or occasionally be skipped. A true external missed-run watchdog and a continuously running Hermes Agent require separate infrastructure.
- After production delivery, check `state/seen.json` and run production mode again to test suppression. Duplicate prevention is best-effort because Telegram `sendMessage` has no atomic transaction with the Git state commit.

## 10. Professional Telegram briefing format

Every delivered Telegram news report uses Telegram's supported HTML formatting: bold section headers, an exact report timestamp, an optional GitHub Actions run ID, story-by-story publication times, and a numbered **REFERENCES** section with clickable original-source URLs. All displayed timestamps are in Cambodia **ICT (UTC+07:00)**. The article publication time comes from the RSS/Atom feed metadata and is not an independently verified event timestamp.

Example format (illustrative, not current news):

```text
🗞 AI & TECH RADAR
Intelligence briefing · Every 3 hours
Issued: 2026-10-13 15:52:00 ICT (UTC+07:00)
Stories: 2
Run record: 38346920698

01 | Example AI development
Short editorial summary or source snippet.
Published (feed): 2026-10-13 14:10:00 ICT
Source: Example Tech Blog · Ref: [1]

02 | Example DevOps release
Short explanation of the change.
Published (feed): 2026-10-13 13:40:00 ICT
Source: Example Cloud Blog · Ref: [2]

REFERENCES
[1] Example Tech Blog · Original article ↗
[2] Example Cloud Blog · Original article ↗

All timestamps: Cambodia ICT (UTC+07:00).
```

Source titles, descriptions, and URLs are HTML-escaped before insertion into Telegram messages. A conservative message budget avoids cutting HTML tags and citations. If an unusually long original URL forces the formatter to include fewer articles, **only articles actually included in the sent report** are marked delivered in `state/seen.json`.
