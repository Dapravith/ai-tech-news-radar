#!/usr/bin/env python3
"""Two independently filtered 08:00 Cambodia Telegram news digests.

No paid AI provider or Hermes gateway is required. Articles come from RSS
metadata; all third-party text is treated as untrusted data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from news_radar import (
    TZ_KH, clean, fetch_feed, make_id, normalize_url, report_timestamp,
    send_telegram, similar_headline,
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "channels.json"
STATE_PATH = ROOT / "state" / "channel_seen.json"
OUT_DIR = ROOT / "out"
MAX_MESSAGE = 3800


def load_config(path: Path = CONFIG_PATH) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("timezone") != "Asia/Phnom_Penh":
        raise ValueError("Expected Cambodia timezone")
    if not isinstance(config.get("feeds"), list) or not config["feeds"]:
        raise ValueError("At least one RSS feed is required")
    channels = config.get("channels")
    if not isinstance(channels, dict) or set(channels) != {"it_support", "software"}:
        raise ValueError("Expected exactly the two configured channels")
    for key, channel in channels.items():
        if not re.fullmatch(r"@[A-Za-z0-9_]{5,32}", channel.get("chat_id", "")):
            raise ValueError(f"Invalid Telegram destination: {key}")
        if not isinstance(channel.get("topics"), dict) or not channel["topics"]:
            raise ValueError(f"No categories configured for {key}")
    return config


def load_state(path: Path = STATE_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Invalid channel delivery-state JSON")
    return data


def write_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def merge_state(current: dict, newly_delivered: dict) -> dict:
    """Preserve successful deliveries across concurrent state-commit retries."""
    merged = json.loads(json.dumps(current))
    for channel, days in newly_delivered.items():
        if not isinstance(days, dict):
            raise ValueError("Invalid snapshot day records")
        target = merged.setdefault(channel, {})
        for day, record in days.items():
            if not isinstance(record, dict) or not isinstance(record.get("ids"), list):
                raise ValueError("Invalid snapshot delivery record")
            old = target.get(day, {})
            ids = sorted(set(old.get("ids", [])) | set(record["ids"]))
            target[day] = {"ids": ids, "delivered": bool(
                old.get("delivered", False) or record.get("delivered", False)
            )}
    return merged


def token_matches(term: str, text: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", text))


def classify(article: dict, topics: dict) -> tuple[str | None, int]:
    """Require a matching TITLE keyword; snippets only improve ranking."""
    title = clean(str(article.get("title", "")), 250).casefold()
    summary = clean(str(article.get("summary", "")), 400).casefold()
    best_category, best_points = None, 0
    for category, terms in topics.items():
        headline_hits = sum(token_matches(term, title) for term in terms)
        description_hits = sum(token_matches(term, summary) for term in terms)
        points = headline_hits * 5 + min(description_hits, 3)
        if headline_hits and points > best_points:
            best_category, best_points = category, points
    return best_category, best_points


def choose_stories(
    articles: list[dict], channel: dict, now: datetime, seen_ids: set[str],
    *, test_mode: bool = False, limit: int = 5,
) -> list[dict]:
    age = timedelta(days=7) if test_mode else timedelta(hours=48)
    options = []
    for article in articles:
        published = article.get("published")
        url = normalize_url(str(article.get("url") or ""))
        if not (isinstance(published, datetime) and published.tzinfo and url and
                now - age <= published <= now + timedelta(hours=1)):
            continue
        category, points = classify(article, channel["topics"])
        if not category:
            continue
        key = make_id({"url": url})
        if not test_mode and key in seen_ids:
            continue
        item = dict(article, id=key, url=url, category=category)
        hours = max(0.0, (now - published).total_seconds() / 3600)
        item["score"] = points + max(0, 48 - hours) / 12
        options.append(item)
    options.sort(key=lambda x: (x["score"], x["published"]), reverse=True)
    unique = []
    for item in options:
        if any(item["id"] == old["id"] or similar_headline(item["title"], old["title"])
               for old in unique):
            continue
        unique.append(item)
    picked, counts = [], {}
    for item in unique:
        if counts.get(item["category"], 0) >= 2:
            continue
        picked.append(item)
        counts[item["category"]] = counts.get(item["category"], 0) + 1
        if len(picked) == limit:
            break
    for item in unique:
        if len(picked) >= limit:
            break
        if item["id"] not in {p["id"] for p in picked}:
            picked.append(item)
    return picked


def summarize(article: dict) -> str:
    summary = clean(str(article.get("summary", "")), 160)
    if "Article URL:" in summary or "Comments URL:" in summary:
        summary = ""
    return summary or "Read the original article for details."


def render(channel: dict, stories: list[dict], now: datetime,
           *, test_mode: bool = False, partial: bool = False) -> str:
    title = html.escape(channel["title"])
    header = [
        f'{channel["emoji"]} <b>{title}</b>',
        f'<b>Issued:</b> {html.escape(report_timestamp(now))}',
        '<b>Curated from RSS headlines for this channel</b>',
    ]
    if test_mode:
        header.append('🧪 <i>TEST MODE — repeated stories are possible</i>')
    if partial:
        header.append('⚠️ <i>Some RSS sources were unavailable</i>')
    lines = list(header)
    if not stories:
        lines.append("\nNo fresh matching headlines in the available RSS feeds today.")
    else:
        for index, article in enumerate(stories, 1):
            url = html.escape(article["url"], quote=True)
            lines.extend([
                "",
                f'<b>{index}. [{html.escape(article["category"])}] '
                f'{html.escape(clean(article["title"], 115))}</b>',
                html.escape(summarize(article)),
                f'🏷 {html.escape(article["source"])} · '
                f'{html.escape(report_timestamp(article["published"]))}',
                f'🔗 <a href="{url}">Original source</a>',
            ])
    lines.extend([
        "",
        "<i>Times are Cambodia ICT (UTC+7). Summaries are feed snippets, "
        "not independent fact checks.</i>",
    ])
    message = "\n".join(lines)
    if len(message) > MAX_MESSAGE:
        if not stories:
            raise ValueError("Empty digest is too long")
        return render(channel, stories[:-1], now, test_mode=test_mode, partial=partial)
    return message


def previously_sent(state: dict, channel_id: str) -> set[str]:
    result = set()
    for day in state.get(channel_id, {}).values():
        result.update(day.get("ids", []))
    return result


def run(config: dict, state_path: Path, *, dry_run: bool,
        test_mode: bool, now: datetime) -> int:
    state = load_state(state_path)
    local_date = now.astimezone(TZ_KH).date().isoformat()
    fetched, failed = {}, []
    for feed in config["feeds"]:
        try:
            fetched[feed["name"]] = fetch_feed(feed["name"], feed["url"])
            logging.info("%s: %d entries", feed["name"], len(fetched[feed["name"]]))
        except Exception as exc:
            failed.append(feed["name"])
            logging.warning("Feed unavailable: %s (%s)", feed["name"], type(exc).__name__)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    errors = []
    for key, channel in config["channels"].items():
        if not test_mode and state.get(key, {}).get(local_date, {}).get("delivered"):
            logging.info("%s: already delivered on %s", key, local_date)
            continue
        sources = [feed["name"] for feed in config["feeds"]
                   if key in feed["channels"]]
        healthy = [name for name in sources if name in fetched]
        if not healthy:
            errors.append(f"{key}: all configured feeds unavailable")
            continue

        articles = [article for name in healthy for article in fetched[name]]
        stories = choose_stories(articles, channel, now, previously_sent(state, key),
                                test_mode=test_mode,
                                limit=int(config.get("max_stories_per_channel", 5)))
        message = render(channel, stories, now, test_mode=test_mode,
                         partial=any(name in failed for name in sources))
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / f"{key}_latest.html").write_text(message + "\n", encoding="utf-8")
        logging.info("%s: %d selected stories, %d working feeds", key, len(stories), len(healthy))
        if dry_run:
            print(f"\n===== {key} PREVIEW =====\n{message}\n")
            continue
        if not token:
            errors.append(f"{key}: TELEGRAM_BOT_TOKEN not configured")
            continue
        try:
            send_telegram(message, token, channel["chat_id"])
        except Exception as exc:
            errors.append(f"{key}: Telegram delivery failed ({type(exc).__name__})")
            continue
        logging.info("%s: Telegram accepted digest delivery", key)
        if not test_mode:
            state.setdefault(key, {})[local_date] = {
                "ids": [item["id"] for item in stories],
                "delivered": True,
            }
            # Keep two weeks of channel-specific article history.
            cutoff = (now.astimezone(TZ_KH).date() - timedelta(days=14)).isoformat()
            state[key] = {d: value for d, value in state[key].items() if d >= cutoff}
            # Save immediately: the other channel might fail after this delivery.
            write_state(state, state_path)
    if errors:
        for error in errors:
            logging.error("%s", error)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Render without sending or writing state")
    parser.add_argument("--test-mode", action="store_true",
                        help="Allow older/repeated articles; do not write state")
    parser.add_argument("--merge-state", metavar="SNAPSHOT",
                        help="Merge a delivered-state snapshot into the working state")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.merge_state:
        write_state(merge_state(load_state(STATE_PATH),
                                load_state(Path(args.merge_state))), STATE_PATH)
        return 0
    return run(load_config(), STATE_PATH, dry_run=args.dry_run,
               test_mode=args.test_mode, now=datetime.now(timezone.utc))


if __name__ == "__main__":
    raise SystemExit(main())
