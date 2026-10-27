#!/usr/bin/env python3
"""Safe K3s read-only readiness checks. Does not create, apply or modify resources.

Use an explicit kubectl context. Run in --fixture mode for offline CI.
No deployment of Hermes or news CronJobs happens here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path
import sys

MIN_K8S_MINOR = 27  # CronJob timeZone stabilized in v1.27


def check_cluster(nodes: object, version: object, desired_context: str) -> dict:
    if not isinstance(nodes, dict) or not isinstance(version, dict):
        raise ValueError("Kubernetes response is not an object")
    entries = nodes.get("items", [])
    if not isinstance(entries, list):
        raise ValueError("nodes.items must be a list")
    server = version.get("serverVersion", version)
    minor_raw = str(server.get("minor", "0")).rstrip("+")
    major_raw = str(server.get("major", "0"))
    major = int(major_raw)
    minor = int(minor_raw)
    results = []
    for entry in entries:
        status = entry.get("status", {})
        conditions = {r.get("type"): r.get("status") for r in status.get("conditions", [])}
        results.append({
            "node": entry.get("metadata", {}).get("name", "unknown"),
            "ready": conditions.get("Ready") == "True",
            "memory_pressure": conditions.get("MemoryPressure") == "True",
            "disk_pressure": conditions.get("DiskPressure") == "True",
            "pid_pressure": conditions.get("PIDPressure") == "True",
            "allocatable": {k: v for k, v in status.get("allocatable", {}).items()
                            if k in ("cpu", "memory", "pods")},
        })
    supported = (major > 1 or (major == 1 and minor >= MIN_K8S_MINOR))
    safe = (supported and bool(results) and
            all(n["ready"] and not (n["memory_pressure"] or n["disk_pressure"] or n["pid_pressure"])
                for n in results))
    return {"ok": safe, "kube_context": desired_context, "server_version": f"{major}.{minor}",
            "timezone_api_supported": supported, "nodes": results,
            "limitations": [
                "This probe does not verify SSH access, VM disks, backups, container registry pulls, NTP or external RSS.",
                "No Terraform plan/apply, Helm installation or Hermes gateway launch was performed.",
                "Confirm the exact target cluster and inspect current resource usage before scheduling jobs.",
            ]}


def kubectl_json(context: str, arguments: list[str]) -> dict:
    cmd = ["kubectl", "--context", context, "--request-timeout=8s", *arguments, "-o", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=12, check=False)
    if proc.returncode:
        # Errors may include cluster internals; don't print raw stderr.
        raise RuntimeError(f"kubectl failed with code {proc.returncode} for command: {arguments[0]}")
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, help="Explicit kubectl context; no default context")
    parser.add_argument("--fixture", type=Path, help="Offline fixture with nodes + version objects")
    args = parser.parse_args()
    try:
        if args.fixture:
            fixtures = json.loads(args.fixture.read_text(encoding="utf-8"))
            report = check_cluster(fixtures["nodes"], fixtures["version"], args.context)
        else:
            # No credentials or state are read or emitted beyond kubectl configuration.
            nodes = kubectl_json(args.context, ["get", "nodes"])
            version = kubectl_json(args.context, ["version"])
            report = check_cluster(nodes, version, args.context)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 3
    except Exception as exc:
        print(json.dumps({"ok": False, "error_type": type(exc).__name__,
                          "action": "Check selected Kube context, RBAC and API reachability."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
