# Terraform phase 1: isolated Kubernetes shadow namespace

**Scope:** An already-running Kubernetes/K3s cluster. This code manages only a
`news-radar-shadow` namespace and a small resource quota, not a VM, cloud account,
K3s control plane, application secrets, DNS, storage or production workloads.

## Safe review (no cluster)
```sh
cd infra/terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

## Controlled apply, after independent cluster and cost approval
```sh
cp terraform.tfvars.example terraform.tfvars
# Set the exact kube context; inspect kubectl config get-contexts first.
terraform plan -out=shadow.tfplan
terraform show shadow.tfplan
# Terraform apply only after a human verifies that this is the intended cluster.
terraform apply shadow.tfplan
```

State defaults to **local development** because the cloud/provider and approved remote
backend are not yet known. No CI runs `terraform plan` or `terraform apply` with
cluster credentials. Use a secured remote backend with locking before any shared work.
Never put Telegram secrets or Hermes model keys in Terraform variables or state.

Do not copy the project's live `state/*.json` into this shadow deployment.
The associated Helm CronJobs are suspended by default and execute only `--dry-run --test-mode`
when consciously resumed. They cannot publish to Telegram.

**Next decision:** Confirm hosting provider, K3s availability, backup location,
secrets management, and durable delivery datastore before proposing production migration.
