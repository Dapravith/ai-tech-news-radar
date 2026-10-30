# Khmer visual news: deployment, editorial review and incident operations

The feature adds **four separate visual news editions** to the existing news
collectors. Its output is an 1080×1350 PNG poster + a short Telegram photo
caption + a full, independently readable Telegram text message linking to each
source. It does not replace existing Cambodia, world or tech publishers.

## Status

Code is implemented in `visual_news.py`, `visual_poster.py`,
`scripts/visual_fixture_preview.py`, `tests/test_visual_news.py`, and
`.github/workflows/visual-news.yml`. Production cron expressions are present,
but `VISUAL_NEWS_ENABLED` must explicitly equal `true` in GitHub Actions
**repository variables**. The default is **off**. CI previews never use a
Telegram bot token or an AI translation credential.

## Schedule (Cambodia ICT, UTC+7)

| Edition | Planned local publication | UTC cron |
| --- | --- | --- |
| Cambodia morning | 09:05 daily | `5 2 * * *` |
| Cambodia afternoon | 13:05 daily | `5 6 * * *` |
| Cambodia evening | 19:05 daily | `5 12 * * *` |
| Global | 10:25 daily | `25 3 * * *` |
| AI & software | 16:25 daily | `25 9 * * *` |
| Gadget Friday | 17:15 Friday | `15 10 * * 5` |

These are best-effort GitHub Actions cron times, **not guarantees**.
Different editions have separate state keys; Cambodia has distinct dayparts.

## Source controls

- **Cambodia:** the existing bilingual Google News Cambodia feeds, with a
  named-publisher allowlist (Cambodianess, CamboJA, Phnom Penh Post, Khmer
  Times, Kiripost, selected Khmer publishers and appropriate international
  outlets). Source type is labeled `indexed`, never direct.
- **Global:** established direct BBC, Guardian and Deutsche Welle feeds plus
  the existing reviewed Google News publisher list; reject unknown publishers.
- **AI/software:** existing GitHub, Kubernetes, Python, Cloudflare, Spring,
  Google AI, OpenAI, Hugging Face and UK NCSC primary blog feeds.
- **Gadget Friday:** MacRumors, GSMArena and Android Authority direct feeds,
  supplemented by Google News results only when the original publisher is
  actually identified as one of those three.
- Direct publisher claims must have a normalized URL whose hostname matches
  the pinned expected publisher domain. Source publication date must be
  timezone-aware and fresh (36 hours daily, 8 days weekly); missing sources
  are skipped. A review of an article's **claims** is not implied.
- The news label is `reported`, not `verified`; no blanket **✅ បានបញ្ជាក់**
  status is generated. An official vendor announcement is not independent
  confirmation of a product rumor or price.

## Khmer summarization and quality limits

The optional `OPENROUTER_API_KEY` batches **faithful Khmer translation** of
headlines and limited source excerpts (from direct feeds only). The response
must reuse the original item ID, use Khmer script, and introduce **no new
Arabic-numeral figures**. The numeric check is partial; it is **not** complete
semantic fact verification. When AI is unavailable, existing Khmer headlines
are preserved; an English headline remains attributed in its original text,
accompanied by a cautious Khmer note directing readers to the original source.
The production workflow sets `VISUAL_REQUIRE_KHMER=true` and **fails closed**
rather than publishing an English-only poster. Use a reliable translation
model through the existing approved OpenRouter setup, or keep public visual
posting disabled.

A true article-level summarized brief like the example requires original
article text and/or editorial review. Headlines alone cannot justify added
claims, quotes, product specifications or precise prices. This implementation
deliberately refuses those invented details.

## Font and poster dependencies

CI uses `fonts-noto-core` and pinned Pillow from
`requirements-visual.txt`. Pillow must support libraqm (correct Khmer
shaping). We do not commit or redistribute a font binary or fetch/unlicensed
press images. Poster cards use title text and original publisher names; the
full linked report remains available in Telegram.

Run offline:
```bash
python3 -m pip install -r requirements-visual.txt
# Linux (Ubuntu/Debian): sudo apt-get install fonts-noto-core
python3 -m unittest discover -s tests -v
python3 -m scripts.visual_fixture_preview
python3 visual_news.py --edition cambodia --dry-run
python3 visual_news.py --edition global --dry-run
python3 visual_news.py --edition tech --dry-run
python3 visual_news.py --edition gadget --dry-run
```

All `demo-*` artifacts contain **DEMO** marks and fictional fixture
headlines. Real-news PR previews are dry-run only and upload PNG/HTML artifacts
when qualifying articles are found.

## Activate safely

1. Review `.github/workflows/visual-news.yml`, test code, four PNGs and
   story URLs. Confirm PR tests and live RSS preview results are green.
2. Merge the PR into `main` once source/date/Khmer caption rendering is
   reviewed. Do **not** enable the variable until a private photo test passes.
3. In repository Settings → Secrets and variables → Actions, keep the existing
   `TELEGRAM_BOT_TOKEN`; set an optional `OPENROUTER_API_KEY` for source-only
   Khmer translation, and a **secret** `TELEGRAM_NEWS_CHAT_ID` for the personal
   Telegram chat. Do not place bot tokens or chat IDs in committed code.
4. In Actions → **Khmer Visual News - Cambodia Global Tech Gadget**, select
   **Run workflow → edition=cambodia, dry_run=true**. This generates a preview
   but sends no message. Inspect the artifact.
5. For an actual **private** test choose **dry_run=false,
   test_private=true**. The poster and full report are labeled TEST, and
   no state is recorded. Manual public posts are intentionally disallowed.
6. Only after checking Khmer quality and source links, set Actions repository
   variable `VISUAL_NEWS_ENABLED=true`. Set optional repository variable
   `VISUAL_NEWS_CHANNEL_ID=@dailynewsagents`; otherwise that channel is the
   workflow's default. Existing text-only pipelines remain active.
7. Observe a scheduled job, verify a photo and the companion text, and inspect
   `state/visual_seen.json` for recorded progress. Confirm the bot has
   Post Messages permission in the destination channel. In a channel, sending
   is only possible after permissions are granted.

## Partial delivery and incident handling

Telegram photo and message are **two independent HTTP calls**. If the first
succeeds and the second fails, the application records `photo_sent` and the
exact full report. After a state commit, a later run can resume the text
without re-sending the photo. Both destinations are tracked separately.
`--merge-state` uses monotonic acknowledgements so a concurrent state merge
cannot erase an acknowledged step.

**Exactly-once delivery is not guaranteed.** If Telegram accepted a message
but the runner crashed before the state was committed to Git, a retry could
duplicate it. Reconcile the public channel and delivery state manually after
an ambiguous timeout. Never blindly re-run a failed production job. A
database-backed delivery ledger with reconciliation is required before a
strict reliability SLA.

Stop public visual posting instantly by setting
`VISUAL_NEWS_ENABLED=false`. This does **not** disable the older text news
workflows. Security review is required before running Hermes or allowing an
agent to change the source policy, credentials or news publication schedule.
