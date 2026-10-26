"""Offline regression tests for two-channel 08:00 digest publishing."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import channel_digest as digest


NOW = datetime(2026, 10, 17, 1, 0, tzinfo=timezone.utc)


def story(title, url, *, source="GitHub Blog", hours=2, summary=""):
    return {
        "title": title,
        "url": url,
        "source": source,
        "published": NOW - timedelta(hours=hours),
        "summary": summary,
    }


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.config = digest.load_config()

    def test_crypto_is_excluded_from_both_channels(self):
        sample = story("Bitcoin and crypto token prices jump", "https://example.org/crypto")
        for channel in self.config["channels"].values():
            self.assertEqual(digest.classify(sample, channel["topics"])[0], None)

    def test_primary_feeds_replace_social_ranked_links(self):
        feeds = {feed["name"] for feed in self.config["feeds"]}
        self.assertIn("UK NCSC News", feeds)
        self.assertIn("Spring Blog", feeds)
        self.assertNotIn("Hacker News", feeds)

    def test_it_security_only_goes_to_it(self):
        sample = story("Ransomware incident hits corporate network", "https://example.org/security")
        it = self.config["channels"]["it_support"]["topics"]
        software = self.config["channels"]["software"]["topics"]
        self.assertIsNotNone(digest.classify(sample, it)[0])
        self.assertIsNone(digest.classify(sample, software)[0])

    def test_social_network_headline_is_not_it_operations(self):
        sample = story("New social network for developers", "https://example.org/social")
        it = self.config["channels"]["it_support"]["topics"]
        self.assertIsNone(digest.classify(sample, it)[0])

    def test_cloudflare_marketing_headline_is_not_it_ops(self):
        sample = story("Cloudflare and OpenAI announce AI discovery initiative",
                       "https://example.org/marketing")
        it = self.config["channels"]["it_support"]["topics"]
        self.assertIsNone(digest.classify(sample, it)[0])

    def test_frontend_only_goes_to_software(self):
        sample = story("Next.js and Vue frontend changes", "https://example.org/frontend")
        self.assertIsNone(digest.classify(sample, self.config["channels"]["it_support"]["topics"])[0])
        self.assertIsNotNone(digest.classify(sample, self.config["channels"]["software"]["topics"])[0])

    def test_requires_title_keyword_not_just_description(self):
        sample = story("Weekend sports results", "https://example.org/sport",
                       summary="DevOps Kubernetes infrastructure")
        for channel in self.config["channels"].values():
            self.assertIsNone(digest.classify(sample, channel["topics"])[0])

    def test_older_production_articles_are_skipped(self):
        sample = story("Critical ransomware security patch", "https://example.org/old", hours=73)
        it = self.config["channels"]["it_support"]
        self.assertEqual(digest.choose_stories([sample], it, NOW, set()), [])

    def test_seen_url_not_repeated(self):
        sample = story("Docker Kubernetes infrastructure outage", "https://example.org/outage")
        it = self.config["channels"]["it_support"]
        key = digest.make_id({"url": sample["url"]})
        self.assertEqual(digest.choose_stories([sample], it, NOW, {key}), [])

    def test_html_is_escaped_in_message(self):
        sample = story("Security patch <script>alert(1)</script>", "https://example.org/patch")
        sample["category"] = "Security & Incident Response"
        message = digest.render(self.config["channels"]["it_support"], [sample], NOW)
        self.assertNotIn("<script>", message)
        self.assertIn("Security patch alert(1)", message)
        self.assertNotIn("<script", message)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.config = digest.load_config()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "channel_seen.json"
        self.out = Path(self.temp.name) / "out"
        self.feeds = {
            "GitHub Blog": [
                story("Next.js software developer framework release", "https://example.org/dev"),
                story("Ransomware incident affects network firewall", "https://example.org/ops"),
            ],
            "Cloudflare Blog": [
                story("Critical vulnerability in network firewall", "https://example.org/firewall")
            ],
        }

    def fake_fetch(self, source, _url):
        if source in self.feeds:
            return self.feeds[source]
        return []

    def test_both_channels_receive_separate_categories_and_dedupe(self):
        calls = []
        def send(message, token, chat):
            calls.append((message, chat))
        with (patch.object(digest, "fetch_feed", side_effect=self.fake_fetch),
              patch.object(digest, "send_telegram", side_effect=send),
              patch.object(digest, "OUT_DIR", self.out),
              patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake"}, clear=False)):
            self.assertEqual(digest.run(self.config, self.path, dry_run=False,
                                        test_mode=False, now=NOW), 0)
            self.assertEqual(len(calls), 2)
            by_dest = {dest: msg for msg, dest in calls}
            self.assertIn("@botsupportive", by_dest)
            self.assertIn("@sedev2027", by_dest)
            self.assertIn("ransomware", by_dest["@botsupportive"].lower())
            self.assertNotIn("next.js", by_dest["@botsupportive"].lower())
            self.assertIn("next.js", by_dest["@sedev2027"].lower())
            self.assertNotIn("ransomware", by_dest["@sedev2027"].lower())
            # Even a manual replay the same local day does not duplicate posts.
            self.assertEqual(digest.run(self.config, self.path, dry_run=False,
                                        test_mode=False, now=NOW), 0)
            self.assertEqual(len(calls), 2)

    def test_backup_schedule_skips_fetch_when_both_channels_delivered(self):
        today = NOW.astimezone(digest.TZ_KH).date().isoformat()
        digest.write_state({
            "it_support": {today: {"ids": ["one"], "delivered": True}},
            "software": {today: {"ids": ["two"], "delivered": True}},
        }, self.path)
        with (patch.object(digest, "fetch_feed") as fetch,
              patch.object(digest, "send_telegram") as send):
            self.assertEqual(digest.run(self.config, self.path, dry_run=False,
                                        test_mode=False, now=NOW), 0)
            fetch.assert_not_called()
            send.assert_not_called()

    def test_partial_failure_preserves_first_success(self):
        called = []
        def send(_msg, _token, chat):
            called.append(chat)
            if chat == "@sedev2027":
                raise RuntimeError("Telegram failed")
        with (patch.object(digest, "fetch_feed", side_effect=self.fake_fetch),
              patch.object(digest, "send_telegram", side_effect=send),
              patch.object(digest, "OUT_DIR", self.out),
              patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake"}, clear=False)):
            self.assertEqual(digest.run(self.config, self.path, dry_run=False,
                                        test_mode=False, now=NOW), 1)
            state = digest.load_state(self.path)
            self.assertTrue(state["it_support"]["2026-10-17"]["delivered"])
            self.assertNotIn("software", state)
            self.assertEqual(digest.run(self.config, self.path, dry_run=False,
                                        test_mode=False, now=NOW), 1)
            self.assertEqual(called, ["@botsupportive", "@sedev2027", "@sedev2027"])

    def test_dry_run_does_not_send_or_update_state(self):
        with (patch.object(digest, "fetch_feed", side_effect=self.fake_fetch),
              patch.object(digest, "send_telegram") as sender,
              patch.object(digest, "OUT_DIR", self.out)):
            self.assertEqual(digest.run(self.config, self.path, dry_run=True,
                                        test_mode=True, now=NOW), 0)
            sender.assert_not_called()
            self.assertFalse(self.path.exists())

    def test_all_sources_unavailable_sends_nothing(self):
        with (patch.object(digest, "fetch_feed", side_effect=RuntimeError("offline")),
              patch.object(digest, "send_telegram") as sender,
              patch.object(digest, "OUT_DIR", self.out)):
            self.assertEqual(digest.run(self.config, self.path, dry_run=False,
                                        test_mode=False, now=NOW), 1)
            sender.assert_not_called()

    def test_state_merge_preserves_both_channels(self):
        old = {"it_support": {"2026-10-17": {"delivered": True, "ids": ["a"]}}}
        newer = {"software": {"2026-10-17": {"delivered": True, "ids": ["b"]}},
                 "it_support": {"2026-10-17": {"delivered": True, "ids": ["a", "c"]}}}
        got = digest.merge_state(old, newer)
        self.assertEqual(got["it_support"]["2026-10-17"]["ids"], ["a", "c"])
        self.assertEqual(got["software"]["2026-10-17"]["ids"], ["b"])


if __name__ == "__main__":
    unittest.main()
