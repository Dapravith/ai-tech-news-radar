"""Fail-closed Khmer visual-news validation and per-story editorial approval.

Unicode and model-output checks can prevent broken glyphs and invented figures;
they CANNOT determine whether Khmer prose is natural or claims are truthful.
Only an explicit human-reviewed, source-bound copy may be published publicly.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import unicodedata

DEFAULT_APPROVAL_FILE = Path(__file__).resolve().parent / "config" / "visual_editorial_approvals.json"
DISALLOWED_SQUARES = set("□▯▢▣☐■�")
# Unsupported scripts shouldn't silently render as .notdef boxes in a Khmer poster.
# The source article remains available in the linked full report.
KHMER_RANGE = range(0x1780, 0x1800)


def normalize_visual_text(value: str, *, require_khmer: bool = False,
                          max_length: int = 180) -> str:
    if not isinstance(value, str):
        raise ValueError("Poster text must be a string")
    value = unicodedata.normalize("NFC", value).replace("\u200b", " ")
    value = " ".join(value.split())
    if not value or len(value) > max_length:
        raise ValueError("Poster text is empty or exceeds its length limit")
    if any(char in DISALLOWED_SQUARES for char in value):
        raise ValueError("Poster text contains missing-glyph placeholders")
    for char in value:
        cp = ord(char)
        cat = unicodedata.category(char)
        if cat in {"Cc", "Cs", "Co", "Cn"}:
            raise ValueError("Poster text contains unsupported control/unknown characters")
        if cat == "Cf":
            raise ValueError("Poster text contains hidden format characters")
        if cp in KHMER_RANGE:
            continue
        # English proper names and numbers, common punctuation/currency signs.
        if (cp <= 0x024F or 0x2000 <= cp <= 0x206F or
                cp in {0x20AC, 0x2116, 0x2122}):
            continue
        raise ValueError(f"Poster text uses an unsupported script (U+{cp:04X})")
    if require_khmer:
        letters = sum(1 for char in value if 0x1780 <= ord(char) <= 0x17A2)
        if letters < 5:
            raise ValueError("Headline is not a meaningful Khmer-language candidate")
    return value


def read_approvals(path: Path = DEFAULT_APPROVAL_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError("Editorial approvals missing; public publishing is blocked") from exc
    if not isinstance(data, dict) or not isinstance(data.get("slots"), dict):
        raise ValueError("Editorial approvals file is invalid")
    return data


def approval_for_slot(approvals: dict, slot: str, edition: str) -> dict:
    entry = approvals.get("slots", {}).get(slot)
    if not isinstance(entry, dict) or entry.get("edition") != edition:
        raise ValueError("This edition has no human-reviewed story set; public posting blocked")
    reviewer = entry.get("reviewed_by", "")
    timestamp = entry.get("reviewed_at", "")
    if not isinstance(reviewer, str) or len(reviewer.strip()) < 2:
        raise ValueError("Editorial reviewer identity is missing")
    try:
        approved_at = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError) as exc:
        raise ValueError("Editorial approval timestamp is invalid") from exc
    if approved_at.tzinfo is None:
        raise ValueError("Editorial approval timestamp requires a timezone")
    stories = entry.get("stories")
    if not isinstance(stories, list) or not (1 <= len(stories) <= 3):
        raise ValueError("Editorial approval has no usable stories")
    ids = [item.get("id") for item in stories if isinstance(item, dict)]
    if len(ids) != len(stories) or not all(isinstance(i, str) and i for i in ids):
        raise ValueError("Editorial approval story IDs are invalid")
    if len(set(ids)) != len(ids):
        raise ValueError("Editorial approval contains repeated story IDs")
    return entry


def apply_approved_copy(items: list[dict], entry: dict) -> None:
    """Require exact, ordered story IDs, URL, title and publish timestamp."""
    reviewed = entry["stories"]
    if [item["id"] for item in items] != [item["id"] for item in reviewed]:
        raise ValueError("Selected RSS stories differ from approved editorial stories")
    staged = []
    for original, approval in zip(items, reviewed):
        if (original["title"] != approval.get("source_title") or
            original["url"] != approval.get("source_url") or
            original["published"].isoformat() != approval.get("source_published_at")):
            raise ValueError("Source story changed after editorial review")
        title = normalize_visual_text(approval.get("khmer_title", ""),
                                      require_khmer=True, max_length=125)
        summary = normalize_visual_text(approval.get("khmer_summary", ""),
                                        require_khmer=True, max_length=250)
        staged.append((title, summary))
    for item, (title, summary) in zip(items, staged):
        item["khmer_title"] = title
        item["khmer_summary"] = summary
        item["translation_status"] = "human_editorial_approved"


def review_request(edition: str, slot: str, items: list[dict]) -> dict:
    """Preview artifact to edit in a protected PR before next scheduled post."""
    return {"slots": {slot: {
        "edition": edition,
        "reviewed_by": "REPLACE_WITH_HUMAN_REVIEWER",
        "reviewed_at": "REPLACE_WITH_TIMEZONE_AWARE_ISO_8601",
        "stories": [{
            "id": item["id"], "source_title": item["title"],
            "source_url": item["url"],
            "source_published_at": item["published"].isoformat(),
            "khmer_title": item.get("khmer_title", item["title"]),
            "khmer_summary": item.get("khmer_summary", "សូមអានអត្ថបទដើមសម្រាប់ព័ត៌មានលម្អិត។"),
        } for item in items],
    }}}
