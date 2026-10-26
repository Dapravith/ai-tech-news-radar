"""Offline, deterministic tests for the scheduled all-topic briefing."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import trending_radar as radar

NOW = datetime(2026, 10, 13, 2, 0, 0, tzinfo=timezone.utc)


def article(category="Cambodia", number=0, age=2, title=None):
    return {
        "category": category,
        "source": "BBC World" if category != "Cambodia" else "Google News Cambodia",
        "publisher": "Khmer Times" if category == "Cambodia" else "",
        "title": title or f"Major {category} headline number {number}",
        "url": f"https://example.org/{category.lower()}/{number}",
        "published": NOW - timedelta(hours=age),
        "summary": "A report about a significant development.",
    }


class TrendingRadarTests(unittest.TestCase):
    def test_all_seven_categories_available(self):
        self.assertEqual(list(radar.FEEDS), [
            "World", "Cambodia", "Technology", "Business", "Science", "Sports", "Culture",
        ])
        self.assertTrue(all(radar.FEEDS[key] for key in radar.FEEDS))

    def test_deterministic_category_diversity(self):
        stories = [article(cat, index) for index, cat in enumerate(radar.CATEGORIES)]
        selected = radar.select_stories(stories, {}, NOW)
        self.assertEqual(len(selected), 7)
        self.assertEqual({story["category"] for story in selected}, set(radar.CATEGORIES))

    def test_category_shortfall_fills_remaining_slots(self):
        stories = [article("World", index) for index in range(9)]
        selected = radar.select_stories(stories, {}, NOW)
        self.assertEqual(len(selected), 7)
        self.assertTrue(all(s["category"] == "World" for s in selected))

    def test_score_freshness_and_local_priority(self):
        recent = article("World", 1, age=1)
        old = article("World", 2, age=24)
        local = article("Cambodia", 3, age=1)
        self.assertGreater(radar.score(recent, NOW), radar.score(old, NOW))
        self.assertGreater(radar.score(local, NOW), radar.score(recent, NOW))

    def test_duplicate_urls_and_syndicated_titles(self):
        first = article("World", 1)
        same_title_different_link = dict(first, url="https://different.example/article")
        selected = radar.select_stories([first, first, same_title_different_link], {}, NOW)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["url"], first["url"])

    def test_seen_and_tech_seen_are_filtered(self):
        first, second = article("Technology", 1), article("Technology", 2)
        self.assertEqual(radar.select_stories(
            [first, second], {radar.article_id(first["url"]): NOW.isoformat()}, NOW,
            tech_seen={radar.article_id(second["url"]): NOW.isoformat()},
        ), [])
        self.assertEqual(len(radar.select_stories([first], {
            radar.article_id(first["url"]): NOW.isoformat()}, NOW, test_mode=True)), 1)

    def test_unknown_indexed_publishers_are_excluded(self):
        unknown = article("Cambodia", 3)
        unknown["publisher"] = "Unverified Clickbait Site"
        missing = dict(article("Cambodia", 4))
        missing.pop("publisher")
        reputable = article("Cambodia", 5)
        selected = radar.select_stories([unknown, missing, reputable], {}, NOW)
        self.assertEqual([s["title"] for s in selected], [reputable["title"]])

    def test_direct_reporter_ranks_above_index_at_same_age(self):
        indexed = article("Cambodia", 4)
        direct = dict(indexed, source="Khmer Times",
                      url="https://www.khmertimeskh.com/a")
        self.assertGreater(radar.score(direct, NOW), radar.score(indexed, NOW))

    def test_google_news_report_has_original_publisher_attribution(self):
        item = article("Cambodia", 9)
        report, selected = radar.render_report([item], NOW)
        self.assertEqual(len(selected), 1)
        self.assertIn("Google News Cambodia / Khmer Times (indexed)", report)
        self.assertNotIn("originally reported by Google", report)

    def test_stale_future_invalid_and_javascript_are_filtered(self):
        stale = article(age=80)
        future = article(number=1, age=-3)
        invalid = dict(article(number=2), url="javascript:alert(1)")
        self.assertEqual(radar.select_stories([stale, future, invalid], {}, NOW), [])

    def test_telegram_references_escaped_and_precise_time(self):
        story = article(title="Tech <b>trends</b> & culture")
        report, included = radar.render_report([story], NOW)
        self.assertEqual(included[0]["url"], story["url"])
        self.assertIn("2026-10-13 09:00:00 ICT", report)
        self.assertIn("2026-10-13 07:00:00 ICT", report)
        self.assertIn("Tech trends &amp; culture", report)
        self.assertNotIn("<b>trends</b>", report)
        self.assertIn("<b>REFERENCES</b>", report)
        self.assertIn('<a href="https://example.org/cambodia/0">', report)

    def test_no_misleading_google_news_article_description(self):
        story = dict(article(), summary="<ul><li>Other breaking stories</li></ul>")
        self.assertIn("Headline indexed by Google News", radar.story_summary(story))
        report, _ = radar.render_report([story], NOW)
        self.assertNotIn("Other breaking stories", report)

    def test_long_links_do_not_break_html_or_state(self):
        stories = [article(category, index) for index, category in enumerate(radar.CATEGORIES)]
        for index, item in enumerate(stories):
            item["url"] = "https://example.org/" + "p" * 1000 + str(index)
        report, included = radar.render_report(stories, NOW)
        self.assertTrue(1 <= len(included) < len(stories))
        self.assertLessEqual(len(report), 3800)
        self.assertEqual(report.count('<a href="'), len(included))
        self.assertEqual(report.count("</a>"), len(included))

    def test_partial_feed_failure_and_live_delivery_state(self):
        a = article("World", number=3)
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(radar, "FEEDS", {"World": [
                  ("Unavailable", "https://bad.invalid"), ("Working", "https://example.org/rss")
              ]}),
              patch.object(radar, "fetch_feed", side_effect=[OSError("offline"), [a]]),
              patch.object(radar, "STATE_FILE", Path(folder) / "trending.json"),
              patch.object(radar, "TECH_STATE_FILE", Path(folder) / "tech.json"),
              patch.object(radar, "OUTPUT_FILE", Path(folder) / "report.txt"),
              patch.object(radar, "send_telegram") as send,
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHANNEL_ID": "@MyAITechRadar"}),
              patch.object(sys, "argv", ["trending_radar.py"]),
              patch.object(radar, "utc_now", return_value=NOW)):
            self.assertEqual(radar.main(), 0)
            self.assertEqual(send.call_args.args[2], "@MyAITechRadar")
            self.assertIn("Some news sources were unavailable", send.call_args.args[0])
            state = json.loads((Path(folder) / "trending.json").read_text())
            self.assertEqual(set(state), {radar.article_id(a["url"]), radar.LAST_REPORT_KEY})
            self.assertEqual(state[radar.LAST_REPORT_KEY], NOW.isoformat())

    def test_second_run_does_not_duplicate_notification(self):
        a = article("World", number=3)
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(radar, "FEEDS", {"World": [("Working", "https://example.org/rss")]}),
              patch.object(radar, "fetch_feed", return_value=[a]),
              patch.object(radar, "STATE_FILE", Path(folder) / "trending.json"),
              patch.object(radar, "TECH_STATE_FILE", Path(folder) / "tech.json"),
              patch.object(radar, "OUTPUT_FILE", Path(folder) / "report.txt"),
              patch.object(radar, "send_telegram") as send,
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHANNEL_ID": "@MyAITechRadar"}),
              patch.object(sys, "argv", ["trending_radar.py"]),
              patch.object(radar, "utc_now", return_value=NOW)):
            self.assertEqual(radar.main(), 0)
            self.assertEqual(radar.main(), 0)
            send.assert_called_once()

    def test_late_backup_does_not_publish_new_story_twice_in_one_day(self):
        first, newer = article("World", number=18), article("World", number=19)
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(radar, "FEEDS", {"World": [("Working", "https://example.org/rss")]}),
              patch.object(radar, "fetch_feed", side_effect=[[first], [newer]]) as fetch,
              patch.object(radar, "STATE_FILE", Path(folder) / "trending.json"),
              patch.object(radar, "TECH_STATE_FILE", Path(folder) / "tech.json"),
              patch.object(radar, "OUTPUT_FILE", Path(folder) / "report.txt"),
              patch.object(radar, "send_telegram") as send,
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHANNEL_ID": "@dailynewsagents"}),
              patch.object(sys, "argv", ["trending_radar.py"]),
              patch.object(radar, "utc_now", return_value=NOW)):
            self.assertEqual(radar.main(), 0)
            self.assertEqual(radar.main(), 0)
            send.assert_called_once()
            self.assertEqual(fetch.call_count, 1)
            delivered = radar.load_state(Path(folder) / "trending.json")
            self.assertEqual(delivered[radar.LAST_REPORT_KEY], NOW.isoformat())

    def test_test_mode_uses_channel_but_does_not_update_state(self):
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(radar, "FEEDS", {"World": [("Working", "https://example.org/rss")]}),
              patch.object(radar, "fetch_feed", return_value=[article("World")]),
              patch.object(radar, "STATE_FILE", Path(folder) / "trending.json"),
              patch.object(radar, "TECH_STATE_FILE", Path(folder) / "tech.json"),
              patch.object(radar, "OUTPUT_FILE", Path(folder) / "report.txt"),
              patch.object(radar, "send_telegram") as send,
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHANNEL_ID": "@MyAITechRadar"}),
              patch.object(sys, "argv", ["trending_radar.py", "--test-mode"]),
              patch.object(radar, "utc_now", return_value=NOW)):
            self.assertEqual(radar.main(), 0)
            self.assertIn("TEST RUN", send.call_args.args[0])
            self.assertFalse((Path(folder) / "trending.json").exists())

    def test_failed_delivery_does_not_mark_state(self):
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(radar, "FEEDS", {"World": [("Working", "https://example.org/rss")]}),
              patch.object(radar, "fetch_feed", return_value=[article("World")]),
              patch.object(radar, "STATE_FILE", Path(folder) / "trending.json"),
              patch.object(radar, "TECH_STATE_FILE", Path(folder) / "tech.json"),
              patch.object(radar, "OUTPUT_FILE", Path(folder) / "report.txt"),
              patch.object(radar, "send_telegram", side_effect=RuntimeError("403 forbidden")),
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHANNEL_ID": "@MyAITechRadar"}),
              patch.object(sys, "argv", ["trending_radar.py"]),
              patch.object(radar, "utc_now", return_value=NOW)):
            with self.assertRaisesRegex(RuntimeError, "403 forbidden"):
                radar.main()
            self.assertFalse((Path(folder) / "trending.json").exists())

    def test_all_feeds_fail_without_public_alert(self):
        with (patch.object(radar, "FEEDS", {"World": [("Broken", "https://invalid.invalid")]}),
              patch.object(radar, "fetch_feed", side_effect=OSError("offline")),
              patch.object(radar, "send_telegram") as send,
              patch.object(sys, "argv", ["trending_radar.py"])):
            self.assertEqual(radar.main(), 1)
            send.assert_not_called()

    def test_missing_category_warning_and_empty_test_message(self):
        report, included = radar.render_report([], NOW, test_mode=True, partial=True,
                                               available_categories={"World"})
        self.assertEqual(included, [])
        self.assertIn("Unavailable categories:", report)
        self.assertIn("No fresh qualifying headlines", report)

    def test_state_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "invalid.json"
            p.write_text('[]')
            with self.assertRaises(ValueError):
                radar.load_state(p)


if __name__ == "__main__":
    unittest.main()
