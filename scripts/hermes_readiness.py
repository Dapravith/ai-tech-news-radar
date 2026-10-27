#!/usr/bin/env python3
"""Read-only Hermes A2A agent-card readiness probe. Does not send agent tasks.

Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/a2a
HTTP is permitted only for local loopback; remote origins must use HTTPS.
A2A token is never printed. The probe makes a single GET of the Agent Card.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PATH = "/.well-known/agent-card.json"


def safe_agent_url(raw: str) -> str:
    u = urlparse(raw.strip())
    if u.scheme not in {"http", "https"} or not u.hostname:
        raise ValueError("Hermes A2A URL must have http(s) and a host")
    if u.username or u.password or u.path not in {"", "/"} or u.query or u.fragment:
        raise ValueError("Supply only the clean A2A origin (no auth, path, query or fragment)")
    if u.scheme == "http" and u.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Plain HTTP is allowed for loopback only; use HTTPS remotely")
    # Do not follow any URL advertised in the card; it is untrusted metadata.
    return raw.strip().rstrip("/") + PATH


def validate_card(data: object) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Hermes Agent Card must be a JSON object")
    name = data.get("name")
    skills = data.get("skills", [])
    if not isinstance(name, str) or not name.strip() or not isinstance(skills, list):
        raise ValueError("Invalid Hermes Agent Card: name or skills missing")
    skill_names = []
    for skill in skills[:30]:
        if isinstance(skill, dict):
            label = skill.get("name")
            if isinstance(label, str):
                skill_names.append(label[:80])
    return {"ready": True, "agent": name[:100], "skill_names": skill_names,
            "checked": "Agent Card only; task execution, model availability, secrets and persistence NOT tested"}


def probe(origin: str, token: str = "", timeout: float = 8.0) -> dict:
    url = safe_agent_url(origin)
    headers = {"Accept": "application/json", "User-Agent": "news-radar-readonly-check/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("A2A Agent Card did not return 200")
        payload = response.read(65537)
    if len(payload) > 65536:
        raise ValueError("A2A Agent Card too large")
    return validate_card(json.loads(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default=os.getenv("HERMES_A2A_ORIGIN", ""))
    parser.add_argument("--fixture", type=Path, help="Offline JSON card; no network")
    args = parser.parse_args()
    try:
        if args.fixture:
            card = validate_card(json.loads(args.fixture.read_text(encoding="utf-8")))
            card["mode"] = "offline fixture"
        else:
            if not args.origin:
                parser.error("Pass --origin explicitly, or --fixture for an offline test")
            card = probe(args.origin, os.getenv("HERMES_A2A_TOKEN", ""))
            card["mode"] = "read-only remote Agent Card"
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Do not echo potentially credential-bearing network messages or URLs.
        print(json.dumps({"ready": False, "error_type": type(exc).__name__,
                          "action": "Verify gateway is running and A2A is enabled; inspect private gateway logs."}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
