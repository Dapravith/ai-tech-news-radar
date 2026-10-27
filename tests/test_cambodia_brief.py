"""Offline deterministic regression tests for curated Cambodia Telegram reports."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import cambodia_brief as brief

AM = datetime(2026, 10, 26, 0, 23, tzinfo=timezone.utc)
NOON = datetime(2026, 10, 26, 5, 23, tzinfo=timezone.utc)
PM = datetime(2026, 10, 26, 11, 13, tzinfo=timezone.utc)


def item(title="Cambodia digital economy update", publisher="Cambodianess", hours=2, index=1):
    return {
        "title": title, "publisher": publisher, "source": "Cambodia English Index",
        "url": f"https://news.google.com/rss/articles/{index}",
        "published": AM - timedelta(hours=hours),
        "summary": "<a>Untrusted indexed metadata</a>",
    }


class SelectionTests(unittest.TestCase):
    def test_cambodia_ict_daypart_boundaries(self):
        self.assertEqual(brief.slot_for_time(AM), "2026-10-26:morning")
        self.assertEqual(brief.slot_for_time(NOON), "2026-10-26:afternoon")
        self.assertEqual(brief.slot_for_time(PM), "2026-10-26:evening")
        cases = [
            (4, 59, "overnight"), (5, 0, "morning"),
            (11, 59, "morning"), (12, 0, "afternoon"),
            (17, 59, "afternoon"), (18, 0, "evening"),
            (23, 59, "evening"), (0, 0, "overnight"),
        ]
        for hour, minute, expected in cases:
            # Local Cambodia time expressed with a +07:00 offset.
            moment = datetime(2026, 10, 27, hour, minute,
                              tzinfo=brief.TZ_KH)
            with self.subTest(local_time=(hour, minute)):
                self.assertEqual(brief.slot_for_time(moment),
                                 f"2026-10-27:{expected}")

    def test_delayed_morning_run_at_1216_is_afternoon_and_transparent(self):
        delayed = datetime(2026, 10, 27, 5, 16, 15, tzinfo=timezone.utc)
        self.assertEqual(brief.slot_for_time(delayed), "2026-10-27:afternoon")
        notice = brief.scheduled_delay_notice(delayed, "23 0 * * *")
        self.assertIn("07:23", notice)
        self.assertIn("12:16", notice)
        self.assertIn("4h 53m late", notice)
        report = brief.render([], delayed, period="afternoon", partial=False,
                              test_mode=False, delayed_notice=notice)
        self.assertIn("AFTERNOON", report)
        self.assertNotIn("🌆 EVENING", report)
        self.assertIn("Delayed GitHub schedule", report)
        self.assertIsNone(brief.scheduled_delay_notice(
            datetime(2026, 10, 27, 0, 30, tzinfo=timezone.utc),
            "23 0 * * *"
        ))

    def test_legacy_wrong_evening_and_morning_state_is_reclassified(self):
        # Actual records retrieved 27 Oct: a 00:20 ICT run was stored as
        # "morning", and a 12:16 ICT run was stored as "evening".
        old = {"seen": {
            "before": "2026-10-26T17:20:45+00:00",
            "lunch": "2026-10-27T05:16:15+00:00",
        }, "slots": {
            "2026-10-27:morning": {
                "ids": ["before"], "sent": {"channel": True}},
            "2026-10-27:evening": {
                "ids": ["lunch"], "sent": {"personal": True}},
        }}
        fixed = brief.normalize_state_slots(old)
        self.assertEqual(set(fixed["slots"]),
                         {"2026-10-27:overnight", "2026-10-27:afternoon"})
        self.assertTrue(fixed["slots"]["2026-10-27:afternoon"]["sent"]["personal"])
        self.assertNotIn("2026-10-27:evening", fixed["slots"])

    def test_afternoon_and_evening_retry_have_distinct_delivery_slots(self):
        self.assertNotEqual(brief.slot_for_time(NOON), brief.slot_for_time(PM))

    def test_reject_unknown_missing_and_old_publishers(self):
        unknown = item(index=2, publisher="Random Viral Content")
        no_source = item(index=3, publisher="")
        stale = item(index=4, hours=72)
        ok = item(index=5, publisher="CamboJA News")
        chosen = brief.select([unknown, no_source, stale, ok], {}, AM)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]["publisher"], "CamboJA News")

    def test_sources_and_duplicate_headlines_are_balanced(self):
        articles = [item(index=i, title=f"Cambodia digital economy report {i}") for i in range(4)]
        articles.extend([item(index=10+i, publisher="Khmer Times",
                             title=f"Cambodia trade news {i}") for i in range(3)])
        selected = brief.select(articles, {}, AM)
        self.assertEqual(len(selected), 4)
        self.assertEqual(sum(a["publisher"] == "Cambodianess" for a in selected), 2)
        self.assertEqual(sum(a["publisher"] == "Khmer Times" for a in selected), 2)

    def test_multiple_index_duplicates_and_seen_ids(self):
        a = item(index=99)
        b = dict(a, source="Cambodia Khmer Index")
        seen = {brief.make_id({"url": a["url"]}): AM.isoformat()}
        self.assertEqual(brief.select([a, b], seen, AM), [])

    def test_safe_render_and_links_include_ict(self):
        one = dict(item(title="Cambodia <b>digital</b> & economy", index=99),
                   id="abc", category="💼 Economy & Business",
                   publisher="Cambodianess")
        text = brief.render([one], AM, period="morning", partial=False, test_mode=False)
        self.assertIn("Cambodia digital &amp; economy", text)
        self.assertNotIn("<b>digital</b>", text)
        self.assertIn("2026-10-26 07:23:00 ICT", text)
        self.assertIn("Cambodianess", text)
        self.assertIn("Read reported article", text)

    def test_state_merging_partial_successes(self):
        old = {"seen": {"id1": AM.isoformat()},
               "slots": {"2026-10-26:morning": {"ids": ["id1"], "sent": {"personal": True}}}}
        other = {"seen": {"id2": AM.isoformat()},
                 "slots": {"2026-10-26:morning": {"ids": ["id2"], "sent": {"channel": True}}}}
        merged = brief.merge_state(old, other)
        self.assertEqual(set(merged["slots"]["2026-10-26:morning"]["ids"]), {"id1", "id2"})
        self.assertEqual(merged["slots"]["2026-10-26:morning"]["sent"],
                         {"personal": True, "channel": True})


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "seen.json"
        self.output = Path(tmp.name) / "latest.html"
        self.reports = [item(index=1), item(index=2, publisher="CamboJA News",
                                            title="Cambodia economic cooperation")]
        self.fetch = lambda *_: self.reports

    def test_dry_run_never_posts_or_modifies_state(self):
        with (patch.object(brief, "fetch_feed", side_effect=self.fetch),
              patch.object(brief, "OUTPUT_FILE", self.output),
              patch.object(brief, "send_telegram") as send):
            self.assertEqual(brief.run(AM, self.path, dry_run=True, test_mode=True,
                                       channel="@dailynewsagents", private_chat=""), 0)
            self.assertFalse(self.path.exists())
            send.assert_not_called()

    def test_two_destinations_sent_once_per_slot(self):
        sent = []
        with (patch.object(brief, "fetch_feed", side_effect=self.fetch),
              patch.object(brief, "OUTPUT_FILE", self.output),
              patch.object(brief, "send_telegram", side_effect=lambda _, __, ch: sent.append(ch)),
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"})):
            self.assertEqual(brief.run(AM, self.path, dry_run=False, test_mode=False,
                                       channel="@dailynewsagents", private_chat="private123"), 0)
            self.assertEqual(sent, ["@dailynewsagents", "private123"])
            self.assertEqual(brief.run(AM + timedelta(minutes=30), self.path,
                                       dry_run=False, test_mode=False,
                                       channel="@dailynewsagents", private_chat="private123"), 0)
            self.assertEqual(len(sent), 2)
            state = brief.load_state(self.path)
            self.assertTrue(state["slots"]["2026-10-26:morning"]["sent"]["personal"])

    def test_partial_failure_records_only_accepted_destination(self):
        def sender(_, __, chat):
            if chat == "private123":
                raise RuntimeError("Telegram denied")
        with (patch.object(brief, "fetch_feed", side_effect=self.fetch),
              patch.object(brief, "OUTPUT_FILE", self.output),
              patch.object(brief, "send_telegram", side_effect=sender),
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"})):
            self.assertEqual(brief.run(AM, self.path, dry_run=False, test_mode=False,
                                       channel="@dailynewsagents", private_chat="private123"), 1)
            delivered = brief.load_state(self.path)["slots"]["2026-10-26:morning"]["sent"]
            self.assertTrue(delivered["channel"])
            self.assertNotIn("personal", delivered)

    def test_all_failed_index_sources_sends_nothing(self):
        with (patch.object(brief, "fetch_feed", side_effect=OSError("offline")),
              patch.object(brief, "OUTPUT_FILE", self.output),
              patch.object(brief, "send_telegram") as send):
            self.assertEqual(brief.run(AM, self.path, dry_run=False, test_mode=False,
                                       channel="@dailynewsagents", private_chat=""), 1)
            send.assert_not_called()
            self.assertFalse(self.path.exists())

    def test_empty_but_healthy_sources_produce_truthful_report(self):
        with (patch.object(brief, "fetch_feed", return_value=[]),
              patch.object(brief, "OUTPUT_FILE", self.output),
              patch.object(brief, "send_telegram") as send,
              patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"})):
            self.assertEqual(brief.run(AM, self.path, dry_run=False, test_mode=False,
                                       channel="@dailynewsagents", private_chat=""), 0)
            self.assertIn("No new qualifying headlines", send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
