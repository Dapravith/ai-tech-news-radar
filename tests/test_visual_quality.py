"""Editorial quality gate tests; runs even when Pillow/fonts are absent."""
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import visual_news as news
import visual_quality as quality


class CopyValidationTests(unittest.TestCase):
    def test_valid_khmer_and_english_product_name(self):
        text = "ព័ត៌មានថ្មីអំពី Apple MacBook Pro និង Samsung W27"
        self.assertEqual(quality.normalize_visual_text(text, require_khmer=True), text)

    def test_rejects_tofu_and_unsupported_foreign_script(self):
        for text in ("ព័ត៌មានថ្មី □□□□", "ព័ត៌មានថ្មី �", "ប្រភព 世界",
                     "ទិន្នន័យ ☐", "ខ្មែរ \u200d ព័ត៌មាន"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                quality.normalize_visual_text(text)

    def test_zero_width_spaces_are_made_visible(self):
        self.assertEqual(quality.normalize_visual_text("ព័ត៌មាន\u200bថ្មី"), "ព័ត៌មាន ថ្មី")

    def test_khmer_language_required_when_reviewing_copy(self):
        with self.assertRaises(ValueError):
            quality.normalize_visual_text("Apple W27 OLED", require_khmer=True)


class EditorialApprovalTests(unittest.TestCase):
    def setUp(self):
        self.slot = "2026-10-31:cambodia:morning"
        self.now = datetime(2026, 10, 31, 1, 0, tzinfo=timezone.utc)
        self.stories = [{
            "id": "article-001", "title": "New Cambodia technology policy",
            "url": "https://news.google.com/rss/articles/example",
            "published": self.now, "publisher": "Cambodianess",
            "source_kind": "indexed", "edition": "cambodia",
        }]
        self.request = quality.review_request("cambodia", self.slot, self.stories)
        self.approval = self.request["slots"][self.slot]
        self.approval["reviewed_by"] = "News editor"
        self.approval["reviewed_at"] = "2026-10-31T08:15:00+07:00"
        self.approval["stories"][0]["khmer_title"] = "ព័ត៌មានថ្មីអំពីគោលនយោបាយបច្ចេកវិទ្យាកម្ពុជា"
        self.approval["stories"][0]["khmer_summary"] = "សេចក្ដីសង្ខេបខ្លីដែលអ្នកកែសម្រួលបានផ្ទៀងផ្ទាត់។"

    def test_missing_review_is_not_a_technical_success(self):
        with self.assertRaisesRegex(ValueError, "no human-reviewed"):
            quality.approval_for_slot({"slots": {}}, self.slot, "cambodia")

    def test_approved_source_and_khmer_copy_apply_exactly(self):
        entry = quality.approval_for_slot(self.request, self.slot, "cambodia")
        quality.apply_approved_copy(self.stories, entry)
        self.assertEqual(self.stories[0]["translation_status"], "human_editorial_approved")
        self.assertEqual(self.stories[0]["khmer_title"],
                         "ព័ត៌មានថ្មីអំពីគោលនយោបាយបច្ចេកវិទ្យាកម្ពុជា")

    def test_unknown_reviewer_or_timezone_is_rejected(self):
        self.approval["reviewed_at"] = "2026-10-31T08:15:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            quality.approval_for_slot(self.request, self.slot, "cambodia")
        self.approval["reviewed_at"] = "2026-10-31T08:15:00+07:00"
        self.approval["reviewed_by"] = ""
        with self.assertRaisesRegex(ValueError, "reviewer"):
            quality.approval_for_slot(self.request, self.slot, "cambodia")

    def test_source_url_and_original_title_changes_block_delivery(self):
        for field, altered in (("source_title", "Unreviewed other article"),
                               ("source_url", "https://evil.example/other"),
                               ("source_published_at", "2026-10-30T01:00:00+00:00")):
            approval = dict(self.approval["stories"][0])
            approval[field] = altered
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "changed"):
                quality.apply_approved_copy(self.stories, {"stories": [approval]})

    def test_source_selection_order_and_ids_must_match(self):
        item = dict(self.stories[0], id="another-story")
        with self.assertRaisesRegex(ValueError, "differ"):
            quality.apply_approved_copy([item], self.approval)

    def test_editorial_title_rejects_square_placeholders(self):
        self.approval["stories"][0]["khmer_title"] = "ព័ត៌មាន □□□□"
        with self.assertRaisesRegex(ValueError, "missing-glyph"):
            quality.apply_approved_copy(self.stories, self.approval)

    def test_default_approval_file_initially_empty(self):
        file = quality.DEFAULT_APPROVAL_FILE
        data = quality.read_approvals(file)
        self.assertEqual(data, {"slots": {}})

    def test_public_execute_refuses_unapproved_story_before_feed(self):
        with (patch.object(news, "read_approvals", return_value={"slots": {}}),
              patch.object(news, "collect") as collect,
              patch.object(news, "send_edition") as send,
              patch.dict("os.environ", {"NEWS_SCHEDULE_CRON": ""})):
            with self.assertRaisesRegex(ValueError, "no human-reviewed"):
                news.execute("cambodia", dry_run=False, test_mode=False,
                             channel="@example", private_chat="",
                             now=self.now, state_path=Path("/nonexistent/state.json"))
            collect.assert_not_called()
            send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
