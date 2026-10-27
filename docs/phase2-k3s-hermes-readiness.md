# Phase 2 — K3s hosting verification and Hermes integration contract

## Scope and boundary

The Phase 1 shadow platform in PR #15 has no running K3s cluster and no real Hermes.
This Phase 2 change adds **read-only** cluster and A2A checks, a full offline
Docker smoke test, and a throwaway **kind Kubernetes cluster in GitHub CI** that
admits the six suspended Helm CronJobs and runs one network-independent smoke Job.
Only that disposable CI cluster receives Kubernetes objects. No production VPS is
provisioned, SSH connection attempted, Telegram message sent, production cron
switched, or real-server Kubernetes object applied.

### Known pipeline incidents (evidence)
- PR #15's first Terraform CI run failed on `terraform fmt -check` (main.tf
  label alignment); a subsequent commit corrected formatting. Latest run
  40463964229: Terraform, Helm, Python and Docker checks all succeeded.
- During Hermes A2A probe hardening, CI failed because one test still mocked
  `urlopen` after the implementation switched to a no-redirect HTTP opener.
  The test was updated and the latest CI run passed. No production workflow was
  affected.
- Previous Docker job only imported modules. It could not detect an unusable
  read-only filesystem, a broken RSS dry-run route, missing state defaults,
  bad destination rendering or a mistakenly enabled Telegram send.
- Production GitHub Actions started a Cambodia scheduled job at **12:16 ICT**,
  hours after its intended morning cron. This is a scheduler issue; K3s migration
  may improve operator control but cannot offer mathematical exactness.

### Proposed cutover architecture (NOT active)
1. Terraform: provision or verify an approved host and secure K3s cluster.
2. Existing news application: CronJobs in `Asia/Phnom_Penh` (one authoritative
   publishing scheduler at cutover), webhook/Telegram sending and a durable
   idempotency ledger in a separate app-owned database.
3. Hermes: isolated **optional analysis service**, not Telegram publisher,
   not K8s controller or DevOps agent. It receives only previously vetted,
   bounded news input; responses are recommendations requiring deterministic
   validation and link attribution. If Hermes fails, preserve the existing
   plain-source digest.
4. Delivery monitor: lag / RSS availability / accepted bot response / durable
   state; alerts are incident records with request/run ID.
5. Shadow tests first; never run both new CronJobs and GitHub Actions publishers.

### Run Phase 2 offline preflight
```bash
python3 -m unittest discover -s tests -v
python3 scripts/preflight_k3s.py --context k3s-news-dev \
  --fixture tests/fixtures/k3s-ready.json
python3 scripts/hermes_readiness.py \
  --fixture tests/fixtures/hermes-agent-card.json

docker build -t news-radar:shadow .
docker run --rm --network none --read-only \
  --tmpfs /app/out:uid=10001,gid=10001 \
  -e TELEGRAM_BOT_TOKEN= \
  news-radar:shadow -m scripts.smoke_container
```

### Kubernetes API integration (CI only)

GitHub Actions starts a disposable kind cluster (not the real K3s host),
loads a locally built image without publishing to a registry, applies six
**suspended** CronJobs, verifies that no scheduled Jobs were created,
and manually executes `deploy/k8s/shadow-smoke-job.yaml` under restricted
nonroot settings. The Job uses fixture data, does not need external RSS,
has no Telegram secret, and exits only when it has produced a correct
AFTERNOON report. The CI cluster is discarded after the run. This proves
Kubernetes admission and representative container execution, **not**
live K3s availability or provider-network behavior.

### Verify an approved existing K3s cluster (read only)
```bash
kubectl config get-contexts
# Choose and double-check explicit nonproduction context:
python3 scripts/preflight_k3s.py --context k3s-news-dev
kubectl --context k3s-news-dev get nodes -o wide
kubectl --context k3s-news-dev get --raw /readyz
# On the actual host, check time synchronization without modifying it:
timedatectl show -p NTPSynchronized -p Timezone
```

This only inspects Kubernetes status; it cannot prove provider reachability from
your location, external TLS, image registry access, persistent storage, or backup
restores. Do **not** run Terraform apply or Helm install until a human verifies
the host, kube-context, budget and rollback plan.

### Hermes verification (read only)

Official Nous Research docs specify a canonical A2A Agent Card at
`/.well-known/agent-card.json` and configurable per-peer authentication.
Keep its gateway private (loopback or private network) and configure separate
per-peer tokens. **Never expose A2A port 9900 publicly just for news enrichment.**
A2A task calls use a live agent with its tools, so task execution requires
additional data minimization and strict agent permissions.

```bash
# On the Hermes host or authorized private tunnel ONLY:
python3 scripts/hermes_readiness.py --origin http://127.0.0.1:9900
# For a trusted remote HTTPS tunnel:
# HERMES_A2A_TOKEN from local secret store, never in a URL or repository
python3 scripts/hermes_readiness.py --origin https://YOUR-AUTHENTICATED-ENDPOINT
```

A healthy Agent Card is not proof that AI providers, gateway memory, model
quota, Telegram or news summarization are functioning. Do not turn on model
calls, A2A tasks or a Hermes Kubernetes Deployment in this phase.
The exact Hermes image digest, secrets mount, /opt/data persistence, backups and
gateway lifecycle are platform-dependent and await a real approved host.

### Debugging guide

| Failure signal | Likely cause | Minimum read-only evidence |
| --- | --- | --- |
| `ImagePullBackOff` | Shadow tag is placeholder, registry credentials, blocked egress | Pod events; image ref and registry access |
| `CrashLoopBackOff` | Wrong command, missing config, non-writable output directory | Last/previous container logs and pod securityContext |
| `Pending` | Insufficient nodes, resource quota, taints | Pod describe, events, node Ready, quota |
| `kubectl auth` / 403 | Wrong context or RBAC | `kubectl config get-contexts`, can-i (read only) |
| A2A connection refused | Hermes gateway stopped or A2A disabled | Local 9900 listener, process logs, Agent Card GET |
| A2A 401/403 | Wrong per-peer credential or gateway policy | Sanitized status code; no token exposure |
| Gemini/OpenRouter 429 | Provider free-tier limits or model unavailable | Request ID, status and retry-after; deterministic digest fallback |
| GitHub late cron | GitHub scheduler delay | Event cron, planned vs actual time (not only Actions run status) |
| Terraform CI fails | fmt / version / provider lock / syntax | First failed step and exact formatter/validator output |

### Exit criteria before K3s/Hermes live work

- [ ] Phase 1 PR #15 reviewed and merged (not forced by this PR)
- [x] Container and ephemeral Kubernetes Job generate valid dry-run reports offline
- [ ] Cluster preflight detects unhealthy nodes and unsupported versions
- [ ] Hermes A2A probe validates card and rejects unsafe remote HTTP URLs
- [ ] Nonproduction K3s host and backup are identified; estimated monthly cost approved
- [ ] Secrets and Hermes permissions independently reviewed
- [ ] Shadow deployment has ZERO tokens and ZERO Telegram posts
- [ ] Helm image tag replaced with pinned, locally built/proven artifact
- [ ] Controlled rollback remains available

**No promises of zero technical debt or 100% uptime.** Operational acceptance
requires measured delivery-time distributions, duplicate rate, controlled
failure injection and recovery drills on the real cluster.
