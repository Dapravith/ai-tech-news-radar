# AI News Radar: phase 1 audit, migration boundaries and incident playbook

## Baseline (checked 27 October 2026)

Source of truth: GitHub `main` in `Dapravith/ai-tech-news-radar`.
Four independent publishers still run with GitHub Actions:
Cambodia local news, seven-topic trending, 3-hour tech radar,
and two engineering/IT support channel digests. The repository did not
previously contain Terraform, Kubernetes manifests, Hermes deployment files
or a durable centralized delivery database.

### Evidence-based incident findings

1. **Late GitHub workflow creation:** Cambodia jobs scheduled for the morning
   were actually instantiated at 05:16Z and 05:40Z (12:16 and 12:40 ICT)
   on Oct 27. This is an upstream GitHub Actions scheduling delay.
   Changing Python daypart labels cannot make the workflow start on time.
2. **Misclassified report:** earlier `local.hour >= 12` labeled a 12:16 ICT
   report as evening. PR #14 already fixed daypart classification and
   historical state mapping.
3. **Duplicate-delivery window:** scripts send Telegram first, then write
   delivered IDs and push JSON state to Git. The HTTP send and Git push are
   not one atomic transaction; push failures can cause a replay.
4. **Log confusion:** unittest negative-path tests print ERROR/WARNING
   lines by design. The publish-job result, application log section,
   accepted Telegram API responses, and persisted delivery state must
   be correlated before calling this a live incident.
5. **Agent authority:** no verified Hermes runtime or AI policy currently
   deploys from this repository. A repo's name or Telegram bot username
   is not evidence that Hermes is active.

## Incident triage (deterministic; AI is advisory)

Identify workflow run ID, triggered event, created/start time UTC and ICT,
expected cron slot when provable from `github.event.schedule`, and the
current repository commit. Collect the **production application log step**,
source feed counts and last state commit. Avoid exposing tokens, chat IDs,
message contents containing private data, or access credentials.

| Symptom | Evidence required | Operator response |
| --- | --- | --- |
| Late report | Planned cron from workflow event, actual runner timestamp | Record lag; check missed runs; evaluate dedicated scheduler |
| Empty report | Feed counts, producer allowlist and freshness exclusions | Do not fabricate news or widen trust policy automatically |
| Telegram forbidden | Bot rights, channel membership and API error code (redacted) | Repair permissions manually; no credential pasted into logs |
| Duplicate report | Message ID, delivery state commit, overlapping publishers | Freeze one publisher; inspect persistence window before retry |
| Agent fails | Model quota, optional Hermes gateway health and rate limits | Deterministic fallback; no hallucinated article summaries |
| Kubernetes job fails | Namespace/events/pod logs, image pull, CPU/memory and exit code | Keep scheduled shadow jobs suspended; never activate publishing as a workaround |

### Practical read-only diagnostics

```bash
python3 scripts/diagnose_delivery.py --repo Dapravith/ai-tech-news-radar
python3 -m unittest discover -s tests -v

# After a human approves a K3s cluster:
kubectl --context YOUR_CONTEXT -n news-radar-shadow get cronjobs,jobs,pods
kubectl --context YOUR_CONTEXT -n news-radar-shadow describe cronjob cambodia-morning
kubectl --context YOUR_CONTEXT -n news-radar-shadow get events --sort-by=.lastTimestamp
```

The GitHub REST run list cannot prove original cron scheduled time; do not
misinterpret its `created_at` as that planned timestamp. Green jobs cannot
prove receipt by both Telegram channel and private subscriber.

## Change controls

- **One publishing authority:** GitHub is production until a separately
  reviewed cutover; no concurrent Hermes, GitHub and K3s publishers.
- **No new model authority:** Hermes can rank/summarize from verified inputs,
  but is not allowed to alter infra, terraform, RBAC, k8s, secrets or live code.
- **No secrets in code/images/state:** Helm shadow jobs contain no token env vars;
  app container excludes `state/`; Terraform manages no secrets.
- **Explicit approvals:** Confirm VPS/provider, kubecontext, DNS/network, paid
  model limits, state backend, persistent deduplication, rollback and cost.
- **Fail-closed cutover:** Shadow run succeeds with real feed URLs and 0 public
  posts, test shutdown/restart, then create durable state adapter, reconcile
  Telegram and persistence before any production switch.

## Completion criteria for phase 1

- [ ] Helm lint/template and Terraform fmt/validate on every PR.
- [ ] Safety tests fail if shadow jobs can publish or escape namespace.
- [ ] Docker image builds and Python imports as nonroot without credentials.
- [ ] Offline incident-diagnostics test explains API data limitations.
- [ ] No K3s resources are deployed or Telegram jobs altered by the PR.
- [ ] Human reviews CI logs, approves the baseline and hosting assumptions.

## Next decisions (do not implement prematurely)

1. Choose K3s host/provider and actual Kube context. Single-node K3s has no
   high availability; assess outages and backups.
2. Choose a reliable cron control plane; K3s CronJob is more directly controlled
   than GitHub Actions but still approximate and requires idempotent jobs.
3. Adopt durable, transactional delivery records with a reconciliation plan.
   Exactly-once Telegram delivery cannot be guaranteed by the Bot API and
   a separate database alone.
4. Validate Hermes Docker image, gateway persistence, network boundaries,
   tool permissions and model provider. No Docker socket mounts or privileged
   pods. Publish AI summaries only when human-verifiable sources are attached.

The uploaded *From Alert to Auto-Fix (CODE-C 2026)* presentation motivates
context-rich incident evidence, deterministic classification and restricted
model authority. Those are proposed process controls, **not claims** that
this repository already has observability or self-healing production infrastructure.
