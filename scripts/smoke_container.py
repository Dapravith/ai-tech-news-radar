#!/usr/bin/env python3
"""Offline end-to-end shadow smoke test for the actual container runtime.

Run with --network none, --read-only and a writable /app/out tmpfs.
A mocked feed means neither external RSS nor Telegram/network access is needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from unittest.mock import patch

import cambodia_brief as news


def main() -> int:
    now = datetime(2026, 10, 27, 5, 25, tzinfo=timezone.utc)  # 12:25 ICT
    article = {
        "title": "Cambodia renewable energy innovation expands",
        "publisher": "Cambodianess",
        "source": "Google News Cambodia English",
        "url": "https://news.google.com/rss/articles/shadow-test",
        "published": now - timedelta(minutes=12),
        "summary": "Mocked article: this is not real news.",
    }
    output = Path("/app/out")
    if not output.exists():
        raise RuntimeError("Container must mount writable /app/out tmpfs")
    state = output / "shadow-smoke-state.json"
    report = output / "cambodia_latest.html"
    if state.exists():
        state.unlink()
    with (patch.object(news, "OUTPUT_FILE", report),
          patch.object(news, "fetch_feed", return_value=[article]),
          patch.object(news, "send_telegram") as telegram,
          patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": ""})):
        result = news.run(now, state, dry_run=True, test_mode=True,
                          private_chat="", channel="@no-production-destination")
        telegram.assert_not_called()
    text = report.read_text(encoding="utf-8")
    assert result == 0, f"Expected success in dry-run, got {result}"
    assert "AFTERNOON" in text, "Daypart mismatch"
    assert "Cambodianess" in text, "Publisher was not preserved"
    assert "1 curated headlines" in text, "One vetted article was expected"
    assert not state.exists(), "Dry-run MUST NOT persist delivery state"
    print("PASS: offline, read-only, nonroot, no-network news run and no Telegram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
