"""Offline regression tests for visual edition collection, Khmer grounding and Telegram stages."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import visual_news as v

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def story(name="GitHub Blog", title="New security release 8", offset=1, edition="tech"):
    urls = {
        "GitHub Blog": "https://github.blog/changelog/secure-release",
        "BBC World": "https://www.bbc.com/news/world-event",
        "MacRumors": "https://www.macrumors.com/2026/10/30/mac-news",
    }
    return {
        "source": name, "title": title,
        "url": urls.get(name, "https://example.org/article"),
        "published": NOW - timedelta(hours=offset),
        "summary": "New security release 8 announced.",
    }


class StoryTrustTests(unittest.TestCase):
    def test_valid_direct_source_is_attributed_but_not_verified(self):
        result = v.normalize_story(story(), "tech", NOW)
        self.assertEqual(result["publisher"], "GitHub Blog")
        self.assertEqual(result["source_kind"], "direct")
        self.assertEqual(result["status"], "reported")
        self.assertEqual(result["excerpt"], "New security release 8 announced.")

    def test_rejects_forged_direct_domain(self):
        forged = dict(story(), url="https://github.blog.evil.example/security")
        self.assertIsNone(v.normalize_story(forged, "tech", NOW))

    def test_source_links_must_use_https_without_inline_credentials(self):
        for url in ("http://github.blog/changelog/secure-release",
                    "https://user:password@github.blog/changelog/secure-release",
                    "https://github.blog.evil.example/release"):
            with self.subTest(url=url):
                self.assertIsNone(v.normalize_story(dict(story(), url=url), "tech", NOW))

    def test_google_index_requires_named_reviewed_publisher(self):
        raw = dict(story(), source="Google News Cambodia English",
                   publisher="Cambodianess",
                   title="Cambodia development update",
                   url="https://news.google.com/rss/articles/abc")
        selected = v.normalize_story(raw, "cambodia", NOW)
        self.assertEqual(selected["publisher"], "Cambodianess")
        self.assertEqual(selected["source_kind"], "indexed")
        self.assertEqual(selected["excerpt"], "")
        self.assertEqual(selected["status"], "reported")
        self.assertIsNone(v.normalize_story(dict(raw, publisher="Unknown Trending Viral"), "cambodia", NOW))
        self.assertIsNone(v.normalize_story(dict(raw, url="https://danger.example/rss/articles/abc"), "cambodia", NOW))

    def test_gadget_rejects_other_publishers_and_expired_stories(self):
        valid = v.normalize_story(story("MacRumors", "New Mac display rumors", offset=35),
                                  "gadget", NOW)
        self.assertEqual(valid["publisher"], "MacRumors")
        self.assertIsNone(v.normalize_story(story(), "gadget", NOW))
        self.assertIsNone(v.normalize_story(story("MacRumors", offset=200), "gadget", NOW))

    def test_rejects_stale_and_future_dates(self):
        self.assertIsNone(v.normalize_story(story(offset=50), "tech", NOW))
        self.assertIsNone(v.normalize_story(story(offset=-2), "tech", NOW))
        self.assertIsNone(v.normalize_story(dict(story(), published=None), "tech", NOW))

    def test_edition_feed_lists_are_separate(self):
        self.assertTrue(any("Google News Cambodia" in x[0] for x in v.feeds_for("cambodia")))
        self.assertTrue(any("BBC World" in x[0] for x in v.feeds_for("global")))
        self.assertTrue(any("GitHub Blog" in x[0] for x in v.feeds_for("tech")))
        self.assertTrue(any("MacRumors" in x[0] for x in v.feeds_for("gadget")))

    def test_collect_partial_feed_failure_no_fabrication(self):
        with (patch.object(v, "feeds_for", return_value=[
                ("Broken", "https://bad.invalid"), ("GitHub Blog", "https://github.blog/feed/")]),
              patch.object(v.news_radar, "fetch_feed",
                           side_effect=[OSError("offline"), [story()]])):
            selected, health = v.collect("tech", NOW)
        self.assertEqual(len(selected), 1)
        self.assertEqual(health["failed"], ["Broken"])

    def test_all_feed_failures_block_publishing(self):
        with (patch.object(v, "feeds_for", return_value=[("Broken", "https://bad.invalid")]),
              patch.object(v.news_radar, "fetch_feed", side_effect=OSError("offline"))):
            with self.assertRaisesRegex(RuntimeError, "All configured RSS"):
                v.collect("tech", NOW)


class TranslationTests(unittest.TestCase):
    def test_fallback_does_not_invent_details(self):
        item = v.normalize_story(story(), "tech", NOW)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            v.apply_khmer_translation([item])
        self.assertEqual(item["khmer_title"], item["title"])
        self.assertIn("សូមអានអត្ថបទដើម", item["khmer_summary"])
        self.assertEqual(item["translation_status"], "original_title")

    def test_khmer_and_ascii_digits_are_compared_by_value(self):
        self.assertEqual(v.extract_numbers("តម្លៃ ៨ និង 20.5"), {"8", "20.5"})
        self.assertEqual(v.extract_numbers("8 vs ៨"), {"8"})
        self.assertNotEqual(v.extract_numbers("១០០"), v.extract_numbers("200"))

    def test_khmer_headline_preserved(self):
        raw = dict(story(), title="ព័ត៌មានថ្មីអំពីសុវត្ថិភាព")
        item = v.normalize_story(raw, "tech", NOW)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            v.apply_khmer_translation([item])
        self.assertEqual(item["translation_status"], "already_khmer")

    def test_reject_ai_translation_with_unsupported_numbers(self):
        item = v.normalize_story(story(), "tech", NOW)
        output = {"choices": [{"message": {"content": json.dumps({"items": [{
            "id": item["id"], "title_km": "ព័ត៌មានថ្មី មានតម្លៃ 999 ដុល្លារ",
            "summary_km": "",
        }]})}}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps(output).encode()
        with (patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake-token"}),
              patch.object(v, "urlopen", return_value=Response())):
            v.apply_khmer_translation([item])
        self.assertEqual(item["translation_status"], "original_title")


class CaptionTests(unittest.TestCase):
    def setUp(self):
        self.item = v.normalize_story(story(), "tech", NOW)
        v.khmer_fallback(self.item)

    def test_caption_attribution_without_verified_badge(self):
        msg = v.full_caption([self.item], "tech", NOW)
        self.assertIn("GitHub Blog", msg)
        self.assertIn("https://github.blog/", msg)
        self.assertIn("រាយការណ៍", msg)
        self.assertNotIn("✅ បានបញ្ជាក់", msg)
        self.assertIn("2026-10-30", msg)

    def test_telegram_photo_caption_within_limit(self):
        msg = v.short_caption([self.item], "tech", "2026-10-30 ICT")
        self.assertLess(len(msg), 921)

    def test_late_cron_is_detected_in_utc(self):
        intended = "5 2 * * *"
        self.assertEqual(v.scheduled_lateness_minutes(
            intended, datetime(2026, 10, 30, 2, 25, tzinfo=timezone.utc)), 20)
        self.assertEqual(v.scheduled_lateness_minutes(
            intended, datetime(2026, 10, 30, 4, 5, tzinfo=timezone.utc)), 120)
        self.assertIsNone(v.scheduled_lateness_minutes("0 0 * * *", NOW))

    def test_different_editions_and_dayparts_get_distinct_keys(self):
        morning = datetime(2026, 10, 30, 1, tzinfo=timezone.utc)
        afternoon = datetime(2026, 10, 30, 7, tzinfo=timezone.utc)
        self.assertNotEqual(v.slot_for("cambodia", morning), v.slot_for("cambodia", afternoon))
        self.assertNotEqual(v.slot_for("global", morning), v.slot_for("tech", morning))


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "visual.json"
        self.poster = Path(self.tmp.name) / "poster.png"
        self.poster.write_bytes(b"fake-png-test-bytes")
        self.item = v.normalize_story(story(), "tech", NOW)
        v.khmer_fallback(self.item)

    def test_partial_photo_failure_preserves_progress_and_retries_text_only(self):
        sent = []
        def sender(token, endpoint, fields, image=None):
            sent.append(endpoint)
            if len(sent) == 2:
                raise RuntimeError("Telegram text timeout")
            return len(sent)
        with (patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"}),
              patch.object(v, "telegram_api", side_effect=sender)):
            self.assertEqual(v.send_edition("tech", NOW, [self.item], self.poster,
                                            self.state, {"channel": "@example"}), 1)
            state = v.read_state(self.state)
            staged = state["deliveries"][v.slot_for("tech", NOW)]["destinations"]["channel"]
            self.assertTrue(staged["photo_sent"])
            self.assertFalse(staged.get("text_sent", False))
            self.assertEqual(v.send_edition("tech", NOW, [self.item], self.poster,
                                            self.state, {"channel": "@example"}), 0)
        self.assertEqual(sent, ["sendPhoto", "sendMessage", "sendMessage"])

    def test_existing_delivery_skips_duplicates(self):
        with (patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"}),
              patch.object(v, "telegram_api", return_value=123) as api):
            self.assertEqual(v.send_edition("tech", NOW, [self.item], self.poster,
                                            self.state, {"channel": "@example"}), 0)
            self.assertEqual(v.send_edition("tech", NOW, [self.item], self.poster,
                                            self.state, {"channel": "@example"}), 0)
            self.assertEqual(api.call_count, 2)

    def test_stages_merge_monotonically(self):
        slot = v.slot_for("tech", NOW)
        current = {"deliveries": {slot: {"destinations": {"channel": {
            "photo_sent": True, "text_sent": True, "report": "original"
        }}}}}
        incoming = {"deliveries": {slot: {"destinations": {"channel": {
            "photo_sent": True, "text_sent": False, "report": "stale"
        }}}}}
        merged = v.merge_state(current, incoming)
        self.assertTrue(merged["deliveries"][slot]["destinations"]["channel"]["text_sent"])
        self.assertEqual(merged["deliveries"][slot]["destinations"]["channel"]["report"], "original")

    def test_dry_run_creates_report_without_telegram_or_state(self):
        import sys
        from types import SimpleNamespace
        with (patch.object(v, "collect", return_value=(
                  [self.item], {"eligible": 1, "working": ["GitHub"], "failed": []})),
              patch.object(v, "apply_khmer_translation"),
              patch.dict(sys.modules, {"visual_poster": SimpleNamespace(
                  render_poster=lambda *args: self.poster)}),
              patch.object(v, "send_edition") as send):
            output = Path(self.tmp.name) / "out"
            status = v.execute("tech", dry_run=True, test_mode=True,
                               channel="", private_chat="", now=NOW,
                               state_path=self.state, output=output)
            self.assertEqual(status, 0)
            self.assertTrue((output / "tech-latest.html").exists())
            self.assertFalse(self.state.exists())
            send.assert_not_called()

    def test_resume_photo_only_without_recollecting_or_resending_photo(self):
        slot = v.slot_for("tech", NOW)
        v.save_state({"deliveries": {slot: {"destinations": {"channel": {
            "photo_sent": True, "text_sent": False, "report": "original sourced report",
            "stories": [self.item["id"]],
        }}}}}, self.state)
        with (patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake", "NEWS_SCHEDULE_CRON": ""}),
              patch.object(v, "approval_for_slot",
                           return_value={"stories": [{"id": self.item["id"]}]}),
              patch.object(v, "telegram_api", return_value=678) as api,
              patch.object(v, "collect") as collect):
            status = v.execute("tech", dry_run=False, test_mode=False,
                               channel="@example", private_chat="", now=NOW,
                               state_path=self.state, output=Path(self.tmp.name) / "out")
            self.assertEqual(status, 0)
            collect.assert_not_called()
            self.assertEqual(api.call_count, 1)
            self.assertEqual(api.call_args.args[1], "sendMessage")
            self.assertEqual(api.call_args.args[2]["text"], "original sourced report")
            self.assertTrue(v.read_state(self.state)["deliveries"][slot]
                            ["destinations"]["channel"]["text_sent"])

    def test_unreviewed_public_english_story_cannot_publish(self):
        # The stronger editorial gate now blocks public posts before calling
        # an AI model or even collecting headlines. Khmer script alone was
        # never sufficient evidence of a correct translation.
        with (patch.dict(os.environ, {"VISUAL_REQUIRE_KHMER": "true",
                                      "TELEGRAM_BOT_TOKEN": "fake",
                                      "NEWS_SCHEDULE_CRON": "",
                                      "OPENROUTER_API_KEY": ""}),
              patch.object(v, "collect") as collect,
              patch.object(v, "send_edition") as send):
            with self.assertRaisesRegex(ValueError, "no human-reviewed"):
                v.execute("tech", dry_run=False, test_mode=False,
                          channel="@example", private_chat="", now=NOW,
                          state_path=self.state, output=Path(self.tmp.name) / "out")
            collect.assert_not_called()
            send.assert_not_called()

    def test_delayed_scheduled_run_does_not_collect_or_send(self):
        intended = datetime(2026, 10, 30, 4, 5, tzinfo=timezone.utc)
        with (patch.dict(os.environ, {"NEWS_SCHEDULE_CRON": "5 2 * * *"}),
              patch.object(v, "collect") as collect,
              patch.object(v, "send_edition") as send):
            with self.assertRaisesRegex(RuntimeError, "too late"):
                v.execute("cambodia", dry_run=False, test_mode=False,
                          channel="@example", private_chat="", now=intended,
                          state_path=self.state, output=Path(self.tmp.name) / "out")
            collect.assert_not_called()
            send.assert_not_called()

    def test_partial_fanout_blocks_changed_story_selection(self):
        slot = v.slot_for("tech", NOW)
        v.save_state({"deliveries": {slot: {"destinations": {
            "channel": {"photo_sent": True, "text_sent": True, "stories": ["old-digest"],
                        "report": "Already delivered"}}
        }}}, self.state)
        new_item = dict(self.item, id="brand-new-story")
        with (patch.dict(os.environ, {"NEWS_SCHEDULE_CRON": "", "OPENROUTER_API_KEY": ""}),
              patch.object(v, "approval_for_slot",
                           return_value={"stories": [{"id": "old-digest"}]}),
              patch.object(v, "collect", return_value=(
                  [new_item], {"eligible": 1, "working": ["GitHub"], "failed": []})),
              patch.object(v, "send_edition") as send):
            with self.assertRaisesRegex(RuntimeError, "selection changed"):
                v.execute("tech", dry_run=False, test_mode=False,
                          channel="@example", private_chat="private1", now=NOW,
                          state_path=self.state, output=Path(self.tmp.name) / "out")
            send.assert_not_called()

    def test_private_test_labels_photo_and_full_report(self):
        sent = []
        def fake_send(token, endpoint, fields, image=None):
            sent.append((endpoint, fields))
            return 18
        with (patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"}),
              patch.object(v, "telegram_api", side_effect=fake_send)):
            self.assertEqual(v.send_edition("tech", NOW, [self.item], self.poster,
                                            self.state, {"personal": "private1"},
                                            test_mode=True), 0)
        self.assertIn("TEST ONLY", sent[0][1]["caption"])
        self.assertIn("TEST ONLY", sent[1][1]["text"])
        self.assertFalse(self.state.exists())

    def test_invalid_state_fails_closed(self):
        self.state.write_text("[]")
        with self.assertRaises(ValueError):
            v.read_state(self.state)



class TelegramTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / "poster.png"
        self.file.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + b"test-image-content")

    def test_send_photo_uses_multipart_and_keeps_caption(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b'{"ok":true,"result":{"message_id":112}}'

        with patch.object(v, "urlopen", return_value=Response()) as http:
            message_id = v.telegram_api(
                "fake-token", "sendPhoto",
                {"chat_id": "@example", "caption": "សេចក្ដីសង្ខេប"}, self.file
            )
        self.assertEqual(message_id, 112)
        request = http.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.full_url.endswith("/sendPhoto"))
        self.assertIn("multipart/form-data", request.get_header("Content-type"))
        self.assertIn(b'name="photo"', request.data)
        self.assertIn(b'name="caption"', request.data)
        self.assertIn("សេចក្ដីសង្ខេប".encode(), request.data)
        self.assertIn(self.file.read_bytes(), request.data)

    def test_telegram_rejection_fails_without_fake_acknowledgement(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return b'{"ok":false,"description":"Bad Request"}'
        with patch.object(v, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(RuntimeError, "Telegram rejected sendMessage"):
                v.telegram_api("fake-token", "sendMessage", {"chat_id": "1", "text": "test"})




if __name__ == "__main__":
    unittest.main()
