#!/usr/bin/env python3
"""Clearly labeled design fixtures. No live stories or Telegram delivery."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from visual_news import EDITIONS, NAMES, full_caption, khmer_fallback
from visual_poster import render_poster

NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
HEADLINES = [
    "ព័ត៌មានថ្មីៗអំពីការអភិវឌ្ឍបច្ចេកវិទ្យា",
    "សេចក្ដីប្រកាសថ្មីសម្រាប់អ្នកប្រើប្រាស់",
    "ការពិភាក្សាអំពីនវានុវត្តន៍ និងសុវត្ថិភាព",
]


def main() -> int:
    output = Path("out/visual")
    output.mkdir(parents=True, exist_ok=True)
    for edition in EDITIONS:
        stories = []
        for index in range(3):
            item = {
                "id": f"fixture-{edition}-{index}",
                "title": HEADLINES[index],
                "url": f"https://example.org/demo/{edition}/{index}",
                "publisher": "DEMO SOURCE — NOT REAL NEWS",
                "published": NOW - timedelta(hours=index),
                "source_kind": "direct",
                "status": "reported",
                "edition": edition,
                "excerpt": "",
            }
            khmer_fallback(item)
            item["khmer_title"] = item["title"]
            stories.append(item)
        path = render_poster(edition, stories, "DEMO · 30 Oct 2026", output / f"demo-{edition}.png")
        text = "[DEMO ONLY · NOT REAL NEWS]\n" + full_caption(stories, edition, NOW)
        (output / f"demo-{edition}.html").write_text(text, encoding="utf-8")
        print(f"DEMO {edition}: {path} {path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
