#!/usr/bin/env python3
"""Daily seven-topic Telegram news briefing from public RSS/Atom feeds.

No browser automation, private social APIs, or paid service is required.
The ranking is a *newsworthiness proxy*, not measured social virality.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

from news_radar import clean, fetch_feed, normalize_url, parse_datetime, report_timestamp, send_telegram

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state" / "trending_seen.json"
TECH_STATE_FILE = ROOT / "state" / "seen.json"
OUTPUT_FILE = ROOT / "out" / "trending_latest.txt"
MAX_STORIES = 7
FRESHNESS = timedelta(hours=36)

GOOGLE_TOPIC = "https://news.google.com/rss/headlines/section/topic/"
US_LOCALE = "?hl=en-US&gl=US&ceid=US:en"
CAMBODIA_SEARCH = (
    "https://news.google.com/rss/search?q="
    + quote_plus("Cambodia when:1d")
    + "&hl=en-US&gl=US&ceid=US:en"
)

# Every category has at least one publicly accessible RSS source.
# Google News entries link to an aggregator page, not necessarily a publisher URL.
FEEDS: dict[str, list[tuple[str, str]]] = {
    "World": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Google News World", GOOGLE_TOPIC + "WORLD" + US_LOCALE),
    ],
    "Cambodia": [
        ("Google News Cambodia", CAMBODIA_SEARCH),
    ],
    "Technology": [
        ("BBC Technology", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("GitHub Blog", "https://github.blog/feed/"),
        ("Google News Technology", GOOGLE_TOPIC + "TECHNOLOGY" + US_LOCALE),
    ],
    "Business": [
        ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
        ("Google News Business", GOOGLE_TOPIC + "BUSINESS" + US_LOCALE),
    ],
    "Science": [
        ("BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        ("Google News Science", GOOGLE_TOPIC + "SCIENCE" + US_LOCALE),
    ],
    "Sports": [
        ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
        ("Google News Sports", GOOGLE_TOPIC + "SPORTS" + US_LOCALE),
    ],
    "Culture": [
        ("BBC Culture", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
        ("Google News Culture", GOOGLE_TOPIC + "ENTERTAINMENT" + US_LOCALE),
    ],
}
CATEGORIES = tuple(FEEDS)

SIGNIFICANCE_TERMS = (
    "announces", "announced", "launches", "launched", "election", "agreement",
    "court", "policy", "government", "inflation", "economy", "markets", "bank",
    "discovery", "breakthrough", "research", "security", "climate", "flood",
    "earthquake", "record", "championship", "wins", "award", "releases",
)


def load_state(path: Path) -> dict[str, str]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(state, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                               for k, v in state.items()):
        raise ValueError(f"Invalid delivery-state format in {path}")
    return state


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def article_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:22]


def title_similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left.casefold(), right.casefold()).ratio()


def similar_story(a: dict, b: dict) -> bool:
    if a["id"] == b["id"]:
        return True
    # Different counts, years, scores and dates can signify separate events.
    if re.findall(r"\b\d+\b", a["title"]) != re.findall(r"\b\d+\b", b["title"]):
        return False
    similarity = title_similarity(a["title"], b["title"])
    return similarity >= (0.91 if a["category"] == b["category"] else 0.96)


def score(item: dict, now: datetime) -> float:
    """Heuristic rank: freshness (40), significance (25), publisher (15), local (10).

    The remaining score space is intentionally unassigned: public RSS does not
    supply comparable, verified engagement signals across platforms.
    """
    hours = max(0.0, (now - item["published"]).total_seconds() / 3600)
    freshness = max(0.0, 40.0 * (1.0 - hours / 36.0))
    title = item["title"].casefold()
    significance = min(25.0, 5.0 * sum(term in title for term in SIGNIFICANCE_TERMS))
    publisher = 15.0 if item["source"].startswith("BBC ") else 13.0 if item["source"] == "GitHub Blog" else 8.0
    local_relevance = 10.0 if item["category"] == "Cambodia" else 0.0
    return round(freshness + significance + publisher + local_relevance, 2)


def select_stories(
    articles: list[dict], seen: dict, now: datetime, *,
    test_mode: bool = False, tech_seen: dict | None = None,
) -> list[dict]:
    """Prioritize one story per category, then fill remaining positions.

    Global near-title deduplication avoids reporting the same topic under
    multiple categories or via multiple syndicated sources.
    """
    age = timedelta(days=4) if test_mode else FRESHNESS
    blocked = set() if test_mode else set(seen) | set(tech_seen or {})
    candidates = []
    for raw in articles:
        published = raw.get("published")
        title = raw.get("title", "")
        url = normalize_url(str(raw.get("url") or ""))
        category = raw.get("category")
        if not (isinstance(published, datetime) and published.tzinfo and
                isinstance(title, str) and title.strip() and url and category in FEEDS):
            continue
        if not now - age <= published <= now + timedelta(hours=1):
            continue
        key = article_id(url)
        if key in blocked:
            continue
        item = dict(raw, url=url, id=key)
        item["rank"] = score(item, now)
        candidates.append(item)
    candidates.sort(key=lambda item: (item["rank"], item["published"]), reverse=True)

    unique: list[dict] = []
    for item in candidates:
        if any(similar_story(item, previous) for previous in unique):
            continue
        unique.append(item)

    chosen: list[dict] = []
    for category in CATEGORIES:
        story = next((item for item in unique if item["category"] == category), None)
        if story is not None:
            chosen.append(story)
    chosen.sort(key=lambda item: (item["rank"], item["published"]), reverse=True)
    for item in unique:
        if len(chosen) >= MAX_STORIES:
            break
        if item["id"] not in {selected["id"] for selected in chosen}:
            chosen.append(item)
    return chosen[:MAX_STORIES]


def story_summary(item: dict) -> str:
    # Google News RSS 'description' may contain a list of nested story links.
    # Never present such markup/aggregator metadata as an AI-written synopsis.
    if item["source"].startswith("Google News"):
        return "Headline indexed by Google News; follow the source link for context."
    summary = clean(item.get("summary", ""), 165)
    return summary or "Open the original source for details."


def render_report(
    stories: list[dict], now: datetime, *, test_mode: bool = False,
    partial: bool = False, available_categories: set[str] | None = None,
) -> tuple[str, list[dict]]:
    """Render balanced HTML; never truncate links, tags, or delivered-story IDs."""
    for count in range(min(MAX_STORIES, len(stories)), -1, -1):
        displayed = stories[:count]
        lines = [
            "🌍 <b>DAILY TRENDING INTELLIGENCE</b>",
            "<b>World · Cambodia · Technology · Business · Science · Sports · Culture</b>",
            f"<b>Issued:</b> <code>{report_timestamp(now)}</code>",
            f"<b>Stories:</b> {len(displayed)}",
        ]
        run_id = os.getenv("GITHUB_RUN_ID", "")
        if run_id.isdecimal():
            lines.append(f"<b>Run record:</b> <code>{run_id}</code>")
        if test_mode:
            lines.append("🧪 <i>TEST RUN — previously reported stories may appear</i>")
        if partial:
            lines.append("⚠️ <i>Some news sources were unavailable</i>")
        if available_categories is not None:
            missing = [cat for cat in CATEGORIES if cat not in available_categories]
            if missing:
                lines.append("<b>Unavailable categories:</b> " + html.escape(", ".join(missing)))
        references = []
        for index, item in enumerate(displayed, 1):
            title = html.escape(clean(item["title"], 104), quote=False)
            category = html.escape(str(item["category"]), quote=False)
            source = html.escape(clean(str(item["source"]), 65), quote=False)
            synopsis = html.escape(clean(story_summary(item), 130), quote=False)
            link = html.escape(item["url"], quote=True)
            lines.extend([
                "", f"<b>{index:02d} · {category} | {title}</b>",
                synopsis,
                f"🕒 <b>Published (feed):</b> {report_timestamp(item['published'])}",
                f"🏷 <b>Source:</b> {source} · <b>Ref:</b> [{index}]",
            ])
            references.append(f'[{index}] <a href="{link}">{source} · Article ↗</a>')
        if displayed:
            lines.extend(["", "📚 <b>REFERENCES</b>", *references])
        else:
            lines.extend(["", "No fresh qualifying headlines were found during this test."])
        lines.extend(["", "<i>All times: Cambodia ICT (UTC+07:00). Publication times are feed metadata. "
                      "Rank is an editorial estimate, not a measured social-media trend. "
                      "Google News links may open aggregator pages.</i>"])
        report = "\n".join(lines)
        if len(report) <= 3800:
            return report, displayed
        if count == 1:
            raise ValueError("One article's source URL exceeds Telegram report size limit")
    raise ValueError("Could not fit report in Telegram message limit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily trending intelligence")
    parser.add_argument("--test-mode", action="store_true", help="Post test report without changing state")
    parser.add_argument("--dry-run", action="store_true", help="Print report, do not post or change state")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    now = utc_now()
    seen = load_state(STATE_FILE)
    tech_seen = load_state(TECH_STATE_FILE)
    articles: list[dict] = []
    failed: list[str] = []
    available: set[str] = set()
    for category, sources in FEEDS.items():
        for name, url in sources:
            try:
                fetched = fetch_feed(name, url)
                available.add(category)
                articles.extend(dict(item, category=category) for item in fetched)
                logging.info("%s / %s: %d entries", category, name, len(fetched))
            except Exception as exc:
                failed.append(name)
                logging.warning("%s / %s unavailable: %s", category, name, exc)
    if not available:
        logging.error("All trending feeds unavailable; no channel post")
        return 1
    stories = select_stories(articles, seen, now, test_mode=args.test_mode, tech_seen=tech_seen)
    if not stories and not args.test_mode:
        logging.info("No fresh, undelivered headlines; channel remains quiet")
        return 0
    report, sent_stories = render_report(
        stories, now, test_mode=args.test_mode,
        partial=bool(failed), available_categories=available,
    )
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(report + "\n", encoding="utf-8")
    if args.dry_run:
        print(report)
        return 0
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    channel = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not channel:
        logging.error("Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID")
        return 2
    send_telegram(report, token, channel)
    logging.info("Telegram channel accepted daily briefing: %d stories", len(sent_stories))
    if not args.test_mode:
        for item in sent_stories:
            seen[item["id"]] = now.isoformat()
        cutoff = now - timedelta(days=90)
        seen = {k: v for k, v in seen.items() if (parse_datetime(v) or now) >= cutoff}
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(seen, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
