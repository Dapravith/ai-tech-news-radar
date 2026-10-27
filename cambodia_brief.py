#!/usr/bin/env python3
"""Cambodia-focused, curated Telegram news briefs. No Facebook scraping or paid AI.

Publisher allowlist is curated; Google News is only an RSS discovery index.
No feed snippets are treated as independently verified factual summaries.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import html
import json
import logging
import os
from pathlib import Path
from urllib.parse import quote_plus

from news_radar import (TZ_KH, clean, fetch_feed, make_id, normalize_url,
                        report_timestamp, send_telegram, similar_headline)

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state" / "cambodia_seen.json"
OUTPUT_FILE = ROOT / "out" / "cambodia_latest.html"
MAX_STORIES = 6

# This is a source-vetting policy, not proof that every published claim is true.
# Independent reporting, regional newsrooms and official agencies are included
# with their identity intact; readers can compare differing coverage.
PUBLISHERS = {
    "cambodianess": "Cambodianess",
    "camboja news": "CamboJA News",
    "camboja": "CamboJA News",
    "the phnom penh post": "Phnom Penh Post",
    "phnom penh post": "Phnom Penh Post",
    "khmer times": "Khmer Times",
    "kiripost": "Kiripost",
    "agence kampuchea presse": "AKP (state agency)",
    "akp": "AKP (state agency)",
    "reuters": "Reuters",
    "associated press": "Associated Press",
    "ap news": "Associated Press",
    "bbc news": "BBC News",
    "the guardian": "The Guardian",
    "rfi": "RFI",
    "rfi khmer": "RFI Khmer",
    "voa khmer": "VOA Khmer",
    "voice of america": "VOA",
    "koh santepheap": "Koh Santepheap",
    "kampuchea thmey": "Kampuchea Thmey",
}
LOCALE_EN = "&hl=en-US&gl=US&ceid=US:en"
LOCALE_KM = "&hl=km&gl=KH&ceid=KH:km"
BASE = "https://news.google.com/rss/search?q="
FEEDS = {
    "Google News Cambodia English": BASE + quote_plus("Cambodia when:1d") + LOCALE_EN,
    "Google News Cambodia Khmer": BASE + quote_plus("កម្ពុជា when:1d") + LOCALE_KM,
    "Google News Cambodia Business": BASE + quote_plus("Cambodia business economy when:1d") + LOCALE_EN,
}
TOPICS = {
    "💼 Economy & Business": ("economy", "business", "investment", "trade", "bank", "tourism", "startup",
                             "សេដ្ឋកិច្ច", "ពាណិជ្ជកម្ម", "វិនិយោគ", "ទេសចរណ៍"),
    "🏛️ Public Affairs": ("government", "ministry", "law", "policy", "parliament", "election", "border",
                           "រដ្ឋាភិបាល", "ក្រសួង", "ច្បាប់", "ព្រំដែន"),
    "💻 Tech & Education": ("technology", "digital", "education", "school", "university", "ai ", "internet",
                             "បច្ចេកវិទ្យា", "ឌីជីថល", "អប់រំ", "សាលា"),
    "🌿 Society & Environment": ("society", "health", "flood", "climate", "environment", "community",
                                   "សង្គម", "សុខភាព", "ទឹកជំនន់", "បរិស្ថាន"),
}


# Reporting periods are wall-clock dayparts in Cambodia (ICT), not labor-law shifts.
# A delayed GitHub Action must be classified by when it actually runs.
DAYPART_HEADINGS = {
    "overnight": "🌙 OVERNIGHT",
    "morning": "☀️ MORNING",
    "afternoon": "🌤️ AFTERNOON",
    "evening": "🌆 EVENING",
}
SCHEDULED_SLOTS = {
    "23 0 * * *": ("Morning", 7, 23),
    "53 0 * * *": ("Morning recovery", 7, 53),
    "23 5 * * *": ("Afternoon", 12, 23),
    "53 5 * * *": ("Afternoon recovery", 12, 53),
    "13 11 * * *": ("Evening", 18, 13),
    "43 11 * * *": ("Evening recovery", 18, 43),
}


def slot_for_time(now: datetime) -> str:
    local = now.astimezone(TZ_KH)
    hour = local.hour
    if hour < 5:
        daypart = "overnight"
    elif hour < 12:
        daypart = "morning"
    elif hour < 18:
        daypart = "afternoon"
    else:
        daypart = "evening"
    return f"{local:%Y-%m-%d}:{daypart}"


def scheduled_delay_notice(now: datetime, cron: str) -> str | None:
    """Show real scheduling delays; never imply Github cron is exact-time."""
    if cron not in SCHEDULED_SLOTS:
        return None
    name, hour, minute = SCHEDULED_SLOTS[cron]
    local = now.astimezone(TZ_KH)
    planned = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if planned > local:
        planned -= timedelta(days=1)
    delay = max(0, int((local - planned).total_seconds() // 60))
    if delay < 30:
        return None
    return (f"⚠️ <i>Delayed GitHub schedule: {html.escape(name)} "
            f"{planned:%Y-%m-%d %H:%M} ICT → actual {local:%H:%M} ICT "
            f"({delay // 60}h {delay % 60}m late). "
            "Period reflects the actual Cambodia clock time.</i>")


def normalize_state_slots(state: dict) -> dict:
    """Repair saved daypart keys incorrectly classified by older versions.

    Article delivery timestamps are recorded on Telegram API acknowledgement,
    so they're a more reliable basis for classifying a slot than its old name.
    """
    seen = state["seen"]
    corrected = {}
    for old_slot, record in state["slots"].items():
        new_slot = old_slot
        if isinstance(record, dict):
            for article_id in record.get("ids", []):
                try:
                    delivered = datetime.fromisoformat(seen[article_id])
                except (KeyError, ValueError, TypeError):
                    continue
                if delivered.tzinfo is not None:
                    new_slot = slot_for_time(delivered)
                    break
        existing = corrected.setdefault(new_slot, {"ids": [], "sent": {}})
        existing["ids"] = sorted(set(existing["ids"]) | set(record.get("ids", [])))
        existing["sent"].update(record.get("sent", {}))
    return {"seen": seen, "slots": corrected}


def load_state(path: Path = STATE_FILE) -> dict:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"seen": {}, "slots": {}}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("seen"), dict) or not isinstance(parsed.get("slots"), dict):
        raise ValueError("Invalid Cambodia delivery state")
    return normalize_state_slots(parsed)


def save_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def topic_for(title: str) -> str:
    lowered = title.casefold()
    for category, keywords in TOPICS.items():
        if any(k in lowered for k in keywords):
            return category
    return "📰 Cambodia News"


def select(articles: list[dict], seen: dict, now: datetime, *, limit: int = MAX_STORIES) -> list[dict]:
    candidates = []
    for original in articles:
        publisher = PUBLISHERS.get(str(original.get("publisher", "")).strip().casefold())
        published = original.get("published")
        url = normalize_url(str(original.get("url") or ""))
        title = clean(str(original.get("title", "")), 170)
        if not publisher or not url or not title or not isinstance(published, datetime) or not published.tzinfo:
            continue
        age = now - published
        if age < timedelta(hours=-1) or age > timedelta(hours=30):
            continue
        key = make_id({"url": url})
        if key in seen:
            continue
        item = dict(original, id=key, title=title, url=url, publisher=publisher,
                    category=topic_for(title))
        hours = max(0, age.total_seconds() / 3600)
        item["rank"] = max(0, 35 - hours) + (5 if item["category"] != "📰 Cambodia News" else 0)
        candidates.append(item)
    candidates.sort(key=lambda a: (a["rank"], a["published"]), reverse=True)
    unique = []
    for item in candidates:
        if any(old["id"] == item["id"] or similar_headline(old["title"], item["title"]) for old in unique):
            continue
        unique.append(item)
    output, per_publisher = [], {}
    for item in unique:
        if per_publisher.get(item["publisher"], 0) >= 2:
            continue
        output.append(item)
        per_publisher[item["publisher"]] = per_publisher.get(item["publisher"], 0) + 1
        if len(output) >= limit:
            break
    # Truthful short briefing is preferable to filling slots with stale/untrusted news.
    return output


def render(items: list[dict], now: datetime, *, period: str, partial: bool,
           test_mode: bool, delayed_notice: str | None = None) -> str:
    heading = DAYPART_HEADINGS[period]
    intro = [
        f"🇰🇭 <b>CAMBODIA NEWS · ព័ត៌មានកម្ពុជា · {heading}</b>",
        f"🕒 <b>Report:</b> {html.escape(report_timestamp(now))}",
        f"📰 <b>{len(items)} curated headlines</b> · No endless scrolling",
    ]
    if delayed_notice:
        intro.append(delayed_notice)
    if test_mode:
        intro.append("🧪 <i>TEST / PREVIEW: previously reported stories may appear</i>")
    if partial:
        intro.append("⚠️ <i>Partial RSS coverage: some sources unavailable</i>")
    if not items:
        intro.append("\nNo new qualifying headlines from reviewed publishers in this window.")
    for i, item in enumerate(items, 1):
        link = html.escape(item["url"], quote=True)
        title = html.escape(clean(item["title"], 125))
        publisher = html.escape(item["publisher"])
        category = html.escape(item["category"])
        intro.extend([
            "",
            f'<b>{i}. {title}</b>',
            f'{category} · <b>{publisher}</b>',
            f'🕒 {html.escape(report_timestamp(item["published"]))}',
            f'🔗 <a href="{link}">Read reported article</a>',
        ])
    intro.extend(["", "<i>Headlines are attributed to their original publishers via Google News RSS. "
                  "This is a curated feed, not independent fact-checking. Links may open Google News first.</i>"])
    report = "\n".join(intro)
    if len(report) > 3800:
        raise ValueError("Report exceeds safe Telegram HTML length")
    return report


def merge_state(existing: dict, delivered: dict) -> dict:
    merged = {"seen": dict(existing.get("seen", {})),
              "slots": json.loads(json.dumps(existing.get("slots", {})))}
    merged["seen"].update(delivered.get("seen", {}))
    for slot, record in delivered.get("slots", {}).items():
        current = merged["slots"].setdefault(slot, {"sent": {}, "ids": []})
        current["sent"].update(record.get("sent", {}))
        current["ids"] = sorted(set(current.get("ids", [])) | set(record.get("ids", [])))
    return merged


def run(now: datetime, state_path: Path, *, dry_run: bool, test_mode: bool,
        private_chat: str, channel: str) -> int:
    state = load_state(state_path)
    slot = slot_for_time(now)
    period = slot.split(":")[-1]
    destinations = {"channel": channel}
    if private_chat:
        destinations["personal"] = private_chat
    finished = state["slots"].get(slot, {}).get("sent", {})
    if not dry_run and not test_mode and all(finished.get(k) for k in destinations):
        logging.info("%s: all destinations already delivered", slot)
        return 0

    articles, failures = [], []
    for name, url in FEEDS.items():
        try:
            items = fetch_feed(name, url)
            logging.info("%s: %d indexed headlines", name, len(items))
            articles.extend(items)
        except Exception as error:
            failures.append(name)
            logging.warning("%s unavailable: %s", name, type(error).__name__)
    if dry_run:
        from collections import Counter
        counts = Counter(clean(str(a.get("publisher", "")), 100) or "(missing)" for a in articles)
        logging.info("RSS publisher sample: %s", counts.most_common(12))
    if len(failures) == len(FEEDS):
        logging.error("All Cambodia news indexes unavailable, refusing stale digest")
        return 1

    # Reuse the same article IDs when a second destination needs retrying.
    record = state["slots"].get(slot, {"ids": [], "sent": {}})
    fresh = select(articles, state["seen"], now)
    if record.get("ids") and not test_mode:
        indexed = {make_id({"url": normalize_url(str(a.get("url") or ""))}): a for a in articles}
        prepared = select([indexed[k] for k in record["ids"] if k in indexed], {}, now)
        if prepared:
            fresh = prepared
    notice = scheduled_delay_notice(now, os.getenv("NEWS_SCHEDULE_CRON", "").strip())
    if notice:
        logging.warning("Delayed scheduled execution, report reclassified to %s ICT", period)
    message = render(fresh, now, period=period, partial=bool(failures),
                     test_mode=test_mode, delayed_notice=notice)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(message + "\n", encoding="utf-8")
    if dry_run:
        print(message)
        return 0

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not channel:
        logging.error("Missing Telegram token or news channel configuration")
        return 2

    errors = []
    for key, dest in destinations.items():
        if not test_mode and finished.get(key):
            continue
        try:
            send_telegram(message, token, dest)
            logging.info("%s: Telegram acknowledged %s destination", slot, key)
        except Exception as error:
            errors.append(key)
            logging.error("%s: %s destination rejected delivery (%s)", slot, key, type(error).__name__)
            continue
        if not test_mode:
            record = state["slots"].setdefault(slot, {"ids": [i["id"] for i in fresh], "sent": {}})
            record["sent"][key] = True
            for article in fresh:
                state["seen"][article["id"]] = now.isoformat()
            cutoff = now - timedelta(days=21)
            state["seen"] = {key: stamp for key, stamp in state["seen"].items()
                             if datetime.fromisoformat(stamp) >= cutoff}
            state["slots"] = {key: value for key, value in state["slots"].items()
                              if key[:10] >= (now.astimezone(TZ_KH).date() - timedelta(days=21)).isoformat()}
            save_state(state, state_path)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--merge-state", metavar="SNAPSHOT")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if args.merge_state:
        save_state(merge_state(load_state(STATE_FILE), load_state(Path(args.merge_state))), STATE_FILE)
        return 0
    return run(datetime.now(timezone.utc), STATE_FILE, dry_run=args.dry_run,
               test_mode=args.test_mode, private_chat=os.getenv("TELEGRAM_NEWS_CHAT_ID", "").strip(),
               channel=os.getenv("TELEGRAM_NEWS_CHANNEL_ID", "@dailynewsagents").strip())


if __name__ == "__main__":
    raise SystemExit(main())
