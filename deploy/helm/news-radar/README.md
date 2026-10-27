# Helm phase 1: suspended shadow cronjobs

Safety invariant: **this chart cannot publish to Telegram**.
Every job has both `--dry-run` and `--test-mode`, no Telegram secrets,
a disabled Kubernetes service account token, and `suspend: true` enforced
in template logic (attempting to override it causes Helm to fail).

Kubernetes CronJobs use `timeZone: Asia/Phnom_Penh` rather than manually
converting UTC. Controller scheduling is approximate, so production will
still need a durable idempotency store and end-to-end delivery monitoring.
`startingDeadlineSeconds: 300` skips stale shadow jobs instead of replaying
multi-hour old briefings.

## Local rendering validation
```sh
helm lint deploy/helm/news-radar
helm template radar-shadow deploy/helm/news-radar \
  --namespace news-radar-shadow > /tmp/news-radar-shadow.yaml
```

## Future operator steps (do not run until K3s host is approved)
1. Apply reviewed Terraform namespace/quota configuration.
2. Build the container in CI; sign and pin its immutable image digest.
3. Update the shadow image reference.
4. Inspect Helm dry-run output for six suspended jobs and no credentials.
5. Run `helm upgrade --install` only after a change review.
6. Run one **manual dry-run Kubernetes Job** and collect its logs. This Helm chart
   never unsuspends scheduled collection; enabling a future stage requires a
   separate explicitly reviewed deployment artifact.

Current GitHub Actions are the **only production publishers**. No Telegram bot
token, Hermes API key or Terraform backend credential is used here.
