# Live original-publisher RSS only — Khmer visual news

## Real news, not fabricated fixtures

`visual_news.py` now collects **live publisher-owned RSS/Atom feeds** for all
four visual editions. News is attributed to the actual reporting publisher and
linked to the original article URL. The collector rejects Google News redirects,
unapproved article domains, undated items, invalid URLs, unsupported scripts, and
stories older than 36 hours (daily) or eight days (Gadget Friday).

The older text-only Cambodia brief and trending workflows remain separate and
may still use their vetted Google News index. **This change applies to the new
photo/poster editions only.**

## Publisher-owned RSS feeds

| Edition | Direct publishers and feed locations |
| --- | --- |
| Cambodia Khmer | Koh Santepheap: `https://kohsantepheapdaily.com.kh/feed/`; Kampuchea Thmey: `https://kampucheathmey.com/feed/` |
| Cambodia English (active) | CamboJA News: `https://cambojanews.com/feed/` |
| Global | Existing BBC, Guardian and DW **direct feeds**, and CNA World: `https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6311` |
| AI & Software | Existing official OpenAI, GitHub, Kubernetes, Spring, Cloudflare, Google AI, Python, Hugging Face and NCSC feeds |
| Gadget Friday | Original MacRumors, GSMArena and Android Authority RSS feeds; no Google News index |

Direct endpoints are **candidates** until a real GitHub Actions run confirms
a successful RSS response. Some publisher servers can reject cloud CI traffic
(HTTP 403), may change their RSS URL, or may publish a feed that isn't fresh.
The system reports failures and skips unavailable sources. It **does not**
substitute old articles, a syndicated redirect, a fallback story invented by an
AI model, or a fabricated poster.

## Reader-visible source evidence

Each live run writes:
- `out/visual/<edition>-latest.png`: current RSS story poster
- `out/visual/<edition>-latest.html`: full sourced Telegram text
- `out/visual/<edition>-sources.json`: original headlines, publisher, **direct**
  source article URLs, publisher RSS endpoint, timezone-aware publication
  timestamps and source language
- `out/visual/<edition>-review-request.json`: editable *unapproved* source-bound
  Khmer copy for human editorial review

A direct RSS headline is authentic **publisher reporting**, not independent
confirmation that its claims are true. Quotes, numbers and product specifications
still require original article review.

## Khmer source text

Native Khmer publisher headlines are preferred for Cambodia and reused **as
published**; when the original RSS excerpt is in Khmer too, it is reused
rather than inventing an explanation. English-language originals are displayed
in English with attribution until a reviewed Khmer translation is available.
A model-generated Khmer translation is only an optional **editorial draft**
when `VISUAL_AI_TRANSLATION_DRAFT=true` is explicitly set; it cannot authorize
a public post and must be checked against the original article.

The private-delivery input `test_private=true` is retained for workflow
compatibility, but its output is **real live news**, not sample/fake headlines
and not labeled “TEST ONLY” or “DEMO”. It is delivered only to the private
Telegram chat, and no production public-delivery state is written.

## Publication safety

Public visual news still requires both explicit Actions variables
`VISUAL_NEWS_ENABLED=true` and `VISUAL_PUBLICATION_REVIEWED=true`, plus
**human-approved** source-bound Khmer copy for each exact edition/time slot
in `config/visual_editorial_approvals.json`. By default the approvals file
is empty, so live story collection is operational but publication is on hold.
A failed feed check must never be bypassed with placeholder articles.

### Manual live validation

Run `Khmer Visual News - Cambodia Global Tech Gadget` from Actions:
1. Choose `cambodia` and `dry_run=true`. Inspect original article links
   in `cambodia-sources.json` and compare dates/claims with the publisher.
2. For real live source delivery to your private chat, choose
   `dry_run=false, test_private=true`. No public channel receives it.
3. Review/render and proofread exact Khmer copy, commit approvals via a protected
   PR, and activate the public gate only when approved.

The CI font smoke job uses synthetic neutral text **only inside automated
typeface unit tests**, never as a newsfeed or Telegram publisher.
