"""The schedule diagnosis CLI must never invent exact cron lateness."""
import unittest

from scripts.diagnose_delivery import summarize, iso_time


class DiagnosticsTests(unittest.TestCase):
    def test_only_scheduled_runs_and_local_timestamp(self):
        runs = [
            {"event": "push", "created_at": "2026-10-27T05:20:00Z",
             "name": "Cambodia", "conclusion": "success"},
            {"event": "schedule", "created_at": "2026-10-27T05:16:09Z",
             "name": "Cambodia News Brief", "id": 99,
             "status": "completed", "conclusion": "success", "html_url": "https://github.com/example"},
        ]
        result = summarize(runs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["local_started"], "2026-10-27 12:16:09 ICT")
        self.assertEqual(result[0]["cron_start_lag"], "NOT AVAILABLE from this API")
        self.assertEqual(result[0]["telegram_accepted"], "NOT VERIFIED from run status")

    def test_failing_run_is_not_dropped(self):
        data = [{"event": "schedule", "created_at": "2026-10-27T05:30:00Z",
                 "name": "IT Digest", "id": 123, "status": "completed",
                 "conclusion": "failure"}]
        self.assertEqual(summarize(data)[0]["conclusion"], "failure")

    def test_z_utc_parse(self):
        self.assertEqual(iso_time("2026-10-27T05:16:09Z").utcoffset().total_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
