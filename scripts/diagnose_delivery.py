#!/usr/bin/env python3
"""Read-only GitHub Actions incident overview. Never sends Telegram or changes a cluster.

WARNING: REST workflow run created_at is NOT the intended cron fire time.
The script deliberately does not claim schedule punctuality from that field.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

KH = timezone(timedelta(hours=7))


def iso_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def summarize(runs: list[dict]) -> list[dict]:
    result = []
    for record in runs:
        if record.get("event") != "schedule":
            continue
        created = record.get("created_at")
        if not created:
            continue
        start = iso_time(created).astimezone(KH)
        status = record.get("status")
        conclusion = record.get("conclusion") or "unknown"
        result.append({
            "workflow": record.get("name") or "unknown",
            "id": record.get("id"),
            "local_started": start.strftime("%Y-%m-%d %H:%M:%S ICT"),
            "status": status,
            "conclusion": conclusion,
            "link": record.get("html_url") or "",
            "cron_start_lag": "NOT AVAILABLE from this API",
            "telegram_accepted": "NOT VERIFIED from run status",
        })
    return result


def list_runs(repo: str, count: int) -> list[dict]:
    if not (repo.count("/") == 1 and
            all(part.replace("-", "").replace("_", "").isalnum() for part in repo.split("/"))):
        raise ValueError("Repository must be owner/repo")
    url = f"https://api.github.com/repos/{repo}/actions/runs?branch=main&per_page={count}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "news-radar-diagnostics/1.0"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    with urlopen(Request(url, headers=headers), timeout=20) as response:
        return json.load(response)["workflow_runs"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Dapravith/ai-tech-news-radar")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--runs-json", type=Path, help="Offline GitHub API JSON fixture")
    args = parser.parse_args()
    if not (1 <= args.count <= 100):
        parser.error("--count must be between 1 and 100")
    if args.runs_json:
        payload = json.loads(args.runs_json.read_text(encoding="utf-8"))
        runs = payload["workflow_runs"] if isinstance(payload, dict) else payload
    else:
        runs = list_runs(args.repo, args.count)
    entries = summarize(runs)
    print(json.dumps({"scheduled_runs": entries, "notes": [
        "GitHub Actions success is not proof of Telegram delivery.",
        "The GitHub workflow run API does NOT expose original planned cron time here.",
        "Inspect workflow job logs for INFO: Telegram acknowledged and NEWS_SCHEDULE_CRON delay warnings.",
        "ERROR lines from unittest negative-path cases do not demonstrate production failure.",
        "Confirm state persistence, channel/private delivery, and the final report timestamp.",
    ]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
