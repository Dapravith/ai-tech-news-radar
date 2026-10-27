"""Phase 2 evidence-oriented diagnostics: no infra changes or Telegram sends."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts import hermes_readiness as hermes
from scripts import preflight_k3s as k3s

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CARD = json.loads((FIXTURES / "hermes-agent-card.json").read_text(encoding="utf-8"))
CLUSTER = json.loads((FIXTURES / "k3s-ready.json").read_text(encoding="utf-8"))


class HermesReadinessTests(unittest.TestCase):
    def test_offline_card_is_read_only_metadata(self):
        result = hermes.validate_card(CARD)
        self.assertTrue(result["ready"])
        self.assertEqual(result["agent"], "Hermes News Research Sandbox")
        self.assertEqual(result["skill_names"], ["Research News"])
        self.assertIn("NOT tested", result["checked"])

    def test_refuses_insecure_remote_url_and_credentials(self):
        bad = [
            "http://not-local.example:9900", "https://user:pass@example.com",
            "ftp://example.com", "https://example.com/path",
            "https://example.com/?secret=123", "https://example.com/#frag",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                hermes.safe_agent_url(url)
        self.assertEqual(hermes.safe_agent_url("http://127.0.0.1:9900"),
                         "http://127.0.0.1:9900/.well-known/agent-card.json")
        self.assertEqual(hermes.safe_agent_url("https://agent.example.net/"),
                         "https://agent.example.net/.well-known/agent-card.json")

    def test_invalid_card_fails_closed(self):
        for card in ({}, {"name": "Agent", "skills": None}, []):
            with self.assertRaises(ValueError):
                hermes.validate_card(card)

    def test_probe_only_gets_card_never_posts_task(self):
        class FakeResponse:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, count): return json.dumps(CARD).encode()
        with patch.object(hermes, "urlopen", return_value=FakeResponse()) as http:
            result = hermes.probe("http://127.0.0.1:9900", "sensitive-test-token")
            self.assertTrue(result["ready"])
            request = http.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(request.full_url, "http://127.0.0.1:9900/.well-known/agent-card.json")
            self.assertEqual(request.headers["Authorization"], "Bearer sensitive-test-token")
            self.assertNotIn("sensitive-test-token", str(result))


class ClusterPreflightTests(unittest.TestCase):
    def test_ready_fixture(self):
        result = k3s.check_cluster(CLUSTER["nodes"], CLUSTER["version"], "k3s-news-dev")
        self.assertTrue(result["ok"])
        self.assertTrue(result["timezone_api_supported"])
        self.assertEqual(result["nodes"][0]["node"], "test-k3s-node")
        self.assertIn("does not verify SSH", result["limitations"][0])

    def test_down_node_and_pressure_fail_closed(self):
        for field in ("Ready", "MemoryPressure", "DiskPressure", "PIDPressure"):
            test = deepcopy(CLUSTER)
            conditions = test["nodes"]["items"][0]["status"]["conditions"]
            next(c for c in conditions if c["type"] == field)["status"] = (
                "False" if field == "Ready" else "True")
            result = k3s.check_cluster(test["nodes"], test["version"], "k3s-news-dev")
            with self.subTest(field=field):
                self.assertFalse(result["ok"])

    def test_old_kubernetes_rejected(self):
        old = deepcopy(CLUSTER)
        old["version"]["serverVersion"]["minor"] = "26"
        report = k3s.check_cluster(old["nodes"], old["version"], "k3s-news-dev")
        self.assertFalse(report["ok"])
        self.assertFalse(report["timezone_api_supported"])

    def test_no_nodes_rejected(self):
        state = deepcopy(CLUSTER)
        state["nodes"]["items"] = []
        self.assertFalse(k3s.check_cluster(state["nodes"], state["version"],
                                           "k3s-news-dev")["ok"])

    def test_kubectl_has_no_mutation(self):
        class Result:
            returncode = 0
            stdout = '{"items":[]}'
            stderr = ""
        with patch.object(k3s.subprocess, "run", return_value=Result()) as execute:
            k3s.kubectl_json("k3s-news-dev", ["get", "nodes"])
            cmd = execute.call_args.args[0]
            self.assertEqual(cmd, ["kubectl", "--context", "k3s-news-dev",
                                   "--request-timeout=8s", "get", "nodes", "-o", "json"])
            self.assertFalse(any(i in cmd for i in ("apply", "delete", "patch", "create")))


if __name__ == "__main__":
    unittest.main()
