"""Offline guards for the shadow-only Terraform/K3s news platform."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


class ShadowDeploymentContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chart = (ROOT / "deploy/helm/news-radar/templates/cronjobs.yaml").read_text()
        cls.values = (ROOT / "deploy/helm/news-radar/values.yaml").read_text()
        cls.terraform = (ROOT / "infra/terraform/main.tf").read_text()
        cls.vars = (ROOT / "infra/terraform/variables.tf").read_text()
        cls.docker = (ROOT / "Dockerfile").read_text()

    def test_never_publish_or_unsuspend_in_first_phase(self):
        self.assertIn("suspend: true", self.chart)
        self.assertIn('fail "Cannot activate CronJobs from this phase 1 chart:', self.chart)
        self.assertIn('args: ["--dry-run", "--test-mode"]', self.chart)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", self.chart)
        self.assertNotIn("OPENROUTER_API_KEY", self.chart)
        self.assertNotIn("API_SERVER_KEY", self.chart)
        self.assertNotIn("hermes gateway run", self.chart)

    def test_exact_kh_timezone_and_bounded_jobs(self):
        for item in ("timeZone: Asia/Phnom_Penh", "concurrencyPolicy: Forbid",
                     "startingDeadlineSeconds: 300", "activeDeadlineSeconds: 600",
                     "backoffLimit: 1", "suspend: true"):
            self.assertIn(item, self.chart)
        for scheduled in ('23 7 * * *', '23 12 * * *', '13 18 * * *'):
            self.assertIn(scheduled, self.values)

    def test_pod_runs_nonroot_no_api_token_readonly(self):
        for text in ("automountServiceAccountToken: false", "runAsNonRoot: true",
                     "readOnlyRootFilesystem: true", "allowPrivilegeEscalation: false",
                     'drop: ["ALL"]', "RuntimeDefault"):
            self.assertIn(text, self.chart)
        self.assertRegex(self.docker, r"USER\s+10001:10001")
        self.assertIn('ENTRYPOINT ["python"]', self.docker)
        self.assertIn("COPY --chown=10001:10001 scripts/smoke_container.py", self.docker)


    def test_terraform_scope_cannot_be_redirected_to_production(self):
        self.assertIn('default     = "news-radar-shadow"', self.vars)
        self.assertIn('var.namespace == "news-radar-shadow"', self.vars)
        self.assertIn("prevent_destroy = true", self.terraform)
        self.assertIn("kubernetes_resource_quota_v1", self.terraform)
        self.assertNotIn("kubernetes_secret", self.terraform)
        self.assertNotIn("helm_release", self.terraform)
        self.assertIn("config_context = var.kube_context", self.terraform)

    def test_docker_ignores_state_and_secrets(self):
        ignored = (ROOT / ".dockerignore").read_text().splitlines()
        for name in ("state", ".env", ".git", "infra"):
            self.assertIn(name, ignored)
        gitignored = (ROOT / ".gitignore").read_text()
        self.assertIn("**/*.tfstate", gitignored)
        self.assertIn("**/terraform.tfvars", gitignored)


if __name__ == "__main__":
    unittest.main()
