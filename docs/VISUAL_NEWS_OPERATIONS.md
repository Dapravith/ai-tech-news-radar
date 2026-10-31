# Khmer visual news: deployment, editorial review and incident operations

The feature adds **four separate visual news editions** to the existing news
collectors. Its output is an 1080×1350 PNG poster + a short Telegram photo
caption + a full, independently readable Telegram text message linking to each
source. It does not replace existing Cambodia, world or tech publishers.

## Mandatory poster-quality hold (October 31, 2026)

The previous private Khmer poster had missing glyph squares and awkward Khmer
headlines. **Do not enable public visual publishing until you complete**
[mandatory editorial QA](VISUAL_POSTER_EDITORIAL_QA.md). In addition to
both repository variables, every source-bound story now requires a specific
human-reviewed Khmer title and summary. Unreviewed AI translations only appear
in private tests and are never sufficient for public publication.

## Status

Code is implemented in `visual_news.py`, `visual_poster.py`,
`visual_sources.py`, `tests/test_visual_news.py`, and
`.github/workflows/visual-news.yml`. Production cron expressions are present,
but BOTH `VISUAL_NEWS_ENABLED` and `VISUAL_PUBLICATION_REVIEWED` must explicitly equal `true` in GitHub Actions
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
A scheduled visual edition now refuses publishing when GitHub starts it more than
**90 minutes** after its planned UTC cron, or when the event cron does not
match the edition. This causes an operational failure alert instead of
mislabeling yesterday's/morning's headlines as an on-time report. A delayed
job must not be blindly rerun.
Different editions have separate state keys; Cambodia has distinct dayparts.

## Source controls

- **Cambodia:** only original publisher RSS feeds: Koh Santepheap and
  Kampuchea Thmey (native Khmer), plus Khmer Times, CamboJA News,
  Cambodianess, Phnom Penh Post and Kiripost. The visual editions never
  accept Google News redirect links. Sources can be unavailable to CI and
  are skipped when inaccessible.
- **Global:** original BBC, Guardian, Deutsche Welle and CNA RSS feeds;
  reject aggregator redirects and unapproved article domains.
- **AI/software:** existing GitHub, Kubernetes, Python, Cloudflare, Spring,
  Google AI, OpenAI, Hugging Face and UK NCSC primary blog feeds.
- **Gadget Friday:** only original MacRumors, GSMArena and Android
  Authority RSS feeds. No Google News results are accepted.
- Direct publisher claims must have a normalized URL whose hostname matches
  the pinned expected publisher domain. Source publication date must be
  timezone-aware and fresh (36 hours daily, 8 days weekly); missing sources
  are skipped. A review of an article's **claims** is not implied.
- The news label is `reported`, not `verified`; no blanket **✅ បានបញ្ជាក់**
  status is generated. An official vendor announcement is not independent
  confirmation of a product rumor or price.

## Khmer summarization and quality limits

Native Khmer headlines and Khmer RSS excerpts are preserved as written by
their original publishers. An optional `OPENROUTER_API_KEY` may be used
for Khmer *editorial draft translation* only when
`VISUAL_AI_TRANSLATION_DRAFT=true` is explicitly set. English-only source
headlines otherwise remain attributed original English text; no AI-generated
summary is invented. The response
must reuse the original item ID, use Khmer script, and introduce **no new
Arabic or Khmer numeric figures** (both scripts are normalized before comparison). The numeric check is partial; it is **not** complete
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
python3 -m scripts.check_visual_poster_qa
python3 visual_news.py --edition cambodia --dry-run
python3 visual_news.py --edition global --dry-run
python3 visual_news.py --edition tech --dry-run
python3 visual_news.py --edition gadget --dry-run
```

The CI font test uses neutral typography strings only and never publishes
them as news. Actual edition previews always fetch live original publisher RSS.
Their PNG, report, and `<edition>-sources.json` audit are stored as
short-lived Actions artifacts when qualifying articles are found.

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
5. For **private delivery of live publisher reports**, select
   **dry_run=false, test_private=true**. This input remains for workflow
   compatibility; the private poster is genuine recent original-publisher
   RSS news, with no "TEST ONLY" or "DEMO" labels. It records no public
   delivery state and cannot send to the public channel.
6. Only after checking Khmer quality and source links, and adding exact article
   approvals, set Actions repository variables `VISUAL_NEWS_ENABLED=true` and
   `VISUAL_PUBLICATION_REVIEWED=true`. Set optional repository variable
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
without re-sending the photo. Both destinations are tracked separately. The platform records Telegram photo and text message IDs
when acknowledged, enabling incident reconciliation. If two recipients would
receive a different story selection within one delivery slot, publishing
fails closed rather than silently generating mismatched posts.
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
